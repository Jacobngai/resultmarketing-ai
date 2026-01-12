"""
Routers package for ResultMarketing AI Microservice
"""
from .spreadsheet import router as spreadsheet_router
from .namecard import router as namecard_router
from .chat import router as chat_router

__all__ = [
    "spreadsheet_router",
    "namecard_router",
    "chat_router"
]
