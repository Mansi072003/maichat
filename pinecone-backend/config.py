# config.py - Simple configuration for pinecone-backend
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set parallelism flag to prevent deadlocks in multi-process environments.
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Pinecone configuration
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "maichat-index")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Embedding model configuration
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "emilyalsentzer/Bio_ClinicalBERT")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # Use Docker service name
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation
def validate_config():
    """Validate required configuration parameters"""
    if not PINECONE_API_KEY:
        raise ValueError("Missing required environment variable: PINECONE_API_KEY")
    return True