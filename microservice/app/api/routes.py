from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse
import logging
import traceback
from typing import Optional
import asyncio
import time
import os

from ..api.models import (
    ConversionResponse, 
    HealthResponse, 
    SupportedFormatsResponse,
    SupportedFormat,
    ErrorResponse
)
from ..core.config import settings
from ..core.security import validate_file_type, validate_file_size
from ..services.converter import ConversionService
from ..api.admin import update_conversion_stats


logger = logging.getLogger(__name__)
router = APIRouter(prefix=settings.API_PREFIX)


# Supported formats mapping
SUPPORTED_FORMATS = [
    SupportedFormat(
        extension=".pdf",
        mimetype="application/pdf",
        description="Adobe Portable Document Format"
    ),
    SupportedFormat(
        extension=".docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        description="Microsoft Word Document (DOCX)"
    ),
    SupportedFormat(
        extension=".doc",
        mimetype="application/msword",
        description="Microsoft Word Document (DOC)"
    ),
    SupportedFormat(
        extension=".pptx",
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        description="Microsoft PowerPoint Presentation (PPTX)"
    ),
    SupportedFormat(
        extension=".ppt",
        mimetype="application/vnd.ms-powerpoint",
        description="Microsoft PowerPoint Presentation (PPT)"
    ),
    SupportedFormat(
        extension=".xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description="Microsoft Excel Spreadsheet (XLSX)"
    ),
    SupportedFormat(
        extension=".xls",
        mimetype="application/vnd.ms-excel",
        description="Microsoft Excel Spreadsheet (XLS)"
    ),
    SupportedFormat(
        extension=".csv",
        mimetype="text/csv",
        description="Comma-Separated Values"
    ),
    SupportedFormat(
        extension=".html",
        mimetype="text/html",
        description="HyperText Markup Language"
    ),
    SupportedFormat(
        extension=".epub",
        mimetype="application/epub+zip",
        description="Electronic Publication"
    ),
    SupportedFormat(
        extension=".msg",
        mimetype="application/vnd.ms-outlook",
        description="Microsoft Outlook Message"
    ),
    SupportedFormat(
        extension=".mp3",
        mimetype="audio/mpeg",
        description="MP3 Audio File"
    ),
    SupportedFormat(
        extension=".m4a",
        mimetype="audio/mp4",
        description="MPEG-4 Audio File"
    ),
    SupportedFormat(
        extension=".wav",
        mimetype="audio/wav",
        description="Waveform Audio File"
    ),
    SupportedFormat(
        extension=".jpg",
        mimetype="image/jpeg",
        description="JPEG Image"
    ),
    SupportedFormat(
        extension=".png",
        mimetype="image/png",
        description="Portable Network Graphics"
    ),
    SupportedFormat(
        extension=".gif",
        mimetype="image/gif",
        description="Graphics Interchange Format"
    ),
    SupportedFormat(
        extension=".bmp",
        mimetype="image/bmp",
        description="Bitmap Image"
    ),
    SupportedFormat(
        extension=".xml",
        mimetype="application/xml",
        description="Extensible Markup Language"
    ),
    SupportedFormat(
        extension=".txt",
        mimetype="text/plain",
        description="Plain Text File"
    ),
    SupportedFormat(
        extension=".md",
        mimetype="text/markdown",
        description="Markdown Document"
    ),
    SupportedFormat(
        extension=".json",
        mimetype="application/json",
        description="JavaScript Object Notation"
    ),
    SupportedFormat(
        extension=".ipynb",
        mimetype="application/x-ipynb+json",
        description="Jupyter Notebook"
    ),
    SupportedFormat(
        extension=".zip",
        mimetype="application/zip",
        description="ZIP Archive"
    )
]


async def get_conversion_service(request: Request) -> ConversionService:
    """Get conversion service from app state."""
    if not hasattr(request.app.state, 'worker_pool'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    return request.app.state.worker_pool.get_conversion_service()


@router.post("/convert", response_model=ConversionResponse)
async def convert_file(
    request: Request,
    file: UploadFile = File(...),
    keep_data_uris: bool = False,
    file_extension: Optional[str] = None,
    mimetype: Optional[str] = None,
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """
    Convert a file to markdown format.
    
    - **file**: The file to convert (required)
    - **keep_data_uris**: Whether to preserve data URIs in the output (default: false)
    - **file_extension**: Override the file extension for conversion
    - **mimetype**: Override the MIME type for conversion
    """
    start_time = time.time()
    file_size = 0
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        validate_file_size(file_size)
        
        # Validate file type
        detected_mimetype, detected_extension = validate_file_type(
            file_content, 
            file.filename,
            mimetype or file.content_type
        )
        
        # Use overrides if provided
        final_extension = file_extension or detected_extension
        final_mimetype = mimetype or detected_mimetype
        
        logger.info(
            f"Converting file: {file.filename}, "
            f"size: {file_size} bytes, "
            f"extension: {final_extension}, "
            f"mimetype: {final_mimetype}"
        )
        
        # Convert with timeout
        try:
            result = await asyncio.wait_for(
                conversion_service.convert_async(
                    file_content=file_content,
                    filename=file.filename,
                    keep_data_uris=keep_data_uris,
                    file_extension=final_extension,
                    mimetype=final_mimetype
                ),
                timeout=settings.REQUEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            duration = (time.time() - start_time) * 1000  # Convert to ms
            update_conversion_stats(
                filename=file.filename,
                file_type=final_extension,
                file_size=file_size,
                duration=duration,
                status="timeout"
            )
            logger.error(f"Conversion timeout for file: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Conversion timeout after {settings.REQUEST_TIMEOUT} seconds"
            )
        
        # Calculate duration
        duration = (time.time() - start_time) * 1000  # Convert to ms
        
        # Update statistics
        update_conversion_stats(
            filename=file.filename,
            file_type=final_extension,
            file_size=file_size,
            duration=duration,
            status="success"
        )
        
        logger.info(f"Conversion successful for file: {file.filename} (took {duration:.2f}ms)")
        
        return ConversionResponse(
            markdown=result["markdown"],
            title=result.get("title"),
            metadata=result.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = (time.time() - start_time) * 1000  # Convert to ms
        update_conversion_stats(
            filename=file.filename if file else "unknown",
            file_type=file_extension or os.path.splitext(file.filename)[1] if file else "unknown",
            file_size=file_size,
            duration=duration,
            status="error"
        )
        logger.error(f"Conversion error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversion failed: {str(e)}"
        )
    finally:
        await file.close()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """Check the health status of the service."""
    try:
        workers_available = conversion_service.get_available_workers()
        
        return HealthResponse(
            status="healthy",
            version=settings.APP_VERSION,
            workers_available=workers_available
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "version": settings.APP_VERSION,
                "workers_available": 0,
                "error": str(e)
            }
        )


@router.get("/supported-formats", response_model=SupportedFormatsResponse)
async def get_supported_formats():
    """Get list of supported file formats."""
    return SupportedFormatsResponse(formats=SUPPORTED_FORMATS)


# Note: Exception handlers should be added at the app level in main.py, not on routers