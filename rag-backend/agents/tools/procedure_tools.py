# agents/tools/procedure_tools.py
"""
Procedure tools for the Procedure Agent (maiproc).

Tools:
  getProcedureInfo             — what the procedure is, why it is done
  getPreparationInstructions   — how to prepare (fasting, meds to hold, etc.)
  getPostProcedureInstructions — aftercare and recovery expectations

FHIR Resource Mapping (target state for each tool):
  getProcedureInfo             → Procedure (code, reasonCode, performedPeriod) +
                                  PlanDefinition (protocol-level info)
  getPreparationInstructions   → ServiceRequest (orderDetail, note) +
                                  CarePlan (pre-procedure activity)
  getPostProcedureInstructions → CarePlan (post-procedure activity) +
                                  Procedure.followUp
"""
from typing import Dict, Any
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class GetProcedureInfo(BaseTool):
    name = "getProcedureInfo"
    description = "Get information about a medical procedure: what it is, why it is done, duration, risks and benefits at educational level."
    parameters = {
        "type": "object",
        "properties": {
            "procedureName": {"type": "string", "description": "Name of the procedure (e.g. MRI, endoscopy, colonoscopy, ultrasound abdomen)"}
        },
        "required": ["procedureName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, procedureName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{procedureName} procedure what is it why done duration risks benefits",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"procedureName": procedureName, "info": docs, "sources_found": len(docs)}
        except Exception as e:
            logger.error(f"getProcedureInfo error: {e}")
            return {"procedureName": procedureName, "info": [], "error": str(e)}


class GetPreparationInstructions(BaseTool):
    name = "getPreparationInstructions"
    description = "Get preparation instructions for a procedure: fasting, medications to hold, what to bring, what to wear."
    parameters = {
        "type": "object",
        "properties": {
            "procedureName": {"type": "string", "description": "Name of the procedure"}
        },
        "required": ["procedureName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, procedureName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{procedureName} preparation instructions fasting before procedure what to do",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"procedureName": procedureName, "preparation": docs}
        except Exception as e:
            logger.error(f"getPreparationInstructions error: {e}")
            return {"procedureName": procedureName, "preparation": [], "error": str(e)}


class GetPostProcedureInstructions(BaseTool):
    name = "getPostProcedureInstructions"
    description = "Get post-procedure care instructions: aftercare, recovery, what to expect, warning signs."
    parameters = {
        "type": "object",
        "properties": {
            "procedureName": {"type": "string", "description": "Name of the procedure"}
        },
        "required": ["procedureName"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, procedureName: str, **kwargs) -> Dict[str, Any]:
        try:
            result = await self.retrieval_service.retrieve_context(
                query=f"{procedureName} aftercare recovery post procedure instructions warning signs",
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            docs = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {"procedureName": procedureName, "aftercare": docs}
        except Exception as e:
            logger.error(f"getPostProcedureInstructions error: {e}")
            return {"procedureName": procedureName, "aftercare": [], "error": str(e)}


def create_procedure_tools(retrieval_service):
    """Factory function to create all procedure tools."""
    return [
        GetProcedureInfo(retrieval_service),
        GetPreparationInstructions(retrieval_service),
        GetPostProcedureInstructions(retrieval_service),
    ]
