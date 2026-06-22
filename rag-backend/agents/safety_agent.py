# agents/safety_agent.py
"""
Safety / Triage Agent (maitriage)

Two responsibilities:
1. TRIAGE — when the user describes urgent symptoms, produce an immediate
   "seek care now" response instead of (or before) other agent answers.
2. FINAL SAFETY REVIEW — after specialist agents have produced a merged
   draft, scan the draft for unsafe advice and redact / flag it.
"""
import json
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent, AgentResponse
from utils.logger import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------- #
#  Triage — first-pass handling of urgent symptom questions              #
# --------------------------------------------------------------------- #
TRIAGE_SYSTEM_PROMPT = """You are **MaiTriage**, the Safety and Triage agent of a medical AI assistant.

You are invoked when the user's message may describe an urgent or emergency situation.

Your ONLY job is to decide urgency and respond safely:

1. **Emergency** — symptoms like chest pain, difficulty breathing, severe bleeding,
   stroke signs (face drooping, arm weakness, speech difficulty), loss of consciousness,
   suicidal or self-harm thoughts.
   → Tell the user to call emergency services (911 / local equivalent) or go to the
     nearest emergency room IMMEDIATELY. Do NOT attempt to diagnose.

2. **Urgent but not emergency** — symptoms that need prompt medical attention within hours
   (e.g. high fever >103 °F, worsening pain, signs of infection, allergic reaction without
   anaphylaxis).
   → Advise the user to contact their healthcare provider or visit urgent care TODAY.

3. **Not urgent** — the message is not actually a triage situation (misclassified).
   → Return a short note that no urgent concern was detected.

Always err on the side of caution. Never reassure a potentially dangerous symptom away.

Output as JSON:
{
  "urgency": "emergency" | "urgent" | "not_urgent",
  "message": "<your plain-language guidance to the user>",
  "warnings": ["<critical warnings>"]
}"""


class SafetyAgent(BaseAgent):
    agent_id = "maitriage"
    agent_display_name = "Safety / Triage Agent"

    # ---- Triage (called when intent includes "triage") ---- #

    async def handle(
        self,
        query: str,
        patient_id: Optional[str] = None,
        practitioner_id: Optional[str] = None,
        retrieved_contexts: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        patient_context_summary: Optional[str] = None,
    ) -> AgentResponse:
        """Handle triage intent — assess urgency of user message.

        The returned AgentResponse.metadata["urgency"] is one of
        "emergency", "urgent", or "not_urgent" so the orchestrator can
        decide whether to short-circuit.
        """
        try:
            raw = self._call_llm(TRIAGE_SYSTEM_PROMPT, f"User message: {query}", temperature=0.0)
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(raw)

            urgency = result.get("urgency", "not_urgent")
            message = result.get("message", "")
            warnings = result.get("warnings", [])

            clinician_triggers = []
            if urgency == "emergency":
                clinician_triggers.append("EMERGENCY: Call 911 or go to nearest ER immediately.")
            elif urgency == "urgent":
                clinician_triggers.append("Contact your healthcare provider or visit urgent care today.")

            return AgentResponse(
                answer=message,
                warnings=warnings,
                clinician_triggers=clinician_triggers,
                agent_name=self.agent_id,
                confidence=0.95 if urgency != "not_urgent" else 0.5,
                metadata={"urgency": urgency},
            )
        except Exception as e:
            logger.error(f"SafetyAgent triage error: {e}")
            return AgentResponse(
                answer="If you are experiencing a medical emergency, please call 911 or go to the nearest emergency room.",
                warnings=["Unable to fully assess urgency — please err on the side of caution."],
                clinician_triggers=["Seek medical attention if you feel your symptoms are serious."],
                agent_name=self.agent_id,
                metadata={"urgency": "emergency"},
            )

    # ---- Final safety review (called on merged draft) ---- #

    async def review_merged_answer(self, merged_answer: str, original_query: str) -> Dict[str, Any]:
        """
        Post-merge safety scan. Returns the (possibly redacted) answer
        and any safety flags.
        """
        review_prompt = f"""Review the following draft answer for a medical chat assistant.

Original user question: "{original_query}"

Draft answer:
\"\"\"
{merged_answer}
\"\"\"

Check for:
1. Does it prescribe medication or change dosage? (not allowed)
2. Does it diagnose a condition definitively? (not allowed — should say "may suggest")
3. Does it dismiss potentially serious symptoms? (not allowed)
4. Does it contain factual medical inaccuracies you can detect?

Return JSON:
{{
  "safe": true/false,
  "issues": ["list of issues found, or empty"],
  "revised_answer": "<if safe is false, provide a corrected version; if safe is true, repeat the draft as-is>"
}}"""

        try:
            raw = self._call_llm(
                "You are a medical safety reviewer. Return ONLY valid JSON.",
                review_prompt,
                temperature=0.0,
                max_tokens=1200,
            )
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(raw)

            return {
                "safe": bool(result.get("safe", True)),
                "issues": result.get("issues", []),
                "revised_answer": result.get("revised_answer", merged_answer),
            }
        except Exception as e:
            logger.warning(f"Safety review parse error: {e}; passing through original answer")
            return {
                "safe": True,
                "issues": [],
                "revised_answer": merged_answer,
            }
