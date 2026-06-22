# pipeline/conversation_orchestrator.py
"""
Conversation Orchestrator — the multi-agent replacement for RAGOrchestrator.

Flow (per the MAI Agentic AI doc):
  1. Classify intent
  2. Decide whether patient context is needed
  3. Route to the right agent(s)
  4. Merge outputs into one answer
  5. Run final safety review

Reuses existing services:
  - MongoDBService  (sessions, messages)
  - EmbeddingService / RetrievalService  (Pinecone)
  - GenerationService  (OpenAI)
  - ContextService  (short-term + long-term memory)

Greeting short-circuit is preserved from the original orchestrator.
"""
import asyncio
from typing import Dict, Any, List, Optional

from agents import (
    IntentClassifier,
    MedicationAgent,
    LaboratoryAgent,
    ProcedureAgent,
    EducationAgent,
    SafetyAgent,
    PatientContextAgent,
    ActionAgent,
    AgentResponse,
)
from agents.consent import check_patient_data_consent, ConsentResult
from pipeline.rag_orchestrator import _is_simple_greeting, _greeting_reply
from services import (
    EmbeddingService,
    RetrievalService,
    GenerationService,
    ContextService,
    MongoDBService,
)
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class ConversationOrchestrator:
    """
    Multi-agent orchestrator that classifies intent, routes to specialist
    agents, merges their outputs, and runs a final safety review.
    """

    def __init__(
        self,
        mongodb_service: MongoDBService,
        embedding_service: EmbeddingService,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
        context_service: ContextService,
    ):
        self.mongodb_service = mongodb_service
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service
        self.context_service = context_service

        self.intent_classifier = IntentClassifier(generation_service)

        self.agents: Dict[str, Any] = {
            "medication": MedicationAgent(generation_service, retrieval_service, mongodb_service),
            "lab": LaboratoryAgent(generation_service, retrieval_service),
            "procedure": ProcedureAgent(generation_service, retrieval_service),
            "education": EducationAgent(generation_service, retrieval_service),
            "triage": SafetyAgent(generation_service, retrieval_service),
            "context": PatientContextAgent(generation_service, retrieval_service),
            "action": ActionAgent(generation_service, retrieval_service, mongodb_service),
        }
        self.safety_agent: SafetyAgent = self.agents["triage"]
        self.patient_context_agent: PatientContextAgent = self.agents["context"]

        self.initialized = False

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    async def initialize(self):
        try:
            logger.info("Initializing Conversation Orchestrator …")
            config.validate_config()
            if not self.initialized:
                await self.mongodb_service.initialize()
                await self.embedding_service.initialize()
                await self.retrieval_service.initialize()
                await self.generation_service.initialize()
                await self.context_service.initialize()
                self.initialized = True
            logger.info("Conversation Orchestrator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Conversation Orchestrator: {e}")
            raise

    async def cleanup(self):
        try:
            await self.mongodb_service.close()
            logger.info("Conversation Orchestrator cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    # ------------------------------------------------------------------ #
    #  Main entry point                                                   #
    # ------------------------------------------------------------------ #

    async def process_query(
        self,
        query: str,
        patient_id: Optional[str] = None,
        practitioner_id: Optional[str] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        if not self.initialized:
            raise ValueError("Conversation Orchestrator not initialized. Call initialize() first.")

        if patient_id:
            context_id = patient_id
        elif practitioner_id:
            context_id = practitioner_id
        else:
            raise ValueError("Either patient_id or practitioner_id must be provided")

        try:
            logger.info(f"Processing query for {context_id}: {query[:100]}…")

            # Persist user message
            await self.context_service.add_message(
                patient_id=context_id, role="user", content=query, session_id=session_id
            )

            # ---- Greeting short-circuit ---- #
            if _is_simple_greeting(query):
                greeting_response = _greeting_reply(query)
                await self.context_service.add_message(
                    patient_id=context_id, role="assistant", content=greeting_response, session_id=session_id
                )
                return {
                    "answer": greeting_response,
                    "context_used": [],
                    "sources": [],
                    "metadata": {
                        "patient_id": patient_id,
                        "practitioner_id": practitioner_id,
                        "session_id": session_id,
                        "simple_greeting": True,
                    },
                    "agent_details": {},
                    "intent_classification": {"intents": ["greeting"], "needs_patient_context": False},
                    "retrieval_stats": {"simple_greeting_short_circuit": True},
                    "context_summary": "Simple greeting; no context retrieved.",
                }

            # ---- Step 1: Classify intent ---- #
            short_term_context, long_term_context = await self.context_service.get_full_context(
                patient_id=context_id, session_id=session_id
            )

            classification = await self.intent_classifier.classify(
                query=query, conversation_context=short_term_context
            )
            intents: List[str] = list(classification["intents"])
            needs_patient_context: bool = classification["needs_patient_context"]

            logger.info(f"Intent classification: {intents} | patient_context_needed: {needs_patient_context}")

            # ---- Step 1b: Consent gate ---- #
            consent: Optional[ConsentResult] = None
            if patient_id and (needs_patient_context or any(i != "education" for i in intents)):
                consent = await check_patient_data_consent(
                    patient_id=patient_id,
                    practitioner_id=practitioner_id,
                )
                if not consent.authorized:
                    logger.warning(f"Consent denied for patient {patient_id}: {consent.reason}")
                    denied_msg = (
                        "I'm unable to access patient-specific records at this time. "
                        f"Reason: {consent.reason} "
                        "Please verify your authorization and try again, or ask a general health question."
                    )
                    await self.context_service.add_message(
                        patient_id=context_id, role="assistant", content=denied_msg, session_id=session_id,
                    )
                    return {
                        "answer": denied_msg,
                        "context_used": [],
                        "sources": [],
                        "metadata": {
                            "patient_id": patient_id,
                            "practitioner_id": practitioner_id,
                            "session_id": session_id,
                            "consent_denied": True,
                        },
                        "intent_classification": classification,
                        "agents_invoked": [],
                        "agent_details": {},
                        "all_warnings": [],
                        "all_clinician_triggers": [],
                        "safety_review": {"safe": True, "issues": []},
                        "retrieval_stats": {},
                        "context_summary": "Consent denied; no data accessed.",
                    }
                logger.info(f"Consent granted for patient {patient_id}, scopes: {consent.scopes}")

            # ---- Step 1c: Triage precedence ---- #
            if "triage" in intents:
                triage_response = await self.safety_agent.handle(
                    query=query,
                    patient_id=patient_id,
                    practitioner_id=practitioner_id,
                    conversation_context=short_term_context,
                )
                urgency = triage_response.metadata.get("urgency", "not_urgent")
                logger.info(f"Triage urgency: {urgency}")

                if urgency in ("emergency", "urgent"):
                    # Short-circuit: triage overrides all other agents.
                    # Still run mandatory safety review on the triage answer.
                    safety_result = await self.safety_agent.review_merged_answer(
                        triage_response.answer, query,
                    )
                    final_answer = safety_result.get("revised_answer", triage_response.answer)

                    await self.context_service.add_message(
                        patient_id=context_id, role="assistant",
                        content=final_answer, session_id=session_id,
                    )
                    return {
                        "answer": final_answer,
                        "context_used": [],
                        "sources": [],
                        "metadata": {
                            "patient_id": patient_id,
                            "practitioner_id": practitioner_id,
                            "session_id": session_id,
                            "triage_short_circuit": True,
                            "urgency": urgency,
                        },
                        "intent_classification": classification,
                        "agents_invoked": ["triage"],
                        "agent_details": {"triage": triage_response.to_dict()},
                        "all_warnings": triage_response.warnings,
                        "all_clinician_triggers": triage_response.clinician_triggers,
                        "safety_review": {
                            "safe": safety_result.get("safe", True),
                            "issues": safety_result.get("issues", []),
                        },
                        "retrieval_stats": {},
                        "context_summary": f"Triage short-circuit ({urgency}). Safety review applied.",
                    }

                # Not urgent — remove triage from the intents so remaining
                # agents handle the actual question.
                intents = [i for i in intents if i != "triage"]
                if not intents:
                    intents = ["education"]

            # ---- Step 2: Retrieve context (shared across agents) ---- #
            retrieved_contexts: List[Dict[str, Any]] = []
            sources: List[Dict[str, Any]] = []
            retrieval_stats: Dict[str, Any] = {}

            if needs_patient_context or patient_id:
                retrieval_result = await self.retrieval_service.retrieve_context(
                    query=query, patient_id=patient_id, practitioner_id=practitioner_id
                )
                retrieved_contexts = retrieval_result.get("contexts", [])
                sources = retrieval_result.get("sources", [])
                retrieval_stats = {
                    "total_matches": retrieval_result.get("total_matches", 0),
                    "filtered_matches": retrieval_result.get("filtered_matches", 0),
                }

            # ---- Step 2b: Patient Context Agent (handoff to specialists) ---- #
            patient_context_summary: Optional[str] = None
            if needs_patient_context and patient_id and "context" not in intents:
                ctx_response = await self.patient_context_agent.handle(
                    query=query,
                    patient_id=patient_id,
                    practitioner_id=practitioner_id,
                    retrieved_contexts=retrieved_contexts,
                    conversation_context=short_term_context,
                )
                if ctx_response.answer.strip():
                    patient_context_summary = ctx_response.answer.strip()
                    logger.info(
                        "Patient Context Agent produced summary (%d chars) — "
                        "will be injected into specialist agents",
                        len(patient_context_summary),
                    )

            # ---- Step 3: Route to agent(s) in parallel ---- #
            agent_tasks = []
            agent_names = []
            for intent in intents:
                agent = self.agents.get(intent)
                if agent:
                    agent_tasks.append(
                        agent.handle(
                            query=query,
                            patient_id=patient_id,
                            practitioner_id=practitioner_id,
                            retrieved_contexts=retrieved_contexts,
                            conversation_context=short_term_context,
                            patient_context_summary=patient_context_summary,
                        )
                    )
                    agent_names.append(intent)

            if not agent_tasks:
                agent_tasks.append(
                    self.agents["education"].handle(
                        query=query,
                        retrieved_contexts=retrieved_contexts,
                        conversation_context=short_term_context,
                        patient_context_summary=patient_context_summary,
                    )
                )
                agent_names.append("education")

            agent_responses: List[AgentResponse] = await asyncio.gather(*agent_tasks)

            # ---- Step 4: Merge outputs ---- #
            merged_answer = self._merge_agent_responses(agent_responses, agent_names)

            # ---- Step 4b: Citation / evidence normalization (optional) ---- #
            citations = self._normalize_citations(agent_responses, retrieved_contexts)

            # ---- Step 5: Final safety review (mandatory) ---- #
            safety_result = await self.safety_agent.review_merged_answer(merged_answer, query)
            final_answer = safety_result.get("revised_answer", merged_answer)
            safety_issues = safety_result.get("issues", [])

            # Persist assistant message
            await self.context_service.add_message(
                patient_id=context_id, role="assistant", content=final_answer, session_id=session_id
            )

            # Collect all warnings / clinician triggers from agents
            all_warnings: List[str] = []
            all_clinician_triggers: List[str] = []
            agent_detail_map: Dict[str, Any] = {}
            for name, resp in zip(agent_names, agent_responses):
                all_warnings.extend(resp.warnings)
                all_clinician_triggers.extend(resp.clinician_triggers)
                agent_detail_map[name] = resp.to_dict()

            context_summary = (
                f"Intents: {intents} | Agents invoked: {agent_names} | "
                f"Retrieved {len(retrieved_contexts)} docs | "
                f"Safety issues: {len(safety_issues)}"
            )

            return {
                "answer": final_answer,
                "context_used": [ctx.get("text", "")[:200] + "…" for ctx in retrieved_contexts[:3]],
                "sources": sources,
                "citations": citations,
                "metadata": {
                    "patient_id": patient_id,
                    "practitioner_id": practitioner_id,
                    "session_id": session_id,
                    "retrieved_documents": len(retrieved_contexts),
                    "short_term_messages": len(short_term_context),
                    "has_long_term_context": bool(long_term_context.strip()),
                    "consent_granted": consent.authorized if consent else None,
                    "patient_context_injected": patient_context_summary is not None,
                },
                "intent_classification": classification,
                "agents_invoked": agent_names,
                "agent_details": agent_detail_map,
                "all_warnings": all_warnings,
                "all_clinician_triggers": all_clinician_triggers,
                "safety_review": {
                    "safe": safety_result.get("safe", True),
                    "issues": safety_issues,
                },
                "retrieval_stats": retrieval_stats,
                "context_summary": context_summary,
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            try:
                await self.context_service.add_message(
                    patient_id=context_id,
                    role="assistant",
                    content=f"I apologize, but I encountered an error: {str(e)}",
                    session_id=session_id,
                )
            except Exception:
                pass
            return {
                "answer": f"I apologize, but I encountered an error while processing your query: {str(e)}",
                "context_used": [],
                "sources": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------ #
    #  Merge                                                              #
    # ------------------------------------------------------------------ #

    def _merge_agent_responses(self, responses: List[AgentResponse], agent_names: List[str]) -> str:
        """
        Merge outputs from multiple specialist agents into one coherent answer.
        For single-agent responses, return as-is.
        For multi-agent, use the LLM to synthesise.
        """
        non_empty = [(name, r) for name, r in zip(agent_names, responses) if r.answer.strip()]
        if not non_empty:
            return "I'm sorry, I wasn't able to find an answer to your question. Please try rephrasing."

        if len(non_empty) == 1:
            return non_empty[0][1].answer

        # Multi-agent: ask the LLM to synthesise
        sections = []
        for name, resp in non_empty:
            sections.append(f"=== {resp.agent_name or name} ===\n{resp.answer}")

        merge_prompt = (
            "You are a medical assistant synthesiser. The user asked one question and "
            "multiple specialist agents have each produced a partial answer below.\n\n"
            "Combine them into ONE clear, coherent response. "
            "Preserve all warnings and 'contact clinician if' notes. "
            "Do not add new medical information beyond what the agents provided. "
            "Use a friendly, professional tone.\n\n"
            + "\n\n".join(sections)
        )

        try:
            merged = self.generation_service.client.chat.completions.create(
                model=self.generation_service.model_name,
                messages=[
                    {"role": "system", "content": "You merge specialist agent answers into one response."},
                    {"role": "user", "content": merge_prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            return merged.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Merge LLM call failed ({e}); concatenating agent outputs")
            return "\n\n---\n\n".join(r.answer for _, r in non_empty)

    # ------------------------------------------------------------------ #
    #  Citation / Evidence normalization                                  #
    # ------------------------------------------------------------------ #

    def _normalize_citations(
        self,
        agent_responses: List[AgentResponse],
        retrieved_contexts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Collect evidence references from agent responses and retrieval
        metadata into a normalized citation list.  Does not alter clinical
        substance — only structures provenance info for the frontend.
        """
        seen_texts: set = set()
        citations: List[Dict[str, Any]] = []

        for resp in agent_responses:
            for ref in resp.evidence_references:
                key = ref.get("text", "")[:80]
                if key and key not in seen_texts:
                    seen_texts.add(key)
                    citations.append({
                        "text": ref.get("text", ""),
                        "relevance_score": ref.get("score", 0),
                        "agent": resp.agent_name,
                    })

        for ctx in retrieved_contexts:
            key = ctx.get("text", "")[:80]
            if key and key not in seen_texts:
                seen_texts.add(key)
                meta = ctx.get("metadata", {})
                citations.append({
                    "text": ctx.get("text", "")[:300],
                    "relevance_score": ctx.get("score", 0),
                    "source_id": ctx.get("id", meta.get("id", "")),
                    "fhir_resource_type": meta.get("resource_type", ""),
                    "agent": "retrieval",
                })

        citations.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)
        return citations[:10]

    # ------------------------------------------------------------------ #
    #  Pass-through helpers (same interface as RAGOrchestrator)           #
    # ------------------------------------------------------------------ #

    async def get_chat_history(self, patient_id=None, practitioner_id=None, limit=10, session_id="default"):
        context_id = patient_id or practitioner_id
        if not context_id:
            return []
        return await self.context_service.get_chat_history(patient_id=context_id, session_id=session_id, limit=limit)

    async def clear_chat_history(self, patient_id=None, practitioner_id=None, session_id="default"):
        context_id = patient_id or practitioner_id
        if not context_id:
            raise ValueError("Either patient_id or practitioner_id must be provided")
        await self.context_service.clear_chat_history(patient_id=context_id, session_id=session_id)

    async def get_practitioner_patients(self, practitioner_id: str):
        return await self.mongodb_service.get_practitioner_patients(practitioner_id)

    async def set_practitioner_patients(self, practitioner_id: str, patients: list):
        return await self.mongodb_service.set_practitioner_patients(practitioner_id, patients)

    async def get_patient_summary(self, patient_id: str):
        try:
            retrieval_summary = await self.retrieval_service.get_patient_summary(patient_id)
            context_stats = await self.context_service.get_context_stats(patient_id)
            return {"patient_id": patient_id, "data_summary": retrieval_summary, "context_stats": context_stats}
        except Exception as e:
            logger.error(f"Error getting patient summary: {e}")
            return {"patient_id": patient_id, "error": str(e)}

    async def health_check(self):
        try:
            results = {
                "mongodb": await self.mongodb_service.health_check(),
                "embedding": await self.embedding_service.health_check(),
                "retrieval": await self.retrieval_service.health_check(),
                "generation": await self.generation_service.health_check(),
                "context": await self.context_service.health_check(),
            }
            results["overall"] = all(results.values())
            return results
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"overall": False, "error": str(e)}

    async def search_similar_cases(self, query: str, patient_id: str, top_k: int = 3):
        try:
            return await self.retrieval_service.search_similar_patients(
                query=query, exclude_patient_id=patient_id, top_k=top_k
            )
        except Exception as e:
            logger.error(f"Error searching similar cases: {e}")
            return []
