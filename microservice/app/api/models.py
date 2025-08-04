from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ConversionRequest(BaseModel):
    keep_data_uris: bool = Field(
        default=False,
        description="Whether to preserve data URIs in the converted markdown"
    )
    file_extension: Optional[str] = Field(
        default=None,
        description="Override file extension for conversion"
    )
    mimetype: Optional[str] = Field(
        default=None,
        description="Override MIME type for conversion"
    )


class ConversionResponse(BaseModel):
    markdown: str = Field(
        description="The converted markdown content"
    )
    title: Optional[str] = Field(
        default=None,
        description="Extracted title from the document, if available"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata extracted from the document"
    )


class HealthResponse(BaseModel):
    status: str = Field(
        default="healthy",
        description="Health status of the service"
    )
    version: str = Field(
        description="Version of the service"
    )
    workers_available: int = Field(
        description="Number of available worker processes"
    )


class SupportedFormat(BaseModel):
    extension: str = Field(
        description="File extension (e.g., '.pdf')"
    )
    mimetype: str = Field(
        description="MIME type for the format"
    )
    description: str = Field(
        description="Human-readable description of the format"
    )


class SupportedFormatsResponse(BaseModel):
    formats: list[SupportedFormat] = Field(
        description="List of supported file formats"
    )


class ErrorResponse(BaseModel):
    detail: str = Field(
        description="Error message"
    )
    error_type: str = Field(
        description="Type of error"
    )
    status_code: int = Field(
        description="HTTP status code"
    )