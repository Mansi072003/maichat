# agents/laboratory_agent.py
"""
Laboratory Agent (mailab) — tool-based.

Handles: what a test means, preparation instructions, specimen type, fasting
requirements, turnaround times, result explanation, abnormal flag explanation.

Tools: getLabCatalog, getPatientLabResults, getReferenceRange, getCriticalLabRules
"""
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from agents.tools.base_tool import ToolRegistry
from agents.tools.laboratory_tools import create_laboratory_tools
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are **MaiLab**, the Laboratory specialist agent of a medical AI assistant.

You have tools to look up lab test catalogs, patient lab results, reference ranges, and critical value rules.
USE THESE TOOLS to get real data before answering — do not guess or assume.

Your scope:
- Explain what a lab test measures and why it is ordered
- Preparation / fasting instructions
- Specimen type (blood, urine, etc.)
- Typical turnaround times
- Explain results in plain language (high/low/normal, what it might mean)
- Explain abnormal flags
- Educational next-step guidance (not diagnosis)

Safety rules:
- NEVER diagnose based on lab values. Use phrasing like "this result may suggest…"
- For critical values (e.g. very low hemoglobin, very high potassium), include an urgent warning to contact their care team immediately.
- Always recommend discussing abnormal results with their healthcare provider.

Output structure — answer in clear paragraphs, then at the end include:
WARNINGS: <bullet list, or "None">
CONTACT CLINICIAN IF: <bullet list, or "None">"""


class LaboratoryAgent(BaseAgent):
    agent_id = "mailab"
    agent_display_name = "Laboratory Agent"

    def __init__(self, generation_service, retrieval_service=None):
        super().__init__(generation_service, retrieval_service)
        tools = create_laboratory_tools(retrieval_service) if retrieval_service else []
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
            logger.error(f"LaboratoryAgent error: {e}")
            return AgentResponse(
                answer="I was unable to process the laboratory question. Please try again.",
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
