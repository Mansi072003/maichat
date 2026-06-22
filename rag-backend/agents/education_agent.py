# agents/education_agent.py
"""
Education Agent (maied) — tool-based.

Handles: disease education, preventive care, chronic condition support,
lifestyle guidance, FAQs, patient-friendly explanations.

Tools: searchEducationArticles
"""
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from agents.tools.base_tool import ToolRegistry
from agents.tools.education_tools import create_education_tools
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are **MaiEd**, the Education specialist agent of a medical AI assistant.

You have a tool to search curated health education articles.
USE THIS TOOL to find relevant educational content before answering when appropriate.

Your scope:
- Disease and condition education in plain language
- Preventive care guidance
- Chronic condition management support
- Lifestyle and wellness advice (diet, exercise, sleep)
- Frequently asked health questions
- Patient-friendly explanations of medical concepts

Safety rules:
- Provide general educational information only — NEVER diagnose or prescribe.
- If the user's question suggests an urgent health concern, note that they should contact their healthcare provider.
- Use language appropriate for a general audience (aim for 6th-8th grade reading level).

Output structure — answer in clear, easy-to-read paragraphs with headings where helpful.
At the end include:
LEARN MORE: <1-2 follow-up topics the user might find helpful, or "None">
CONTACT CLINICIAN IF: <bullet list of situations, or "None">"""


class EducationAgent(BaseAgent):
    agent_id = "maied"
    agent_display_name = "Education Agent"

    def __init__(self, generation_service, retrieval_service=None):
        super().__init__(generation_service, retrieval_service)
        tools = create_education_tools(retrieval_service) if retrieval_service else []
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
            if patient_context_summary:
                user_prompt_parts.append(f"Patient context (from records):\n{patient_context_summary}\n")
            conv_text = self._format_conversation(conversation_context or [])
            if conv_text:
                user_prompt_parts.append(f"Recent conversation:\n{conv_text}\n")
            if retrieved_contexts:
                user_prompt_parts.append(f"Relevant knowledge:\n{self._format_retrieved_context(retrieved_contexts)}\n")
            user_prompt_parts.append(f"User question: {query}")
            user_prompt_parts.append("Use your tools if you need additional educational content, then answer.")

            raw_answer = await self._call_llm_with_tools(
                SYSTEM_PROMPT, "\n".join(user_prompt_parts)
            )

            clinician_triggers = _parse_clinician_triggers(raw_answer)
            tools_used = [t.name for t in self.registry.tool_list]

            return AgentResponse(
                answer=raw_answer,
                warnings=[],
                clinician_triggers=clinician_triggers,
                evidence_references=[
                    {"text": c.get("text", "")[:150], "score": c.get("score", 0)}
                    for c in (retrieved_contexts or [])[:3]
                ],
                agent_name=self.agent_id,
                confidence=0.80,
                tools_called=tools_used,
            )
        except Exception as e:
            logger.error(f"EducationAgent error: {e}")
            return AgentResponse(
                answer="I was unable to process the education question. Please try again.",
                agent_name=self.agent_id,
            )


def _parse_clinician_triggers(text: str) -> List[str]:
    triggers = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip().lstrip("- •")
        upper = line.upper().strip()
        if upper.startswith("CONTACT CLINICIAN IF:"):
            in_section = True
            content = stripped.split(":", 1)[-1].strip()
            if content.lower() not in ("", "none"):
                triggers.append(content)
        elif in_section:
            if stripped and stripped.lower() != "none" and not upper.startswith("LEARN MORE"):
                triggers.append(stripped)
            if upper.startswith("LEARN MORE"):
                break
    return triggers
