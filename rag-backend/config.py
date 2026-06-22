# config.py - Enhanced configuration management with MongoDB
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Pinecone configuration
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "maichat-index")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# OpenAI configuration
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")
LLM_API_KEY = os.getenv("LLM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", LLM_API_KEY)  # Fallback
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") # Optional base URL for compatible APIs (e.g. Mistral)

# Embedding model configuration
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "emilyalsentzer/Bio_ClinicalBERT")

# MongoDB configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "rag_medical_db")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")

# MongoDB collections
SESSIONS_COLLECTION = os.getenv("SESSIONS_COLLECTION", "sessions")
MESSAGES_COLLECTION = os.getenv("MESSAGES_COLLECTION", "messages")  
SUMMARIES_COLLECTION = os.getenv("SUMMARIES_COLLECTION", "chat_summaries")
PRACTITIONER_COLLECTION = os.getenv("PRACTITIONER_COLLECTION", "practitioners")

# Context management configuration
MAX_SHORT_TERM_MESSAGES = int(os.getenv("MAX_SHORT_TERM_MESSAGES", "10"))
MESSAGES_TO_SUMMARIZE = int(os.getenv("MESSAGES_TO_SUMMARIZE", "5"))
MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))

# Retrieval configuration
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))

# API configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Firebase configuration
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# Patient chat: frontend uses FHIR patient UUID; Firebase token uid is often different.
# When true, any authenticated user may list sessions for the requested patient id (typical patient portal).
# Set to false in production and use Firebase custom claims (patient_id, patientId, etc.) or uid match.
CHAT_RELAX_PATIENT_SESSION_ACCESS = os.getenv(
    "CHAT_RELAX_PATIENT_SESSION_ACCESS", "true"
).lower() in ("1", "true", "yes")

# Model loading configuration
TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "false")
os.environ["TOKENIZERS_PARALLELISM"] = TOKENIZERS_PARALLELISM

# Temperature settings for different operations
GENERATION_TEMPERATURE = float(os.getenv("GENERATION_TEMPERATURE", "0.2"))
SUMMARIZATION_TEMPERATURE = float(os.getenv("SUMMARIZATION_TEMPERATURE", "0.3"))

# Validation
def validate_config():
    """Validate required configuration parameters"""
    required_vars = {
        "PINECONE_API_KEY": PINECONE_API_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }
    missing = [k for k,v in required_vars.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    return True
