from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
import uuid

from .api import routes
from .core import config, security, logging as app_logging
from .services.worker import WorkerPool


# Setup logging
app_logging.setup_logging(config.settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MarkItDown Microservice...")
    
    # Initialize worker pool
    app.state.worker_pool = WorkerPool(config.settings.WORKER_COUNT)
    await app.state.worker_pool.start()
    logger.info("Worker pool initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MarkItDown Microservice...")
    await app.state.worker_pool.shutdown()
    logger.info("Worker pool shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=config.settings.APP_NAME,
    version=config.settings.APP_VERSION,
    description="Production-ready microservice for converting documents to Markdown",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add middleware
# Security middleware
app.add_middleware(security.SecurityMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Trusted host middleware (optional, for production)
# app.add_middleware(
#     TrustedHostMiddleware,
#     allowed_hosts=["example.com", "*.example.com"]
# )

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracking."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Process the request
    response = await call_next(request)
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    return response

# Include routers
app.include_router(routes.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MarkItDown Microservice",
        "version": config.settings.APP_VERSION,
        "docs": "/docs",
        "health": f"{config.settings.API_PREFIX}/health"
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": "internal_error",
            "status_code": 500,
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=config.settings.LOG_LEVEL.lower()
    )