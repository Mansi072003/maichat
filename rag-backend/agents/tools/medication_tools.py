# agents/tools/medication_tools.py
"""
Medication tools for the Medication Agent (maimed).

Tools:
  getActiveMedications  — list current medications for a patient
  checkDrugInteraction  — check interaction between two drugs
  getMedicationMonograph— get drug info (purpose, dosage, side effects)
  getDispenseHistory    — get dispensing / refill history

FHIR Resource Mapping (target state for each tool):
  getActiveMedications  → MedicationRequest (status=active)
  checkDrugInteraction  → MedicationRequest (cross-reference two MedicationRequests
                           against a drug-interaction knowledge-base or CDS Hooks)
  getMedicationMonograph→ Medication (code, form, ingredient) + external monograph DB
  getDispenseHistory    → MedicationDispense (whenHandedOver, quantity)
"""
from typing import Dict, Any
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class GetActiveMedications(BaseTool):
    name = "getActiveMedications"
    description = "Get the list of active/current medications for a patient. Returns medication names, dosages, frequency, and prescribing info."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {
                "type": "string",
                "description": "The patient identifier (e.g. patient-101)"
            }
        },
        "required": ["patientId"]
    }

    def __init__(self, retrieval_service, mongodb_service):
        self.retrieval_service = retrieval_service
        self.mongodb_service = mongodb_service

    async def execute(self, patientId: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query="current active medications prescribed drugs",
                patient_id=patientId,
                top_k=10,
                similarity_threshold=0.5,
            )
            meds = []
            for ctx in result.get("contexts", []):
                text = ctx.get("text", "").lower()
                if any(kw in text for kw in ["medication", "prescri", "drug", "dose", "mg", "tablet", "capsule", "metformin", "aspirin", "insulin"]):
                    meds.append({"text": ctx["text"], "score": ctx.get("score", 0)})
            return {"patientId": patientId, "medications": meds, "count": len(meds)}
        except Exception as e:
            logger.error(f"getActiveMedications error: {e}")
            return {"patientId": patientId, "medications": [], "error": str(e)}


class CheckDrugInteraction(BaseTool):
    name = "checkDrugInteraction"
    description = "Check for known interactions between two drugs. Returns severity and description of the interaction."
    parameters = {
        "type": "object",
        "properties": {
            "drugA": {"type": "string", "description": "First drug name"},
            "drugB": {"type": "string", "description": "Second drug name"}
        },
        "required": ["drugA", "drugB"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, drugA: str, drugB: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"drug interaction between {drugA} and {drugB}",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            interactions = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {
                "drugA": drugA,
                "drugB": drugB,
                "interactions_found": len(interactions) > 0,
                "interactions": interactions,
                "note": "Verify with a pharmacist for clinical decision-making."
            }
        except Exception as e:
            logger.error(f"checkDrugInteraction error: {e}")
            return {"drugA": drugA, "drugB": drugB, "interactions_found": False, "error": str(e)}


class GetMedicationMonograph(BaseTool):
    name = "getMedicationMonograph"
    description = "Get monograph information for a medication: purpose, mechanism, common side effects, dosage forms, storage."
    parameters = {
        "type": "object",
        "properties": {
            "drugName": {"type": "string", "description": "Name of the medication (e.g. metformin, lisinopril)"}
        },
        "required": ["drugName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, drugName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{drugName} medication purpose side effects dosage mechanism",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"drugName": drugName, "monograph_data": docs, "sources_found": len(docs)}
        except Exception as e:
            logger.error(f"getMedicationMonograph error: {e}")
            return {"drugName": drugName, "monograph_data": [], "error": str(e)}


class GetDispenseHistory(BaseTool):
    name = "getDispenseHistory"
    description = "Get medication dispensing and refill history for a patient."
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
                query="medication dispensing refill history pharmacy",
                patient_id=patientId,
                top_k=10,
                similarity_threshold=0.4,
            )
            records = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"patientId": patientId, "dispense_records": records, "count": len(records)}
        except Exception as e:
            logger.error(f"getDispenseHistory error: {e}")
            return {"patientId": patientId, "dispense_records": [], "error": str(e)}


def create_medication_tools(retrieval_service, mongodb_service):
    """Factory function to create all medication tools with injected services."""
    return [
        GetActiveMedications(retrieval_service, mongodb_service),
        CheckDrugInteraction(retrieval_service),
        GetMedicationMonograph(retrieval_service),
        GetDispenseHistory(retrieval_service),
    ]
