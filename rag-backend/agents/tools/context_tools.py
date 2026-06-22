# agents/tools/context_tools.py
"""
Patient Context tools for the Patient Context Agent.

Tools:
  getPatientSummary — overview of all data available for a patient
  getConditions     — active conditions / diagnoses
  getAllergies      — known allergies and intolerances

FHIR Resource Mapping (target state for each tool):
  getPatientSummary → Patient + Condition + MedicationRequest + Observation
                      + Encounter + CarePlan (bundle / $everything operation)
  getConditions     → Condition (clinicalStatus=active)
  getAllergies      → AllergyIntolerance (clinicalStatus=active)
"""
from typing import Dict, Any
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class GetPatientSummary(BaseTool):
    name = "getPatientSummary"
    description = "Get a summary overview of a patient: demographics, conditions, medications, recent labs, encounters."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"}
        },
        "required": ["patientId"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, patientId: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query="patient summary demographics conditions medications labs encounters care plan",
                patient_id=patientId,
                top_k=15,
                similarity_threshold=0.3,
            )
            records = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            stat = await self.retrieval_service.get_patient_summary(patientId)
            return {
                "patientId": patientId,
                "records": records,
                "total_records_in_store": stat.get("total_records", 0),
                "record_types": stat.get("record_types", {}),
            }
        except Exception as e:
            logger.error(f"getPatientSummary error: {e}")
            return {"patientId": patientId, "records": [], "error": str(e)}


class GetConditions(BaseTool):
    name = "getConditions"
    description = "Get active conditions and diagnoses for a patient (e.g. diabetes, hypertension, asthma)."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"}
        },
        "required": ["patientId"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, patientId: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query="conditions diagnoses active problems chronic disease",
                patient_id=patientId,
                top_k=10,
                similarity_threshold=0.4,
            )
            conditions = []
            for ctx in result.get("contexts", []):
                text = ctx.get("text", "").lower()
                if any(kw in text for kw in ["condition", "diagnos", "disease", "disorder", "syndrome", "diabetes", "hypertension", "asthma"]):
                    conditions.append({"text": ctx["text"], "score": ctx.get("score", 0)})
            return {"patientId": patientId, "conditions": conditions, "count": len(conditions)}
        except Exception as e:
            logger.error(f"getConditions error: {e}")
            return {"patientId": patientId, "conditions": [], "error": str(e)}


class GetAllergies(BaseTool):
    name = "getAllergies"
    description = "Get known allergies and intolerances for a patient."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"}
        },
        "required": ["patientId"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, patientId: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query="allergies allergy intolerance adverse reaction drug food",
                patient_id=patientId,
                top_k=10,
                similarity_threshold=0.4,
            )
            allergies = []
            for ctx in result.get("contexts", []):
                text = ctx.get("text", "").lower()
                if any(kw in text for kw in ["allerg", "intolerance", "adverse", "reaction", "anaphylaxis", "sensitivity"]):
                    allergies.append({"text": ctx["text"], "score": ctx.get("score", 0)})
            return {"patientId": patientId, "allergies": allergies, "count": len(allergies)}
        except Exception as e:
            logger.error(f"getAllergies error: {e}")
            return {"patientId": patientId, "allergies": [], "error": str(e)}


def create_context_tools(retrieval_service):
    """Factory function to create all patient context tools."""
    return [
        GetPatientSummary(retrieval_service),
        GetConditions(retrieval_service),
        GetAllergies(retrieval_service),
    ]
