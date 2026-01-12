"""
ResultMarketing AI Microservice
FastAPI application for spreadsheet analysis, OCR, and AI chat processing
"""
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import HealthCheckResponse, APIResponse
from routers import spreadsheet_router, namecard_router, chat_router
from routers.voice import router as voice_router


# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("=" * 50)
    print("ResultMarketing AI Microservice Starting...")
    print(f"Environment: {'Development' if settings.debug else 'Production'}")
    print(f"Claude Model: {settings.claude_model}")
    print(f"CORS Origins: {settings.cors_origins}")
    print("=" * 50)

    # Check API keys
    if not settings.anthropic_api_key:
        print("WARNING: ANTHROPIC_API_KEY not configured")
    else:
        print("Claude API: Configured")

    if not settings.google_credentials_path:
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not configured")
    else:
        print("Google Vision API: Configured")

    yield

    # Shutdown
    print("ResultMarketing AI Microservice Shutting Down...")


# Create FastAPI application
app = FastAPI(
    title="ResultMarketing AI Microservice",
    description="""
    AI-powered processing service for ResultMarketing CRM.

    Features:
    - Spreadsheet analysis and processing
    - Business card/namecard OCR
    - AI chat with Claude
    - Malaysian phone number formatting
    - Contact categorization

    Built for Malaysian sales professionals.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    # Log error (in production, use proper logging)
    print(f"Unhandled error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include routers
app.include_router(spreadsheet_router)
app.include_router(namecard_router)
app.include_router(chat_router)
app.include_router(voice_router)


# Root endpoint
@app.get("/", response_model=APIResponse)
async def root():
    """
    Root endpoint - API information
    """
    return APIResponse(
        success=True,
        data={
            "name": "ResultMarketing AI Microservice",
            "version": "1.0.0",
            "description": "AI processing service for ResultMarketing CRM",
            "endpoints": {
                "health": "/health",
                "docs": "/docs",
                "spreadsheet": "/api/spreadsheet",
                "namecard": "/api/namecard",
                "chat": "/api/chat",
                "voice": "/api/voice"
            }
        }
    )


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint for monitoring and load balancers
    """
    services_status = {}

    # Check Claude API
    if settings.anthropic_api_key:
        services_status["claude"] = "configured"
    else:
        services_status["claude"] = "not_configured"

    # Check Google Vision
    if settings.google_credentials_path and os.path.exists(settings.google_credentials_path):
        services_status["vision"] = "configured"
    elif settings.google_credentials_path:
        services_status["vision"] = "credentials_missing"
    else:
        services_status["vision"] = "not_configured"

    # Check Redis (optional)
    if settings.redis_url:
        services_status["redis"] = "configured"
    else:
        services_status["redis"] = "not_configured"

    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        services=services_status,
        timestamp=datetime.utcnow()
    )


# Ready endpoint (for Kubernetes/Railway)
@app.get("/ready")
async def readiness_check():
    """
    Readiness check - verifies the service is ready to accept traffic
    """
    # Check required services
    if not settings.anthropic_api_key:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "Claude API not configured"}
        )

    return {"ready": True}


# Live endpoint (for Kubernetes/Railway)
@app.get("/live")
async def liveness_check():
    """
    Liveness check - verifies the service is running
    """
    return {"live": True}


# API info endpoint
@app.get("/api/info")
async def api_info():
    """
    Get API information and available endpoints
    """
    return {
        "name": "ResultMarketing AI Microservice",
        "version": "1.0.0",
        "endpoints": [
            {
                "path": "/api/spreadsheet/analyze",
                "method": "POST",
                "description": "Analyze uploaded spreadsheet"
            },
            {
                "path": "/api/spreadsheet/process",
                "method": "POST",
                "description": "Process and clean spreadsheet data"
            },
            {
                "path": "/api/spreadsheet/validate",
                "method": "POST",
                "description": "Quick validate spreadsheet"
            },
            {
                "path": "/api/namecard/scan",
                "method": "POST",
                "description": "Scan and extract namecard info"
            },
            {
                "path": "/api/namecard/scan-batch",
                "method": "POST",
                "description": "Batch process multiple namecards"
            },
            {
                "path": "/api/namecard/extract-text",
                "method": "POST",
                "description": "Extract raw text from image"
            },
            {
                "path": "/api/chat/query",
                "method": "POST",
                "description": "Process chat query with AI"
            },
            {
                "path": "/api/chat/analytics",
                "method": "POST",
                "description": "Get analytics insights"
            },
            {
                "path": "/api/chat/suggest-followup",
                "method": "POST",
                "description": "Get follow-up suggestions"
            },
            {
                "path": "/api/chat/categorize",
                "method": "POST",
                "description": "Categorize contacts"
            },
            {
                "path": "/api/voice/transcribe",
                "method": "POST",
                "description": "Transcribe voice to text"
            },
            {
                "path": "/api/voice/translate",
                "method": "POST",
                "description": "Transcribe and translate to English"
            },
            {
                "path": "/api/voice/extract",
                "method": "POST",
                "description": "Extract info from voice note"
            },
            {
                "path": "/api/voice/chat",
                "method": "POST",
                "description": "Process voice message for AI chat"
            }
        ],
        "rate_limits": {
            "requests_per_minute": settings.rate_limit_requests,
            "window_seconds": settings.rate_limit_window
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
