# agents/action_agent.py
"""
Action Agent (maiaction)

Handles actions, not just answers.
Possible actions:
  send message to clinic, book appointment, refill request,
  open lab report, create follow-up reminder, route to nurse,
  escalate critical result workflow.

Tools:
  createAppointment, sendCommunication, createTask, escalateToClinician
"""
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from agents.tools.base_tool import ToolRegistry, run_tool_calling_loop
from agents.tools.action_tools import create_action_tools
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are **MaiAction**, the Action agent of a medical AI assistant.

You handle requests that require doing something, not just answering a question.
You have tools to:
- Book/request appointments
- Send messages to the clinic or care team
- Create follow-up reminders
- Escalate urgent situations to a clinician

When to act:
- The user explicitly asks to schedule, book, request, send, remind, or escalate.
- Another agent flags a critical situation that needs escalation.

Safety rules:
- Always confirm the action with the user before executing (describe what you will do).
- For escalations, act immediately — do not wait for confirmation.
- NEVER create fake confirmations. If a tool fails, say so.

After performing an action, summarize what was done and any next steps."""


class ActionAgent(BaseAgent):
    agent_id = "maiaction"
    agent_display_name = "Action Agent"

    def __init__(self, generation_service, retrieval_service=None, mongodb_service=None):
        super().__init__(generation_service, retrieval_service)
        self.mongodb_service = mongodb_service
        tools = create_action_tools(mongodb_service) if mongodb_service else []
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
            conv_text = self._format_conversation(conversation_context or [])
            if conv_text:
                user_prompt_parts.append(f"Recent conversation:\n{conv_text}\n")
            user_prompt_parts.append(f"User request: {query}")
            user_prompt_parts.append("Use the appropriate tool(s) to handle this request.")

            raw_answer = await run_tool_calling_loop(
                client=self.generation_service.client,
                model=self.generation_service.model_name,
                system_prompt=SYSTEM_PROMPT,
                user_prompt="\n".join(user_prompt_parts),
                registry=self.registry,
                temperature=0.1,
                max_tokens=600,
            )

            return AgentResponse(
                answer=raw_answer,
                warnings=[],
                clinician_triggers=[],
                agent_name=self.agent_id,
                confidence=0.80,
            )
        except Exception as e:
            logger.error(f"ActionAgent error: {e}")
            return AgentResponse(
                answer="I was unable to complete the requested action. Please try again or contact the clinic directly.",
                agent_name=self.agent_id,
            )
