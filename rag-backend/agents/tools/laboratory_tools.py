# agents/tools/laboratory_tools.py
"""
Laboratory tools for the Laboratory Agent (mailab).

Tools:
  getLabCatalog         — get info about a lab test (what it measures, specimen, etc.)
  getPatientLabResults  — get recent lab results for a patient
  getReferenceRange     — get reference/normal ranges for a test
  getCriticalLabRules   — get critical value rules for a test

FHIR Resource Mapping (target state for each tool):
  getLabCatalog        → ActivityDefinition or ObservationDefinition (test catalog)
  getPatientLabResults → Observation (category=laboratory), DiagnosticReport
  getReferenceRange    → ObservationDefinition.qualifiedValue / reference-range extension
  getCriticalLabRules  → ObservationDefinition.qualifiedValue (critical range)
"""
from typing import Dict, Any, Optional
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class GetLabCatalog(BaseTool):
    name = "getLabCatalog"
    description = "Get catalog information about a lab test: what it measures, specimen type, fasting requirements, turnaround time."
    parameters = {
        "type": "object",
        "properties": {
            "testName": {"type": "string", "description": "Name or code of the lab test (e.g. HbA1c, CBC, lipid panel, TSH)"}
        },
        "required": ["testName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, testName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{testName} lab test specimen fasting preparation turnaround",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"testName": testName, "catalog_info": docs, "sources_found": len(docs)}
        except Exception as e:
            logger.error(f"getLabCatalog error: {e}")
            return {"testName": testName, "catalog_info": [], "error": str(e)}


class GetPatientLabResults(BaseTool):
    name = "getPatientLabResults"
    description = "Get recent lab results for a patient, optionally filtered by test name or date range."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"},
            "testName": {"type": "string", "description": "Optional: filter by test name (e.g. HbA1c, hemoglobin)"},
        },
        "required": ["patientId"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, patientId: str, testName: str = "", **kwargs) -> Dict[str, Any]:
        try:
            query = f"lab results {testName}" if testName else "laboratory results test values"
            result = await self.retrieval_service.retrieve_context(
                query=query,
                patient_id=patientId,
                top_k=10,
                similarity_threshold=0.4,
            )
            labs = []
            for ctx in result.get("contexts", []):
                text = ctx.get("text", "").lower()
                if any(kw in text for kw in ["result", "lab", "test", "value", "range", "mg/dl", "mmol", "g/dl", "hemoglobin", "glucose", "cholesterol"]):
                    labs.append({"text": ctx["text"], "score": ctx.get("score", 0)})
            return {"patientId": patientId, "testName": testName, "results": labs, "count": len(labs)}
        except Exception as e:
            logger.error(f"getPatientLabResults error: {e}")
            return {"patientId": patientId, "results": [], "error": str(e)}


class GetReferenceRange(BaseTool):
    name = "getReferenceRange"
    description = "Get the normal/reference range for a lab test, optionally adjusted for age and sex."
    parameters = {
        "type": "object",
        "properties": {
            "testName": {"type": "string", "description": "Name of the lab test (e.g. hemoglobin, HbA1c, TSH)"},
            "age": {"type": "integer", "description": "Optional: patient age for age-adjusted ranges"},
            "sex": {"type": "string", "description": "Optional: patient sex (male/female) for sex-adjusted ranges"},
        },
        "required": ["testName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, testName: str, age: int = None, sex: str = None, **kwargs) -> Dict[str, Any]:
        try:
            query_parts = [testName, "reference range normal values"]
            if age:
                query_parts.append(f"age {age}")
            if sex:
                query_parts.append(sex)
            result = await self.retrieval_service.retrieve_context(
                query=" ".join(query_parts),
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"testName": testName, "age": age, "sex": sex, "reference_data": docs}
        except Exception as e:
            logger.error(f"getReferenceRange error: {e}")
            return {"testName": testName, "reference_data": [], "error": str(e)}


class GetCriticalLabRules(BaseTool):
    name = "getCriticalLabRules"
    description = "Get critical/panic value thresholds for a lab test — values that require immediate clinical action."
    parameters = {
        "type": "object",
        "properties": {
            "testName": {"type": "string", "description": "Name of the lab test"}
        },
        "required": ["testName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, testName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{testName} critical value panic value threshold emergency",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"testName": testName, "critical_rules": docs}
        except Exception as e:
            logger.error(f"getCriticalLabRules error: {e}")
            return {"testName": testName, "critical_rules": [], "error": str(e)}


def create_laboratory_tools(retrieval_service):
    """Factory function to create all laboratory tools."""
    return [
        GetLabCatalog(retrieval_service),
        GetPatientLabResults(retrieval_service),
        GetReferenceRange(retrieval_service),
        GetCriticalLabRules(retrieval_service),
    ]
