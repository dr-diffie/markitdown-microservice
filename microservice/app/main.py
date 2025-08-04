from fastapi import FastAPI, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import uvicorn
import logging
import uuid
import os

from .api import routes, auth as auth_routes, admin as admin_routes
from .core import config, security, logging as app_logging
from .core.auth import get_current_user
from .services.worker import WorkerPool


# Setup logging
app_logging.setup_logging(config.settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


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

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(routes.router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)

# Authentication middleware for specific routes
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check authentication for protected routes."""
    path = request.url.path
    
    # Protected routes that require authentication
    protected_routes = ["/docs", "/redoc", "/openapi.json", "/admin"]
    
    # Check if route needs protection
    needs_auth = any(path.startswith(route) for route in protected_routes)
    
    if needs_auth and path not in ["/login", "/api/auth/login"]:
        # Check for auth header
        auth_header = request.headers.get("Authorization")
        
        # For browser requests, redirect to login
        if not auth_header and request.headers.get("accept", "").startswith("text/html"):
            return RedirectResponse(url=f"/login?redirect={path}", status_code=status.HTTP_302_FOUND)
        
        # For API requests, check auth
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"},
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    response = await call_next(request)
    return response

# HTML Routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Serve admin dashboard."""
    if not current_user or not current_user.get("is_admin"):
        return RedirectResponse(url="/login?redirect=/admin", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": current_user
    })

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MarkItDown Microservice",
        "version": config.settings.APP_VERSION,
        "docs": "/docs",
        "health": f"{config.settings.API_PREFIX}/health",
        "admin": "/admin"
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