# agents/intent_classifier.py
"""
Intent classification layer for the Conversation Orchestrator.

Classifies each user query into one or more intents so the orchestrator
knows which specialist agents to invoke.

Supported intents (from the MAI doc):
  medication  – drug purpose, dosage, side effects, interactions, timing
  lab         – test meaning, prep, results, reference ranges
  procedure   – what/why, prep, duration, risks/benefits, aftercare
  education   – disease education, prevention, chronic care, lifestyle
  triage      – urgent symptoms, safety-critical, needs clinician escalation
"""
import json
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

VALID_INTENTS = {"medication", "lab", "procedure", "education", "triage", "action"}

CLASSIFICATION_SYSTEM_PROMPT = """You are an intent classifier for a medical chat assistant.

Given a user message, return a JSON object with:
- "intents": a list of one or more intents from EXACTLY this set:
    medication, lab, procedure, education, triage, action
- "needs_patient_context": boolean — true if answering requires patient-specific records
- "reasoning": one sentence explaining your classification

Rules:
- A message can have MULTIPLE intents (e.g. asking about a medicine before a lab test → ["medication", "lab"]).
- Use "triage" when the user describes urgent symptoms (chest pain, difficulty breathing, severe bleeding, suicidal thoughts, etc.) or asks whether they should go to the ER.
- Use "education" for general wellness, disease explanation, prevention, lifestyle, chronic condition info.
- Use "medication" for anything about drugs: purpose, side effects, interactions, dosage timing, refills, storage.
- Use "lab" for lab tests, lab results, fasting requirements, specimen info, reference ranges.
- Use "procedure" for medical procedures, imaging, surgeries, preparation, aftercare.
- Use "action" when the user wants to DO something: book/schedule an appointment, request a refill, send a message to their doctor/clinic, set a reminder, or escalate a concern.
- If the message is a simple greeting or not medical, return intents: ["education"] and needs_patient_context: false.
- Return ONLY valid JSON. No markdown, no extra text."""


class IntentClassifier:
    """Uses the shared LLM to classify user intent."""

    def __init__(self, generation_service):
        self.generation_service = generation_service

    async def classify(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Classify the user query.

        Returns:
            {
                "intents": ["medication", "lab"],
                "needs_patient_context": true,
                "reasoning": "..."
            }
        """
        try:
            user_prompt_parts = []
            if conversation_context:
                user_prompt_parts.append("Recent conversation:")
                for msg in conversation_context[-3:]:
                    role = msg.get("role", "unknown").capitalize()
                    content = msg.get("content", "")
                    user_prompt_parts.append(f"  {role}: {content}")
                user_prompt_parts.append("")

            user_prompt_parts.append(f'User message: "{query}"')
            user_prompt_parts.append("\nClassify this message. Return JSON only.")
            user_prompt = "\n".join(user_prompt_parts)

            response = self.generation_service.client.chat.completions.create(
                model=self.generation_service.model_name,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=200,
            )

            raw = response.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(raw)

            intents = [i for i in result.get("intents", []) if i in VALID_INTENTS]
            if not intents:
                intents = ["education"]

            return {
                "intents": intents,
                "needs_patient_context": bool(result.get("needs_patient_context", False)),
                "reasoning": result.get("reasoning", ""),
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Intent classification parse error: {e}; falling back to education")
            return {
                "intents": ["education"],
                "needs_patient_context": False,
                "reasoning": "Classification fallback due to parse error.",
            }
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return {
                "intents": ["education"],
                "needs_patient_context": False,
                "reasoning": f"Classification fallback due to error: {e}",
            }
