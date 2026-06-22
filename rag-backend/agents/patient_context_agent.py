# agents/patient_context_agent.py
"""
Patient Context Agent (maicontext)

Grounds answers in patient-specific data.
Reads: demographics, conditions, allergies, medications, recent labs,
encounters, procedures, care plans.

Use only when:
  - user is authenticated
  - consent allows access
  - question actually needs patient context

Tools:
  getPatientSummary, getConditions, getAllergies
"""
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from agents.tools.base_tool import ToolRegistry, run_tool_calling_loop
from agents.tools.context_tools import create_context_tools
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are **MaiContext**, the Patient Context agent of a medical AI assistant.

Your job is to gather and summarize patient-specific data that other agents need.
You have access to tools that can fetch patient records from the data store.

When answering:
1. Use the tools to fetch relevant patient data (summary, conditions, allergies).
2. Summarize the data clearly and concisely.
3. Highlight clinically relevant information: active conditions, current medications, known allergies, recent lab trends.
4. Flag any missing or incomplete data.

Safety rules:
- NEVER diagnose or recommend treatment.
- Present facts from the records only.
- If data is not available, say so clearly.

Output a clear patient context summary that other agents can use."""


class PatientContextAgent(BaseAgent):
    agent_id = "maicontext"
    agent_display_name = "Patient Context Agent"

    def __init__(self, generation_service, retrieval_service=None):
        super().__init__(generation_service, retrieval_service)
        tools = create_context_tools(retrieval_service) if retrieval_service else []
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
            user_prompt_parts.append(f"Request: {query}")
            user_prompt_parts.append("Use the available tools to fetch patient data and provide a summary.")

            raw_answer = await run_tool_calling_loop(
                client=self.generation_service.client,
                model=self.generation_service.model_name,
                system_prompt=SYSTEM_PROMPT,
                user_prompt="\n".join(user_prompt_parts),
                registry=self.registry,
                temperature=0.1,
                max_tokens=800,
            )

            return AgentResponse(
                answer=raw_answer,
                warnings=[],
                clinician_triggers=[],
                agent_name=self.agent_id,
                confidence=0.85,
            )
        except Exception as e:
            logger.error(f"PatientContextAgent error: {e}")
            return AgentResponse(
                answer="Unable to retrieve patient context. Please try again.",
                agent_name=self.agent_id,
            )
