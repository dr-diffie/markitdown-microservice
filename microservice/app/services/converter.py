import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Dict, Any
import io
import logging
import sys
import os
import re

# Try different import methods for markitdown
try:
    from markitdown import MarkItDown
except ImportError:
    # If markitdown is not in the standard path, try adding it
    import site
    site_packages = site.getsitepackages()
    for sp in site_packages:
        if os.path.exists(os.path.join(sp, 'markitdown')):
            sys.path.insert(0, sp)
            break
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise ImportError(f"Could not import markitdown. Make sure it's installed. Error: {e}")

from ..core.config import settings


logger = logging.getLogger(__name__)


class ConversionService:
    """Service for converting files to markdown using MarkItDown."""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or settings.WORKER_COUNT
        self.executor = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the process pool executor."""
        if not self._initialized:
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
            self._initialized = True
            logger.info(f"ConversionService initialized with {self.max_workers} workers")
    
    async def shutdown(self):
        """Shutdown the process pool executor."""
        if self.executor:
            self.executor.shutdown(wait=True)
            self._initialized = False
            logger.info("ConversionService shutdown complete")
    
    async def convert_async(
        self, 
        file_content: bytes, 
        filename: str,
        keep_data_uris: bool = False,
        file_extension: Optional[str] = None,
        mimetype: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert file content to markdown asynchronously.
        
        Args:
            file_content: The file content as bytes
            filename: Original filename
            keep_data_uris: Whether to preserve data URIs
            file_extension: Override file extension
            mimetype: Override MIME type
            
        Returns:
            Dictionary with markdown content and metadata
        """
        if not self._initialized:
            await self.initialize()
        
        loop = asyncio.get_event_loop()
        
        try:
            result = await loop.run_in_executor(
                self.executor,
                _convert_sync,
                file_content,
                filename,
                keep_data_uris,
                file_extension,
                mimetype
            )
            return result
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}", exc_info=True)
            raise
    
    def get_available_workers(self) -> int:
        """Get the number of available workers."""
        if not self._initialized or not self.executor:
            return 0
        # This is an approximation - ProcessPoolExecutor doesn't expose queue state
        return self.max_workers


def _convert_sync(
    file_content: bytes,
    filename: str,
    keep_data_uris: bool = False,
    file_extension: Optional[str] = None,
    mimetype: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous conversion function to run in process pool.
    
    This function runs in a separate process, so it needs to be standalone.
    """
    try:
        # Create MarkItDown instance
        markitdown = MarkItDown()
        
        # Create a file-like object from bytes
        stream = io.BytesIO(file_content)
        
        # Prepare conversion options
        options = {
            "keep_data_uris": keep_data_uris
        }
        
        if file_extension:
            options["file_extension"] = file_extension
        
        if mimetype:
            options["mimetype"] = mimetype
        
        # Perform conversion
        result = markitdown.convert_stream(stream, **options)
        
        # Clean and process the markdown
        cleaned_markdown = _clean_markdown(result.text_content)
        
        # Extract metadata
        metadata = {}
        if hasattr(result, 'metadata') and result.metadata:
            metadata = result.metadata
        
        # Try to extract title if not provided
        title = None
        if hasattr(result, 'title'):
            title = result.title
        
        if not title:
            # Try to extract from first heading
            title_match = re.match(r'^#\s+(.+)$', cleaned_markdown, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
        
        return {
            "markdown": cleaned_markdown,
            "title": title,
            "metadata": metadata
        }
        
    except Exception as e:
        # Log error (logging might not work properly in subprocess)
        import traceback
        error_msg = f"Conversion error: {str(e)}\n{traceback.format_exc()}"
        raise RuntimeError(error_msg)


def _clean_markdown(markdown: str) -> str:
    """
    Clean and post-process markdown content.
    
    Args:
        markdown: Raw markdown content
        
    Returns:
        Cleaned markdown content
    """
    if not markdown:
        return ""
    
    # Remove excessive newlines (more than 2 consecutive)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    
    # Remove trailing whitespace from lines
    lines = markdown.split('\n')
    lines = [line.rstrip() for line in lines]
    markdown = '\n'.join(lines)
    
    # Ensure proper spacing around headers
    markdown = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', markdown)
    markdown = re.sub(r'(#{1,6}\s.+)\n([^\n])', r'\1\n\n\2', markdown)
    
    # Fix common formatting issues
    # Remove zero-width spaces
    markdown = markdown.replace('\u200b', '')
    
    # Normalize bullet points
    markdown = re.sub(r'^\s*[•·]\s+', '- ', markdown, flags=re.MULTILINE)
    
    # Ensure code blocks are properly formatted
    markdown = re.sub(r'```(\w*)\n\n', r'```\1\n', markdown)
    markdown = re.sub(r'\n\n```', r'\n```', markdown)
    
    # Remove leading/trailing whitespace
    markdown = markdown.strip()
    
    return markdown


class WorkerPool:
    """Manager for the conversion worker pool."""
    
    def __init__(self, worker_count: int = None):
        self.worker_count = worker_count or settings.WORKER_COUNT
        self.conversion_service = ConversionService(max_workers=self.worker_count)
        self._started = False
    
    async def start(self):
        """Start the worker pool."""
        if not self._started:
            await self.conversion_service.initialize()
            self._started = True
            logger.info(f"WorkerPool started with {self.worker_count} workers")
    
    async def shutdown(self):
        """Shutdown the worker pool."""
        if self._started:
            await self.conversion_service.shutdown()
            self._started = False
            logger.info("WorkerPool shutdown complete")
    
    def get_conversion_service(self) -> ConversionService:
        """Get the conversion service instance."""
        return self.conversion_service
    
    def get_available_workers(self) -> int:
        """Get the number of available workers."""
        return self.conversion_service.get_available_workers()