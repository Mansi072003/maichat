# main.py (DI-enabled, production-ready)
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import config
from models.schemas import ChatRequest, ChatResponse
from utils.logger import get_logger
from utils.auth import initialize_firebase, verify_firebase_token

# Routers
from routers.chat_router import router as chat_router
from routers.sessions_router import router as sessions_router
from routers.patients_router import router as patients_router

# DI singletons
from dependencies import (
    rag_orchestrator_instance,
    conversation_orchestrator_instance,
    mongodb_service_instance,
    context_service_instance,
)

logger = get_logger(__name__)

# --- Lifespan event handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    try:
        # Initialize Firebase
        try:
            initialize_firebase()
        except Exception as e:
            logger.warning(f"Firebase initialization warning: {e}")
        
        # Validate config
        try:
            config.validate_config()
        except Exception as e:
            logger.warning(f"Config validation warning: {e}")

        # Initialize the multi-agent Conversation Orchestrator (MAI Agentic architecture)
        await conversation_orchestrator_instance.initialize()
        logger.info("Conversation Orchestrator and all services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        await conversation_orchestrator_instance.cleanup()
        logger.info("Conversation Orchestrator cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# FastAPI app
app = FastAPI(
    title="Modular RAG Medical Assistant",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Assign singletons
mongodb_service = mongodb_service_instance
context_service = context_service_instance
rag_orchestrator = rag_orchestrator_instance
conversation_orchestrator = conversation_orchestrator_instance

# --- Include routers with authentication and v1 prefix ---
app.include_router(chat_router, prefix="/v1/chat", tags=["chat"], dependencies=[Depends(verify_firebase_token)])
app.include_router(sessions_router, prefix="/v1/chat/sessions", tags=["sessions"], dependencies=[Depends(verify_firebase_token)])
app.include_router(patients_router, prefix="/v1/chat/patients", tags=["patients"], dependencies=[Depends(verify_firebase_token)])

# --- Root endpoint (public) ---
@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        return FileResponse("static/index.html")
    except FileNotFoundError:
        return HTMLResponse("<h1>Modular RAG Medical Assistant</h1>")

# --- Main chat endpoint (protected) — now uses multi-agent ConversationOrchestrator ---
@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        # Ensure session exists
        session_id = request.session_id or None
        if not session_id or session_id == "default":
            session = await mongodb_service.create_session(patient_id=request.patient_id)
            session_id = session.get("session_id")
        else:
            session = await mongodb_service.get_session(session_id)
            if not session:
                session = await mongodb_service.create_session(
                    patient_id=request.patient_id,
                    session_id=session_id
                )

        # Multi-agent orchestrator: classify → route → agents → merge → safety
        response = await conversation_orchestrator.process_query(
            query=request.query,
            patient_id=request.patient_id,
            practitioner_id=request.practitioner_id,
            session_id=session_id
        )

        assistant_text = response.get("answer", "")

        testing_info = {
            "context_details": response.get("context_used", []),
            "intent_classification": response.get("intent_classification", {}),
            "agents_invoked": response.get("agents_invoked", []),
            "agent_details": response.get("agent_details", {}),
            "all_warnings": response.get("all_warnings", []),
            "all_clinician_triggers": response.get("all_clinician_triggers", []),
            "safety_review": response.get("safety_review", {}),
            "sources_used": response.get("sources", []),
            "retrieval_stats": response.get("retrieval_stats", {}),
            "context_summary": response.get("context_summary", ""),
        }

        return ChatResponse(
            answer=assistant_text,
            session_id=session_id,
            context_used=response.get("context_used", []),
            sources=response.get("sources", []),
            metadata=response.get("metadata", {}),
            testing_details=testing_info
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Health check (public) ---
@app.get("/health")
async def health_check():
    try:
        health_status = await conversation_orchestrator.health_check()
        health_status["mongodb_local"] = await mongodb_service.health_check()
        return {
            "status": "healthy" if health_status.get("overall", True) else "degraded",
            "services": health_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# --- Chat history endpoints (protected) ---
# --- All ID are used patient identifiere, doctor identifier etc ---
@app.get("/v1/chat-history/{patient_id}")
async def get_chat_history(
    patient_id: str,
    limit: int = 10,
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        history = await context_service.get_chat_history(patient_id, limit=limit)
        return {"patient_id": patient_id, "history": history}
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")

@app.delete("/v1/chat-history/{patient_id}")
async def clear_chat_history(
    patient_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    try:
        await context_service.clear_chat_history(patient_id)
        return {"message": f"Chat history cleared for patient {patient_id}"}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear chat history")

# --- Run app ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, log_level="info")
