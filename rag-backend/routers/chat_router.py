# routers/chat_router.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from utils.logger import get_logger
from pipeline.conversation_orchestrator import ConversationOrchestrator
from dependencies import get_conversation_orchestrator
from utils.auth import verify_firebase_token

router = APIRouter()
logger = get_logger(__name__)

@router.post("/suggestions")
async def get_suggestions(
    payload: Dict,
    orchestrator: ConversationOrchestrator = Depends(get_conversation_orchestrator),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        context = payload.get("context")
        suggestions = []
        if context:
            suggestions = [
                "Schedule an appointment",
                "Ask about medications",
                "Request lab interpretation"
            ]
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get suggestions")

@router.post("/stream")
async def stream_chat(
    payload: Dict,
    orchestrator: ConversationOrchestrator = Depends(get_conversation_orchestrator),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        query = payload.get("query") or payload.get("q") or ""
        patient_id = payload.get("patientId") or payload.get("patient_id")
        session_id = payload.get("sessionId") or payload.get("session_id")
        if not query:
            raise HTTPException(status_code=400, detail="Query required")
        resp = await orchestrator.process_query(query=query, patient_id=patient_id, session_id=session_id)
        return {"answer": resp.get("answer"), "metadata": resp.get("metadata", {})}
    except Exception as e:
        logger.error(f"Error in stream endpoint: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream response")
