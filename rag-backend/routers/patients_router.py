# routers/patients_router.py
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict
import config
from utils.logger import get_logger
from services.mongodb_service import MongoDBService
from dependencies import get_mongodb_service
from utils.auth import verify_firebase_token

router = APIRouter()
logger = get_logger(__name__)


def _allowed_to_list_patient_sessions(current_user: dict, requested_user_id: str) -> bool:
    """
    The app calls /patients/{patientUuid}/sessions with the FHIR patient id.
    Firebase ID token uid is usually not the same as that UUID.
    """
    token_uid = current_user.get("uid")
    if not token_uid:
        return False
    if requested_user_id == token_uid:
        return True
    claims = current_user.get("firebase_claims") or {}
    for key in (
        "patient_id",
        "patientId",
        "fhirPatientId",
        "fhir_patient_id",
        "identifierValue",
    ):
        val = claims.get(key)
        if val is not None and str(val) == str(requested_user_id):
            return True
    if config.CHAT_RELAX_PATIENT_SESSION_ACCESS:
        return True
    return False


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


@router.get("/{userId}/sessions")
async def get_user_sessions(
    userId: str,
    limit: int = 50,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        if not _allowed_to_list_patient_sessions(current_user, userId):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only list your own sessions",
            )
        raw_sessions = await mongodb.list_sessions(userId, limit=limit)
        sessions = [_normalize_session(s) for s in raw_sessions]
        return {
            "sessions": sessions,
            "totalSessions": len(sessions),
            "activeSessions": sum(1 for s in sessions if s.get("status") == "active")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@router.get("/{userId}/preferences")
async def get_preferences(
    userId: str,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        prefs = await mongodb.get_json("preferences", userId)
        return prefs or {}
    except Exception as e:
        logger.error(f"Error fetching preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch preferences")

@router.put("/{userId}/preferences")
async def update_preferences(
    userId: str,
    payload: Dict,
    mongodb: MongoDBService = Depends(get_mongodb_service),
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        await mongodb.set_json("preferences", userId, payload)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")
