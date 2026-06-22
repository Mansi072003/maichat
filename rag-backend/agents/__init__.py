# agents/__init__.py
"""MAI specialist agents package — tool-based."""

from .base_agent import BaseAgent, AgentResponse
from .intent_classifier import IntentClassifier
from .medication_agent import MedicationAgent
from .laboratory_agent import LaboratoryAgent
from .procedure_agent import ProcedureAgent
from .education_agent import EducationAgent
from .safety_agent import SafetyAgent
from .patient_context_agent import PatientContextAgent
from .action_agent import ActionAgent
from .consent import ConsentResult, check_patient_data_consent

INTENT_TO_AGENT = {
    "medication": MedicationAgent,
    "lab": LaboratoryAgent,
    "procedure": ProcedureAgent,
    "education": EducationAgent,
    "triage": SafetyAgent,
}

__all__ = [
    "BaseAgent",
    "AgentResponse",
    "IntentClassifier",
    "MedicationAgent",
    "LaboratoryAgent",
    "ProcedureAgent",
    "EducationAgent",
    "SafetyAgent",
    "PatientContextAgent",
    "ActionAgent",
    "ConsentResult",
    "check_patient_data_consent",
    "INTENT_TO_AGENT",
]
