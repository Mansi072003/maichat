# services/mongodb_service.py
import asyncio
from typing import List, Optional, Any, Dict
import json
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from utils.logger import get_logger
import config
import uuid

import dns.resolver
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]

logger = get_logger(__name__)

class MongoDBService:
    """Service for MongoDB operations with async support"""

    def __init__(self):
        self.client = None
        self.db = None
        self.mongodb_url = config.MONGODB_URL
        self.database_name = config.MONGODB_DATABASE
        self.username = config.MONGODB_USERNAME
        self.password = config.MONGODB_PASSWORD

        # collection names
        self.sessions_col = config.SESSIONS_COLLECTION
        self.messages_col = config.MESSAGES_COLLECTION
        self.summaries_col = config.SUMMARIES_COLLECTION
        self.practitioners_col = config.PRACTITIONER_COLLECTION

    async def initialize(self):
        """Initialize MongoDB connection"""
        try:
            logger.info(f"Connecting to MongoDB at {self.mongodb_url}")

            # Build connection string with auth if provided
            if self.username and self.password:
                auth_url = f"mongodb://{self.username}:{self.password}@{self.mongodb_url.replace('mongodb://', '')}"
            else:
                auth_url = self.mongodb_url

            self.client = AsyncIOMotorClient(
                auth_url,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                maxPoolSize=50,
                minPoolSize=10,
                tls=True,
                tlsAllowInvalidCertificates=True,
                retryWrites=True
            )

            self.db = self.client[self.database_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")

            # Create indexes
            await self._create_indexes()

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Messages index - session + userId + timestamp
            await self.db[self.messages_col].create_index([
                ("session_id", 1),
                ("userId", 1),
                ("timestamp", -1)
            ])
            # Sessions index
            await self.db[self.sessions_col].create_index([("session_id", 1)], unique=True)
            await self.db[self.sessions_col].create_index([("userId", 1)])
            # Summaries
            await self.db[self.summaries_col].create_index([
                ("userId", 1),
                ("session_id", 1)
            ])

            logger.info("MongoDB indexes created successfully for chat collections")

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    # -----------------------
    # Session operations
    # -----------------------
    async def create_session(
        self,
        patient_id: Optional[str] = None,  # parameter name kept for backward compat
        session_type: str = "ai",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create or upsert a session doc and return it"""
        try:
            session_id = session_id or str(uuid.uuid4())
            now = datetime.utcnow()
            doc = {
                "session_id": session_id,
                "userId": patient_id,  # Store as userId in MongoDB
                "session_type": session_type,
                "status": "active",
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            }

            await self.db[self.sessions_col].update_one(
                {"session_id": session_id},
                {"$setOnInsert": doc},
                upsert=True
            )

            # Return session
            session = await self.db[self.sessions_col].find_one({"session_id": session_id})
            if session:
                session["_id"] = str(session["_id"])
                # serialize datetimes
                session["created_at"] = session["created_at"].isoformat()
                session["updated_at"] = session["updated_at"].isoformat()
            return session

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def get_session(self, sessionId: str) -> Optional[Dict[str, Any]]:
        """Get a session by session_id"""
        try:
            doc = await self.db[self.sessions_col].find_one({"session_id": sessionId})
            logger.info(f"the doc searched is={doc}")
            logger.info(f"Looking for session_id={sessionId} in collection {self.sessions_col}")
            if not doc:
                return None
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("created_at"), datetime):
                doc["created_at"] = doc["created_at"].isoformat()
            if isinstance(doc.get("updated_at"), datetime):
                doc["updated_at"] = doc["updated_at"].isoformat()
            return doc
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None

    async def get_active_session(self, user_id: str) -> Dict[str, Any]:
        """Return the most recent active session for *user_id*, creating one if none exists."""
        try:
            doc = await self.db[self.sessions_col].find_one(
                {"userId": user_id, "status": "active"},
                sort=[("updated_at", -1)],
            )
            if doc:
                doc["_id"] = str(doc["_id"])
                if isinstance(doc.get("created_at"), datetime):
                    doc["created_at"] = doc["created_at"].isoformat()
                if isinstance(doc.get("updated_at"), datetime):
                    doc["updated_at"] = doc["updated_at"].isoformat()
                return doc
            return await self.create_session(patient_id=user_id, session_type="ai")
        except Exception as e:
            logger.error(f"Error getting active session: {e}")
            raise

    async def list_sessions(self, patient_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List sessions, optionally filter by userId (parameter kept as patient_id for backward compat)"""
        try:
            query = {"userId": patient_id} if patient_id else {}
            cursor = self.db[self.sessions_col].find(query).sort("updated_at", -1).limit(limit)
            sessions = await cursor.to_list(length=limit)
            for s in sessions:
                s["_id"] = str(s["_id"])
                if isinstance(s.get("created_at"), datetime):
                    s["created_at"] = s["created_at"].isoformat()
                if isinstance(s.get("updated_at"), datetime):
                    s["updated_at"] = s["updated_at"].isoformat()
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    async def update_session(self, session_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update session doc and return new document"""
        try:
            update_fields["updated_at"] = datetime.utcnow()
            await self.db[self.sessions_col].update_one({"session_id": session_id}, {"$set": update_fields})
            return await self.get_session(session_id)
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return None

    async def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Mark session as ended"""
        try:
            await self.db[self.sessions_col].update_one(
                {"session_id": session_id},
                {"$set": {"status": "ended", "updated_at": datetime.utcnow()}}
            )
            return await self.get_session(session_id)
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return None

    # -----------------------
    # Chat history operations (messages)
    # -----------------------
    async def add_chat_message(
        self,
        patient_id: Optional[str],  # parameter name kept for backward compat
        session_id: str,
        sender_id: Optional[str],
        sender_type: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to chat history and return the saved message"""
        try:
            message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            message = {
                "message_id": message_id,
                "userId": patient_id,  # Store as userId in MongoDB
                "session_id": session_id,
                "sender_id": sender_id,
                "sender_type": sender_type,  # 'patient' | 'bot' | 'provider' | 'system'
                "content": content,
                "message_type": message_type,
                "metadata": metadata or {},
                "status": "sent",
                "timestamp": now,
            }

            await self.db[self.messages_col].insert_one(message)

            # bump session updated_at
            await self.db[self.sessions_col].update_one(
                {"session_id": session_id},
                {"$set": {"updated_at": now}},
                upsert=True
            )

            # NOTE: _cleanup_old_messages removed from the hot-path so that
            # full chat history is always available to the user.  The LLM
            # context window is limited separately in ContextService.

            # serialize for return
            message["timestamp"] = message["timestamp"].isoformat()
            return message

        except Exception as e:
            logger.error(f"Error adding chat message: {e}")
            raise

    async def get_chat_history(
        self,
        patient_id: Optional[str],  # parameter name kept for backward compat
        session_id: str = "default",
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recent chat history in chronological order"""
        try:
            query = {"session_id": session_id}
            if patient_id:
                query["userId"] = patient_id  # Query uses userId

            cursor = self.db[self.messages_col].find(query).sort("timestamp", 1).skip(skip).limit(limit)
            messages = await cursor.to_list(length=limit)
            for msg in messages:
                msg["_id"] = str(msg["_id"])
                if isinstance(msg.get("timestamp"), datetime):
                    msg["timestamp"] = msg["timestamp"].isoformat()
            return messages

        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def get_chat_message_count(
        self,
        patient_id: Optional[str],  # parameter name kept for backward compat
        session_id: str = "default"
    ) -> int:
        """Get count of messages in chat history"""
        try:
            query = {"session_id": session_id}
            if patient_id:
                query["userId"] = patient_id  # Query uses userId
            count = await self.db[self.messages_col].count_documents(query)
            return count
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0


    async def get_session_attachments(
        self,
        patient_id: Optional[str],
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Return list of attachments for a session. Empty until attachment storage is added."""
        try:
            query = {"session_id": session_id}
            if patient_id:
                query["userId"] = patient_id
            cursor = self.db[self.messages_col].find(query).limit(500)
            messages = await cursor.to_list(length=500)
            attachments = []
            for msg in messages:
                if msg.get("message_type") == "attachment" and isinstance(msg.get("metadata"), dict):
                    att_list = msg.get("metadata", {}).get("attachments", [])
                    for a in att_list if isinstance(att_list, list) else []:
                        if isinstance(a, dict):
                            attachments.append(a)
            return attachments
        except Exception as e:
            logger.error(f"Error getting session attachments: {e}")
            return []

    async def _cleanup_old_messages(
        self,
        patient_id: Optional[str],
        session_id: str
    ) -> None:
        """Remove old messages beyond the short-term limit"""
        try:
            count = await self.get_chat_message_count(patient_id, session_id)
            if count > config.MAX_SHORT_TERM_MESSAGES:
                excess_count = count - config.MAX_SHORT_TERM_MESSAGES
                cursor = self.db[self.messages_col].find({"session_id": session_id}).sort("timestamp", 1).limit(excess_count)
                old_messages = await cursor.to_list(length=excess_count)
                if old_messages:
                    old_ids = [msg["_id"] for msg in old_messages]
                    await self.db[self.messages_col].delete_many({"_id": {"$in": old_ids}})
                    logger.info(f"Cleaned up {len(old_ids)} old messages for session {session_id}")
        except Exception as e:
            logger.error(f"Error during message cleanup: {e}")

    async def clear_chat_history(
        self,
        patient_id: Optional[str],  # parameter name kept for backward compat
        session_id: str = "default"
    ) -> bool:
        """Clear all chat history for a session (and optional userId)"""
        try:
            query = {"session_id": session_id}
            if patient_id:
                query["userId"] = patient_id  # Query uses userId
            result = await self.db[self.messages_col].delete_many(query)
            logger.info(f"Cleared {result.deleted_count} messages for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            return False

    # -----------------------
    # Summaries
    # -----------------------
    async def set_chat_summary(self, patient_id: str, session_id: str, summary: str) -> bool:
        """Set chat summary (parameter name kept as patient_id for backward compat)"""
        try:
            await self.db[self.summaries_col].update_one(
                {"userId": patient_id, "session_id": session_id},  # Query uses userId
                {"$set": {"summary": summary, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error setting chat summary: {e}")
            return False

    async def get_chat_summary(self, patient_id: str, session_id: str) -> Optional[str]:
        """Get chat summary (parameter name kept as patient_id for backward compat)"""
        try:
            doc = await self.db[self.summaries_col].find_one({"userId": patient_id, "session_id": session_id})
            return doc.get("summary") if doc else None
        except Exception as e:
            logger.error(f"Error getting chat summary: {e}")
            return None

    async def delete_chat_summary(self, patient_id: str, session_id: str) -> bool:
        """Delete chat summary (parameter name kept as patient_id for backward compat)"""
        try:
            await self.db[self.summaries_col].delete_one({"userId": patient_id, "session_id": session_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting chat summary: {e}")
            return False

    # -----------------------
    # Practitioner operations (unchanged)
    # -----------------------
    async def get_practitioner_patients(self, practitioner_id: str) -> List[str]:
        try:
            doc = await self.db[self.practitioners_col].find_one({"practitioner_id": practitioner_id})
            if doc and "patients" in doc:
                return doc["patients"]
            else:
                logger.warning(f"No patients found for practitioner {practitioner_id}")
                return []
        except Exception as e:
            logger.error(f"Error getting practitioner patients: {e}")
            return []

    # Generic JSON ops
    async def set_json(self, collection_name: str, key: str, data: dict, expire: int = None) -> bool:
        try:
            doc = {"key": key, "data": data, "created_at": datetime.utcnow()}
            if expire:
                doc["expires_at"] = datetime.utcnow() + timedelta(seconds=expire)
            await self.db[collection_name].update_one({"key": key}, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.error(f"Error setting JSON data: {e}")
            return False

    async def get_json(self, collection_name: str, key: str) -> Optional[dict]:
        try:
            doc = await self.db[collection_name].find_one({"key": key})
            if doc:
                if "expires_at" in doc and doc["expires_at"] < datetime.utcnow():
                    await self.db[collection_name].delete_one({"key": key})
                    return None
                return doc.get("data")
            return None
        except Exception as e:
            logger.error(f"Error getting JSON data: {e}")
            return None

    async def delete_key(self, collection_name: str, key: str) -> bool:
        try:
            await self.db[collection_name].delete_one({"key": key})
            return True
        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if MongoDB connection is healthy"""
        try:
            if not self.client:
                return False
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False

    async def close(self):
        """Close MongoDB connection"""
        try:
            if self.client:
                self.client.close()
                logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
