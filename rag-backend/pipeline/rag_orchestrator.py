# pipeline/rag_orchestrator.py
import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, Any, List
from services import (
    EmbeddingService, 
    RetrievalService, 
    GenerationService, 
    ContextService,
    MongoDBService
)
from utils.logger import get_logger
import config

logger = get_logger(__name__)

# Simple greetings that should get a short "what can I help with?" response instead of full RAG/context
SIMPLE_GREETINGS = frozenset({
    "hi", "hello", "hey", "hey there", "hi there", "hello there",
    "good morning", "good afternoon", "good evening", "good night", "gm", "gn", "good day",
    "howdy", "yo", "sup", "hiya", "greetings", "greeting", "hola", "heya", "hai",
    "namaste", "salutations", "morning", "evening", "afternoon",
    "hi there!", "hello!", "hey!",
})

# Whole-message phrases (no medical question) — still short-circuit without RAG
EXTENDED_GREETING_PHRASES = frozenset({
    "how are you",
    "how are you doing",
    "how are you today",
    "how's it going",
    "hows it going",
    "how do you do",
    "whats up",
    "what's up",
    "wassup",
    "nice to meet you",
    "pleased to meet you",
    "good to see you",
    "long time no see",
    "is anyone there",
    "anybody there",
    "you there",
})


def _normalize_greeting_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_trailing_punct(s: str) -> str:
    return s.rstrip("!?.…~ ").strip()


def _is_simple_greeting(query: str) -> bool:
    """Return True if the query is only a greeting, so we avoid dumping patient context."""
    if not query or not isinstance(query, str):
        return False
    normalized = _normalize_greeting_text(query)
    if not normalized:
        return False
    bare = _strip_trailing_punct(normalized)
    if bare in SIMPLE_GREETINGS or bare in EXTENDED_GREETING_PHRASES:
        return True
    # Very short messages that are only punctuation + greeting (e.g. "hi!", "hello :)")
    if len(bare) <= 22 and _strip_trailing_punct(re.sub(r"^[^\w]+|[^\w]+$", "", bare)) in SIMPLE_GREETINGS:
        return True
    return False


def _greeting_reply(query: str) -> str:
    """Warm, contextual reply for greeting-only messages (no retrieval)."""
    q = _normalize_greeting_text(query)
    bare = _strip_trailing_punct(q)
    hour = datetime.now(timezone.utc).hour
    if 5 <= hour < 12:
        tod_phrase = "Good morning"
    elif 12 <= hour < 17:
        tod_phrase = "Good afternoon"
    elif 17 <= hour < 22:
        tod_phrase = "Good evening"
    else:
        tod_phrase = "Hello"

    # Mirror explicit time-of-day from the user when clear
    if "morning" in bare or bare == "gm":
        opener = "Good morning! "
    elif "afternoon" in bare:
        opener = "Good afternoon! "
    elif "evening" in bare and "morning" not in bare:
        opener = "Good evening! "
    elif "night" in bare or bare == "gn":
        opener = "Good evening! "  # keep professional; "good night" often closes a chat
    elif bare in EXTENDED_GREETING_PHRASES or bare.startswith("how are"):
        opener = "I'm doing well, thank you for asking! "
    else:
        opener = f"{tod_phrase}! "

    bodies: List[str] = [
        (
            "I'm MaiBot, your Mai Health assistant. I can help you understand appointments, medications, "
            "symptoms, lab results, and follow-up questions—just ask in your own words."
        ),
        (
            "Welcome—I'm here to make health questions easier. Tell me what you're trying to do today "
            "(for example: book a visit, review a medicine, or interpret a result), and I'll guide you."
        ),
        (
            "Great to connect. Whether you need scheduling help, medication clarity, or a quick symptom check, "
            "describe what's on your mind and I'll respond with clear, practical information."
        ),
    ]
    idx = int(hashlib.sha256(bare.encode("utf-8")).hexdigest(), 16) % len(bodies)
    closer = " What would you like help with first?"
    return opener + bodies[idx] + closer


class RAGOrchestrator:
    """
    Main orchestrator for the RAG pipeline using modular services.
    Coordinates embedding, retrieval, context management, and generation.
    Enhanced to support both patient and practitioner queries.
    """
    
    def __init__(self, mongodb_service, embedding_service, retrieval_service, generation_service, context_service):
        self.mongodb_service = mongodb_service
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service
        self.context_service = context_service
        self.initialized = False
    
    async def initialize(self):
        """Initialize all services in proper order"""
        try:
            logger.info("Initializing RAG orchestrator and all services...")
            
            # Validate configuration
            config.validate_config()
            
            # Initialize services in dependency order
            if not self.initialized:
                # Initialize only what hasn't been initialized
                await self.mongodb_service.initialize()
                await self.embedding_service.initialize()
                await self.retrieval_service.initialize()
                await self.generation_service.initialize()
                await self.context_service.initialize()
                self.initialized = True
            logger.info("RAG orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG orchestrator: {e}")
            raise
    
    async def process_query(
        self, 
        query: str, 
        patient_id: str = None,
        practitioner_id: str = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Process a user query through the complete RAG pipeline.
        
        Args:
            query: User question/query
            patient_id: Patient identifier for single patient context
            practitioner_id: Practitioner identifier for multi-patient access
            session_id: Session identifier for conversation tracking
            
        Returns:
            Dictionary containing the answer and metadata
        """
        if not self.initialized:
            raise ValueError("RAG orchestrator not initialized. Call initialize() first.")
        
        # Determine the context ID (patient or practitioner)
        # Determine if this is a patient query or practitioner query
        if patient_id:
            context_id = patient_id
            context_type = "patient"
        elif practitioner_id:
            context_id = practitioner_id
            context_type = "practitioner"
        else:
            raise ValueError("Either patient_id or practitioner_id must be provided")
        
        try:
            logger.info(f"Processing query for {'patient' if patient_id else 'practitioner'} {context_id}: {query[:100]}...")
            
            # Step 1: Add user query to context
            await self.context_service.add_message(
                patient_id=context_id,  # Using context_id for both patient and practitioner contexts
                role="user",
                content=query,
                session_id=session_id
            )

            # Short-circuit for simple greetings: respond with a brief welcome and ask what they need,
            # without retrieving/injecting patient context (avoids dumping upserted data on "hi")
            if _is_simple_greeting(query):
                greeting_response = _greeting_reply(query)
                await self.context_service.add_message(
                    patient_id=context_id,
                    role="assistant",
                    content=greeting_response,
                    session_id=session_id
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
                    "retrieval_stats": {"simple_greeting_short_circuit": True},
                    "context_summary": "Simple greeting; no context retrieved.",
                }
            
            # Step 2: Get conversation context
            short_term_context, long_term_context = await self.context_service.get_full_context(
                patient_id=context_id,
                session_id=session_id
            )
            
            # Step 3: Retrieve relevant documents
            retrieval_result = await self.retrieval_service.retrieve_context(
                query=query,
                patient_id=patient_id,
                practitioner_id=practitioner_id
            )
            
            retrieved_contexts = retrieval_result.get("contexts", [])
            sources = retrieval_result.get("sources", [])
            
            # Step 4: Generate answer using all available context
            generation_result = await self.generation_service.generate_answer(
                query=query,
                retrieved_context=retrieved_contexts,
                short_term_context=short_term_context,
                long_term_context=long_term_context,
                patient_id=context_id
            )
            
            answer = generation_result.get("answer", "I apologize, but I couldn't generate a response.")
            
            # Step 5: Add assistant response to context
            await self.context_service.add_message(
                patient_id=context_id,
                role="assistant", 
                content=answer,
                session_id=session_id
            )
            
            # TESTING: Prepare detailed testing information for debugging
            # TODO: Remove this section after testing is complete
            context_summary = f"Retrieved {len(retrieved_contexts)} documents, {len(short_term_context)} short-term messages"
            if long_term_context.strip():
                context_summary += ", has long-term summary"
            
            if practitioner_id:
                context_summary += f", queried {retrieval_result.get('patients_queried', 0)} patients"
            
            # Prepare response
            response = {
                "answer": answer,
                "context_used": [ctx.get("text", "")[:200] + "..." for ctx in retrieved_contexts[:3]],
                "sources": sources,
                "metadata": {
                    "patient_id": patient_id,
                    "practitioner_id": practitioner_id,
                    "session_id": session_id,
                    "retrieved_documents": len(retrieved_contexts),
                    "short_term_messages": len(short_term_context),
                    "has_long_term_context": bool(long_term_context.strip()),
                    **generation_result
                },
                # TESTING: Additional fields for debugging (remove after testing)
                "prompt": generation_result.get("prompt", ""),
                "raw_response": generation_result.get("raw_response", ""),
                "retrieval_stats": {
                    "total_matches": retrieval_result.get("total_matches", 0),
                    "filtered_matches": retrieval_result.get("filtered_matches", 0),
                    "patients_queried": retrieval_result.get("patients_queried", 1 if patient_id else 0),
                    "namespace_used": f"patient-{context_id}" if not context_id.startswith('patient-') else context_id
                },
                "context_summary": context_summary
            }
            
            logger.info(f"Successfully processed query for {'patient' if patient_id else 'practitioner'} {context_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            
            # Still try to add error to context
            try:
                await self.context_service.add_message(
                    patient_id=context_id,
                    role="assistant",
                    content=f"I apologize, but I encountered an error: {str(e)}",
                    session_id=session_id
                )
            except:
                pass  # Don't let context errors mask the main error
            
            return {
                "answer": f"I apologize, but I encountered an error while processing your query: {str(e)}",
                "context_used": [],
                "sources": [],
                "error": str(e)
            }
    
    async def get_chat_history(
        self, 
        patient_id: str = None, 
        practitioner_id: str = None,
        limit: int = 10,
        session_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """Get chat history for a patient or practitioner"""
        try:
            context_id = patient_id if patient_id else practitioner_id
            if not context_id:
                return []
                
            return await self.context_service.get_chat_history(
                patient_id=context_id,
                session_id=session_id,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
    
    async def clear_chat_history(
        self, 
        patient_id: str = None,
        practitioner_id: str = None,
        session_id: str = "default"
    ) -> None:
        """Clear chat history for a patient or practitioner"""
        try:
            context_id = patient_id if patient_id else practitioner_id
            if not context_id:
                raise ValueError("Either patient_id or practitioner_id must be provided")
                
            await self.context_service.clear_chat_history(
                patient_id=context_id,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            raise
    
    async def get_practitioner_patients(self, practitioner_id: str) -> List[str]:
        """Get list of patients for a practitioner"""
        try:
            return await self.mongodb_service.get_practitioner_patients(practitioner_id)
        except Exception as e:
            logger.error(f"Error getting practitioner patients: {e}")
            return []
    
    async def set_practitioner_patients(self, practitioner_id: str, patients: List[str]) -> bool:
        """Set or update practitioner's patient list"""
        try:
            return await self.mongodb_service.set_practitioner_patients(practitioner_id, patients)
        except Exception as e:
            logger.error(f"Error setting practitioner patients: {e}")
            return False
    
    async def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """Get summary information about a patient's data"""
        try:
            # Get data summary from retrieval service
            retrieval_summary = await self.retrieval_service.get_patient_summary(patient_id)
            
            # Get context statistics
            context_stats = await self.context_service.get_context_stats(patient_id)
            
            return {
                "patient_id": patient_id,
                "data_summary": retrieval_summary,
                "context_stats": context_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting patient summary: {e}")
            return {
                "patient_id": patient_id,
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all services"""
        try:
            health_results = {}
            
            # Check each service
            health_results["mongodb"] = await self.mongodb_service.health_check()
            health_results["embedding"] = await self.embedding_service.health_check()
            health_results["retrieval"] = await self.retrieval_service.health_check()
            health_results["generation"] = await self.generation_service.health_check()
            health_results["context"] = await self.context_service.health_check()
            
            # Overall health
            health_results["overall"] = all(health_results.values())
            
            return health_results
            
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return {
                "overall": False,
                "error": str(e)
            }
    
    async def search_similar_cases(
        self,
        
        query: str,
        patient_id: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search for similar cases from other patients"""
        try:
            return await self.retrieval_service.search_similar_patients(
                query=query,
                exclude_patient_id=patient_id,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"Error searching similar cases: {e}")
            return []
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            await self.mongodb_service.close()
            logger.info("RAG orchestrator cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# State management for LangGraph-style workflow (future enhancement)
class RAGState:
    """State class for potential LangGraph integration"""
    
    def __init__(self):
        self.query: str = ""
        self.patient_id: str = ""
        self.practitioner_id: str = ""
        self.session_id: str = "default"
        self.retrieved_contexts: List[Dict] = []
        self.short_term_context: List[Dict] = []
        self.long_term_context: str = ""
        self.generated_answer: str = ""
        self.sources: List[Dict] = []
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary"""
        return {
            "query": self.query,
            "patient_id": self.patient_id,
            "practitioner_id": self.practitioner_id,
            "session_id": self.session_id,
            "retrieved_contexts": self.retrieved_contexts,
            "short_term_context": self.short_term_context,
            "long_term_context": self.long_term_context,
            "generated_answer": self.generated_answer,
            "sources": self.sources,
            "metadata": self.metadata
        }