# agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from agents.tools.base_tool import ToolRegistry, run_tool_calling_loop
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentResponse:
    """Structured output every specialist agent must return."""
    answer: str = ""
    warnings: List[str] = field(default_factory=list)
    clinician_triggers: List[str] = field(default_factory=list)
    evidence_references: List[Dict[str, Any]] = field(default_factory=list)
    agent_name: str = ""
    confidence: float = 0.0
    tools_called: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    citations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "warnings": self.warnings,
            "clinician_triggers": self.clinician_triggers,
            "evidence_references": self.evidence_references,
            "agent_name": self.agent_name,
            "confidence": self.confidence,
            "tools_called": self.tools_called,
            "metadata": self.metadata,
            "citations": self.citations,
        }


class BaseAgent(ABC):
    """
    Base class for all MAI specialist agents.

    Every agent receives:
      - generation_service  (shared OpenAI wrapper)
      - retrieval_service   (shared Pinecone retrieval, agents apply their own filters)

    Agents can register tools in self.registry (a ToolRegistry).
    When tools are present, _call_llm_with_tools() runs the OpenAI function-calling
    loop so the model can call tools and use their results.

    Every agent must implement `handle()` which returns an AgentResponse.
    """

    agent_id: str = "base"
    agent_display_name: str = "Base Agent"

    def __init__(self, generation_service, retrieval_service=None):
        self.generation_service = generation_service
        self.retrieval_service = retrieval_service
        self.registry = ToolRegistry()

    @abstractmethod
    async def handle(
        self,
        query: str,
        patient_id: Optional[str] = None,
        practitioner_id: Optional[str] = None,
        retrieved_contexts: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        patient_context_summary: Optional[str] = None,
    ) -> AgentResponse:
        """Process the query and return a structured AgentResponse.

        Args:
            patient_context_summary: Pre-computed patient context from
                PatientContextAgent, injected by the orchestrator so
                specialist agents can ground answers in patient data.
        """
        ...

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 800) -> str:
        """Simple LLM call without tools (backward compat)."""
        response = self.generation_service.client.chat.completions.create(
            model=self.generation_service.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    async def _call_llm_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> str:
        """LLM call that enables function-calling via the agent's tool registry."""
        return await run_tool_calling_loop(
            client=self.generation_service.client,
            model=self.generation_service.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            registry=self.registry,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _format_retrieved_context(self, contexts: List[Dict[str, Any]]) -> str:
        if not contexts:
            return "No relevant records found."
        parts = []
        for i, ctx in enumerate(contexts, 1):
            text = ctx.get("text", "")
            score = ctx.get("score", 0)
            parts.append(f"[{i}] (relevance {score:.2f}): {text.strip()}")
        return "\n".join(parts)

    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        if not messages:
            return ""
        lines = []
        for msg in messages[-5:]:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
