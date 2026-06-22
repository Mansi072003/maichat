# services/context_service.py
import json
from typing import List, Dict, Any, Optional, Tuple
from services.mongodb_service import MongoDBService
from services.generation_service import GenerationService
from utils.logger import get_logger
import config
import time

logger = get_logger(__name__)


def _sender_type_to_prompt_role(sender_type: Optional[str]) -> str:
    """Map stored sender_type (patient/bot) to user/assistant for prompts and summarization."""
    s = (sender_type or "").lower()
    if s in ("bot", "assistant", "ai", "system"):
        return "assistant"
    if s in ("patient", "user", "provider"):
        return "user"
    return "user"


class ContextService:
    """Service for managing chat context and history with MongoDB storage"""

    def __init__(self, mongodb_service: MongoDBService, generation_service: GenerationService):
        self.mongodb_service = mongodb_service
        self.generation_service = generation_service
        self.max_short_term = config.MAX_SHORT_TERM_MESSAGES
        self.messages_to_summarize = config.MESSAGES_TO_SUMMARIZE

    async def initialize(self):
        """Initialize the context service"""
        logger.info("Context service initialized")

    async def create_session_for_patient(
        self,
        patient_id: str,
        session_type: str = "ai",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new session associated with a patient (or return existing)"""
        session = await self.mongodb_service.create_session(
            patient_id=patient_id,
            session_type=session_type,
            session_id=session_id,
            metadata=metadata
        )
        return session

    async def add_message(
        self,
        patient_id: str,
        role: str,
        content: str,
        session_id: str = "default",
        sender_id: Optional[str] = None,
        sender_type: Optional[str] = None,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to the chat history.
        Persists sender_type as patient | bot | provider. Defaults: user role -> patient, assistant -> bot.
        """
        try:
            if role == "assistant":
                effective_sender_type = sender_type or "bot"
            else:
                effective_sender_type = sender_type or "patient"

            # Ensure session exists (upsert session record)
            await self.mongodb_service.create_session(patient_id=patient_id, session_id=session_id)

            # Add message to MongoDB with richer schema
            saved = await self.mongodb_service.add_chat_message(
                patient_id=patient_id,
                session_id=session_id,
                sender_id=sender_id,
                sender_type=effective_sender_type,
                content=content,
                message_type=message_type,
                metadata=metadata
            )

            # Check if we need to summarize old messages
            await self._check_and_summarize(patient_id, session_id)

            logger.debug(f"Added {role} message for {patient_id} in session {session_id}")
            return saved

        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise

    async def get_short_term_context(
        self,
        patient_id: str,
        session_id: str = "default",
        limit: int = None
    ) -> List[Dict[str, str]]:
        limit = limit or self.max_short_term
        try:
            messages = await self.mongodb_service.get_chat_history(
                patient_id=patient_id,
                session_id=session_id,
                limit=limit
            )
            logger.debug(f"Retrieved {len(messages)} short-term messages for {patient_id}")
            converted = [
                {
                    "role": _sender_type_to_prompt_role(m.get("sender_type")),
                    "content": m.get("content", ""),
                }
                for m in messages
            ]
            return converted
        except Exception as e:
            logger.error(f"Error getting short-term context: {e}")
            return []

    async def get_long_term_context(self, patient_id: str, session_id: str = "default") -> str:
        try:
            summary = await self.mongodb_service.get_chat_summary(patient_id, session_id)
            if summary:
                logger.debug(f"Retrieved long-term context for {patient_id}")
                return summary
            return ""
        except Exception as e:
            logger.error(f"Error getting long-term context: {e}")
            return ""

    async def _check_and_summarize(self, patient_id: str, session_id: str = "default") -> None:
        try:
            message_count = await self.mongodb_service.get_chat_message_count(patient_id, session_id)
            if message_count >= self.max_short_term:
                logger.info(f"Summarizing old messages for patient {patient_id}")
                all_messages = await self.mongodb_service.get_chat_history(patient_id, session_id, limit=message_count)
                messages_to_summarize = all_messages[: self.messages_to_summarize]
                if messages_to_summarize:
                    existing_summary = await self.get_long_term_context(patient_id, session_id)
                    # prepare messages for summarization (list of dicts with role & content)
                    msgs = [
                        {
                            "role": _sender_type_to_prompt_role(m.get("sender_type")),
                            "content": m.get("content", ""),
                        }
                        for m in messages_to_summarize
                    ]
                    new_summary = await self.generation_service.summarize_conversation(msgs, existing_summary)
                    await self.mongodb_service.set_chat_summary(patient_id, session_id, new_summary)
                    logger.info(f"Summarized {len(messages_to_summarize)} messages for patient {patient_id}")
        except Exception as e:
            logger.error(f"Error during summarization check: {e}")

    async def get_full_context(self, patient_id: str, session_id: str = "default") -> Tuple[List[Dict[str, str]], str]:
        try:
            short_term = await self.get_short_term_context(patient_id, session_id)
            long_term = await self.get_long_term_context(patient_id, session_id)
            return short_term, long_term
        except Exception as e:
            logger.error(f"Error getting full context: {e}")
            return [], ""

    async def get_chat_history(self, patient_id: str, session_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
        try:
            messages = await self.mongodb_service.get_chat_history(patient_id, session_id, limit=limit)
            return messages
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def clear_chat_history(self, patient_id: str, session_id: str = "default") -> None:
        try:
            await self.mongodb_service.clear_chat_history(patient_id, session_id)
            await self.mongodb_service.delete_chat_summary(patient_id, session_id)
            logger.info(f"Cleared chat history for patient {patient_id}")
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            raise

    async def get_context_stats(self, patient_id: str, session_id: str = "default") -> Dict[str, Any]:
        """Get context stats (parameter kept as patient_id for backward compat, returns userId)"""
        try:
            message_count = await self.mongodb_service.get_chat_message_count(patient_id, session_id)
            summary = await self.mongodb_service.get_chat_summary(patient_id, session_id)
            return {
                "userId": patient_id,  # Return as userId
                "session_id": session_id,
                "message_count": message_count,
                "has_long_term_summary": bool(summary),
                "max_short_term": self.max_short_term
            }
        except Exception as e:
            logger.error(f"Error getting context stats: {e}")
            return {"userId": patient_id, "session_id": session_id, "message_count": 0, "has_long_term_summary": False, "max_short_term": self.max_short_term}

    async def health_check(self) -> bool:
        try:
            return await self.mongodb_service.health_check()
        except Exception as e:
            logger.error(f"Context service health check failed: {e}")
            return False
