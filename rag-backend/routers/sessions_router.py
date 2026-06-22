# routers/sessions_router.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from services.mongodb_service import MongoDBService
from dependencies import get_mongodb_service
from utils.logger import get_logger
from utils.auth import verify_firebase_token

logger = get_logger(__name__)
router = APIRouter()


def _sender_type_to_role(sender_type: str) -> str:
    """Map stored sender_type to a role the frontend can use directly."""
    st = (sender_type or "").lower()
    if st in ("patient", "user"):
        return "user"
    return "assistant"


def _normalize_message(msg: dict) -> dict:
    """Convert a raw MongoDB message doc into a clean JSON response with role."""
    return {
        "message_id": str(msg.get("message_id", "")),
        "session_id": str(msg.get("session_id", "")),
        "role": _sender_type_to_role(msg.get("sender_type", "")),
        "sender_type": str(msg.get("sender_type", "")),
        "content": str(msg.get("content", "")),
        "timestamp": str(msg.get("timestamp", "")),
    }

@router.get("/active", summary="Get or create the active session for a user")
async def get_active_session(
    userId: str,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        session = await mongodb.get_active_session(userId)
        return {
            "sessionId": session.get("session_id"),
            "userId": session.get("userId"),
            "sessionType": session.get("session_type"),
            "status": session.get("status"),
            "createdAt": session.get("created_at"),
            "updatedAt": session.get("updated_at"),
        }
    except Exception as e:
        logger.error(f"Error getting active session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active session")

@router.post("/", summary="Create chat session")
async def create_session(
    payload: dict,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        # Accept userId or user_id in incoming API
        user_id = payload.get("userId") or payload.get("user_id")
        session_type = payload.get("sessionType") or payload.get("session_type") or "ai"
        
        # Internal services still use patient_id, but transforms response to userId
        session = await mongodb.create_session(patient_id=user_id, session_type=session_type)
        
        # MongoDB service already transforms patient_id -> userId
        return {
            "sessionId": session.get("session_id"),
            "userId": session.get("userId"),
            "sessionType": session.get("session_type"),
            "status": session.get("status"),
            "createdAt": session.get("created_at"),
            "updatedAt": session.get("updated_at"),
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.get("/{sessionId}/history")
async def get_session_history(
    sessionId: str,
    limit: int = 200,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        session = await mongodb.get_session(sessionId)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        user_id = session.get("userId")
        raw_messages = await mongodb.get_chat_history(user_id, sessionId, limit=limit)
        total = await mongodb.get_chat_message_count(user_id, sessionId)

        messages = [_normalize_message(m) for m in raw_messages]
        last = messages[-1]["timestamp"] if messages else None
        
        return {
            "sessionId": sessionId,
            "userId": user_id,
            "messages": messages,
            "totalMessages": total,
            "lastMessageTime": last
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")

def _normalize_session(s: dict) -> dict:
    """Convert a raw MongoDB session doc into a clean camelCase JSON response."""
    return {
        "sessionId": str(s.get("session_id", "")),
        "userId": str(s.get("userId", "")),
        "sessionType": str(s.get("session_type", "")),
        "status": str(s.get("status", "")),
        "createdAt": str(s.get("created_at", "")),
        "updatedAt": str(s.get("updated_at", "")),
    }

@router.put("/{sessionId}")
async def update_session(
    sessionId: str,
    payload: dict,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        updated = await mongodb.update_session(sessionId, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="Session not found or update failed")
        return _normalize_session(updated)
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session")

@router.post("/{sessionId}/end")
async def end_session(
    sessionId: str,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        ended = await mongodb.end_session(sessionId)
        if not ended:
            raise HTTPException(status_code=404, detail="Session not found")
        return _normalize_session(ended)
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")

@router.get("/{sessionId}/attachments")
async def get_session_attachments(
    sessionId: str,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        session = await mongodb.get_session(sessionId)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        user_id = session.get("userId")
        attachments = await mongodb.get_session_attachments(user_id, sessionId)
        return {"sessionId": sessionId, "attachments": attachments}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session attachments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attachments")