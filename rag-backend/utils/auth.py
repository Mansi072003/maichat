# utils/auth.py
import os
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import credentials, initialize_app, auth
from firebase_admin.exceptions import FirebaseError
from utils.logger import get_logger
import config

logger = get_logger(__name__)

# Initialize Firebase Admin SDK
_firebase_initialized = False

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _firebase_initialized
    if _firebase_initialized:
        return
    
    try:
        if config.FIREBASE_CREDENTIALS_PATH and os.path.exists(config.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
            initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with service account credentials")
        elif config.FIREBASE_PROJECT_ID:
            # Use default credentials (e.g., from environment or GCP metadata)
            initialize_app()
            logger.info("Firebase Admin SDK initialized with default credentials")
        else:
            logger.warning("Firebase credentials not configured. Authentication will fail.")
        
        _firebase_initialized = True
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise

# HTTP Bearer token security scheme
# auto_error=False allows us to handle errors manually
security = HTTPBearer(auto_error=False)

async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Firebase ID token and return decoded token
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        Decoded Firebase token with user information
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    # Ensure Firebase is initialized
    if not _firebase_initialized:
        try:
            initialize_firebase()
        except Exception as e:
            logger.error(f"Firebase not initialized: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not available. Firebase not configured.",
            )
    
    # Check if credentials are provided
    if not credentials:
        logger.warning("No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Validate token is not empty
    if not token or not token.strip():
        logger.warning("Empty token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(token)
        
        # Extract user information
        user_info = {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "firebase_claims": decoded_token
        }
        
        logger.debug(f"Authenticated user: {user_info.get('uid')}")
        return user_info
        
    except ValueError as e:
        logger.warning(f"Invalid token format: {e}")
        logger.debug(f"Token length: {len(token) if token else 0}, Token preview: {token[:20] if token else 'None'}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token format: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except FirebaseError as e:
        logger.warning(f"Firebase authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error: {str(e)}",
        )

