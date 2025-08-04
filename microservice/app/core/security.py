from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
import magic
import mimetypes
from ..core.config import settings


logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for request validation and rate limiting."""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit_storage = defaultdict(list)
        self.cleanup_interval = 60  # Clean up old entries every minute
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Add security headers
        start_time = time.time()
        
        # Check rate limiting
        if not await self.check_rate_limit(request):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "error_type": "rate_limit_error",
                    "status_code": 429
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        # Add request timing
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    async def check_rate_limit(self, request: Request) -> bool:
        """Check if request exceeds rate limit."""
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return True
        
        # Clean up old entries periodically
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.cleanup_old_entries()
            self.last_cleanup = current_time
        
        # Get client IP
        client_ip = request.client.host
        
        # Get current timestamp
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Filter requests within the last minute
        recent_requests = [
            req_time for req_time in self.rate_limit_storage[client_ip]
            if req_time > minute_ago
        ]
        
        # Update storage with filtered list
        self.rate_limit_storage[client_ip] = recent_requests
        
        # Check rate limit
        if len(recent_requests) >= settings.RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return False
        
        # Add current request
        self.rate_limit_storage[client_ip].append(now)
        return True
    
    def cleanup_old_entries(self):
        """Remove old entries from rate limit storage."""
        cutoff_time = datetime.now() - timedelta(minutes=2)
        for ip in list(self.rate_limit_storage.keys()):
            self.rate_limit_storage[ip] = [
                req_time for req_time in self.rate_limit_storage[ip]
                if req_time > cutoff_time
            ]
            if not self.rate_limit_storage[ip]:
                del self.rate_limit_storage[ip]


def validate_file_type(file_content: bytes, filename: str, provided_mimetype: str = None) -> tuple[str, str]:
    """
    Validate file type using magic numbers and extension.
    
    Returns:
        tuple: (detected_mimetype, file_extension)
    
    Raises:
        HTTPException: If file type is not supported
    """
    # Detect MIME type using python-magic
    try:
        mime = magic.Magic(mime=True)
        detected_mimetype = mime.from_buffer(file_content)
    except Exception as e:
        logger.error(f"Error detecting MIME type: {e}")
        detected_mimetype = None
    
    # Get file extension
    file_extension = None
    if filename:
        parts = filename.lower().split('.')
        if len(parts) > 1:
            file_extension = f".{parts[-1]}"
    
    # Use provided mimetype if detection failed
    if not detected_mimetype and provided_mimetype:
        detected_mimetype = provided_mimetype
    
    # Validate against supported extensions
    if file_extension and file_extension not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file_extension}' is not supported"
        )
    
    # Additional MIME type validation
    supported_mimetypes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/html",
        "application/epub+zip",
        "application/vnd.ms-outlook",
        "audio/mpeg",
        "audio/mp4",
        "audio/wav",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "application/rss+xml",
        "text/xml",
        "text/plain",
        "text/markdown",
        "application/json",
        "application/x-ipynb+json",
        "application/zip",
        "application/x-zip-compressed"
    }
    
    if detected_mimetype and detected_mimetype not in supported_mimetypes:
        # Check if it's a text file with different encoding
        if not detected_mimetype.startswith("text/"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"MIME type '{detected_mimetype}' is not supported"
            )
    
    return detected_mimetype, file_extension


def validate_file_size(file_size: int) -> None:
    """
    Validate file size against configured limit.
    
    Raises:
        HTTPException: If file size exceeds limit
    """
    if file_size > settings.MAX_FILE_SIZE:
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )