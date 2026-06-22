# routers/__init__.py
"""
API routers for different endpoints
"""

from .chat_router import router as chat_router
from .sessions_router import router as sessions_router
from .patients_router import router as patients_router

__all__ = ["chat_router", "sessions_router", "patients_router"]

