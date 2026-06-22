# agents/procedure_agent.py
"""
Procedure Agent (maiproc) — tool-based.

Handles: what the procedure is, why it is done, preparation, expected duration,
risks / benefits at educational level, aftercare instructions, recovery expectations.

Tools: getProcedureInfo, getPreparationInstructions, getPostProcedureInstructions
"""
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from agents.tools.base_tool import ToolRegistry
from agents.tools.procedure_tools import create_procedure_tools
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are **MaiProc**, the Procedure specialist agent of a medical AI assistant.

You have tools to look up procedure information, preparation instructions, and aftercare guidelines.
USE THESE TOOLS to get real data before answering — do not guess or assume.

Your scope:
- Explain what a medical procedure is and why it is performed
- Preparation instructions (fasting, medications to hold, what to bring)
- Expected duration
- Risks and benefits at an *educational* level (not consent-level detail)
- Aftercare and recovery expectations
- Do's and Don'ts before and after the procedure

Safety rules:
- NEVER guarantee outcomes.
- If the user describes post-procedure emergency symptoms (e.g. uncontrolled bleeding, severe pain, high fever), add a triage warning to seek immediate care.
- Always recommend confirming preparation steps with their care team.

Output structure — answer in clear paragraphs, then at the end include:
WARNINGS: <bullet list, or "None">
CONTACT CLINICIAN IF: <bullet list, or "None">"""


class ProcedureAgent(BaseAgent):
    agent_id = "maiproc"
    agent_display_name = "Procedure Agent"

    def __init__(self, generation_service, retrieval_service=None):
        super().__init__(generation_service, retrieval_service)
        tools = create_procedure_tools(retrieval_service) if retrieval_service else []
        self.registry = ToolRegistry(tools)

    async def handle(
        self,
        query: str,
        patient_id: Optional[str] = None,
        practitioner_id: Optional[str] = None,
        retrieved_contexts: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        patient_context_summary: Optional[str] = None,
    ) -> AgentResponse:
        try:
            user_prompt_parts = []
            if patient_id:
                user_prompt_parts.append(f"Patient ID: {patient_id}")
            if patient_context_summary:
                user_prompt_parts.append(f"Patient context (from records):\n{patient_context_summary}\n")
            conv_text = self._format_conversation(conversation_context or [])
            if conv_text:
                user_prompt_parts.append(f"Recent conversation:\n{conv_text}\n")
            if retrieved_contexts:
                user_prompt_parts.append(f"Pre-retrieved records:\n{self._format_retrieved_context(retrieved_contexts)}\n")
            user_prompt_parts.append(f"User question: {query}")
            user_prompt_parts.append("Use your tools to get any additional data you need, then answer.")

            raw_answer = await self._call_llm_with_tools(
                SYSTEM_PROMPT, "\n".join(user_prompt_parts)
            )

            warnings, clinician_triggers = _parse_structured_tail(raw_answer)
            tools_used = [t.name for t in self.registry.tool_list]

            return AgentResponse(
                answer=raw_answer,
                warnings=warnings,
                clinician_triggers=clinician_triggers,
                evidence_references=[
                    {"text": c.get("text", "")[:150], "score": c.get("score", 0)}
                    for c in (retrieved_contexts or [])[:3]
                ],
                agent_name=self.agent_id,
                confidence=0.85,
                tools_called=tools_used,
            )
        except Exception as e:
            logger.error(f"ProcedureAgent error: {e}")
            return AgentResponse(
                answer="I was unable to process the procedure question. Please try again.",
                agent_name=self.agent_id,
            )


def _parse_structured_tail(text: str):
    warnings, triggers = [], []
    in_warnings, in_triggers = False, False
    for line in text.splitlines():
        stripped = line.strip().lstrip("- •")
        upper = line.upper().strip()
        if upper.startswith("WARNINGS:"):
            in_warnings, in_triggers = True, False
            content = stripped.split(":", 1)[-1].strip()
            if content.lower() not in ("", "none"):
                warnings.append(content)
        elif upper.startswith("CONTACT CLINICIAN IF:"):
            in_warnings, in_triggers = False, True
            content = stripped.split(":", 1)[-1].strip()
            if content.lower() not in ("", "none"):
                triggers.append(content)
        elif in_warnings and stripped and stripped.lower() != "none":
            warnings.append(stripped)
        elif in_triggers and stripped and stripped.lower() != "none":
            triggers.append(stripped)
    return warnings, triggers
