# dependencies.py
from pipeline.rag_orchestrator import RAGOrchestrator
from pipeline.conversation_orchestrator import ConversationOrchestrator
from services.mongodb_service import MongoDBService
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService
from services.generation_service import GenerationService
from services.context_service import ContextService

# Singleton instances of all services
mongodb_service_instance = MongoDBService()
embedding_service_instance = EmbeddingService()
generation_service_instance = GenerationService()
retrieval_service_instance = RetrievalService(embedding_service_instance, mongodb_service_instance)
context_service_instance = ContextService(mongodb_service_instance, generation_service_instance)

# Legacy single-pipeline orchestrator (kept for backward compatibility)
rag_orchestrator_instance = RAGOrchestrator(
    mongodb_service_instance,
    embedding_service_instance,
    retrieval_service_instance,
    generation_service_instance,
    context_service_instance,
)

# New multi-agent Conversation Orchestrator (MAI Agentic architecture)
conversation_orchestrator_instance = ConversationOrchestrator(
    mongodb_service_instance,
    embedding_service_instance,
    retrieval_service_instance,
    generation_service_instance,
    context_service_instance,
)

# Dependency functions for FastAPI DI
async def get_mongodb_service() -> MongoDBService:
    return mongodb_service_instance

async def get_embedding_service() -> EmbeddingService:
    return embedding_service_instance

async def get_generation_service() -> GenerationService:
    return generation_service_instance

async def get_retrieval_service() -> RetrievalService:
    return retrieval_service_instance

async def get_context_service() -> ContextService:
    return context_service_instance

async def get_rag_orchestrator() -> RAGOrchestrator:
    return rag_orchestrator_instance

async def get_conversation_orchestrator() -> ConversationOrchestrator:
    return conversation_orchestrator_instance
