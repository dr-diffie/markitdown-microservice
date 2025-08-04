import pytest
import asyncio
from app.services.converter import ConversionService, _clean_markdown


@pytest.fixture
async def conversion_service():
    """Create a conversion service instance."""
    service = ConversionService(max_workers=2)
    await service.initialize()
    yield service
    await service.shutdown()


@pytest.mark.asyncio
async def test_conversion_service_initialization(conversion_service):
    """Test conversion service initialization."""
    assert conversion_service._initialized
    assert conversion_service.executor is not None
    assert conversion_service.max_workers == 2


@pytest.mark.asyncio
async def test_convert_text_file(conversion_service):
    """Test converting a simple text file."""
    content = b"Hello, World!\nThis is a test."
    
    result = await conversion_service.convert_async(
        file_content=content,
        filename="test.txt",
        keep_data_uris=False
    )
    
    assert "markdown" in result
    assert "Hello, World!" in result["markdown"]
    assert "This is a test." in result["markdown"]


@pytest.mark.asyncio
async def test_convert_with_options(conversion_service):
    """Test conversion with custom options."""
    content = b"Test content"
    
    result = await conversion_service.convert_async(
        file_content=content,
        filename="test.txt",
        keep_data_uris=True,
        file_extension=".txt",
        mimetype="text/plain"
    )
    
    assert "markdown" in result
    assert result["markdown"].strip() == "Test content"


def test_clean_markdown_excessive_newlines():
    """Test cleaning excessive newlines."""
    markdown = "Line 1\n\n\n\nLine 2\n\n\n\n\nLine 3"
    cleaned = _clean_markdown(markdown)
    assert cleaned == "Line 1\n\nLine 2\n\nLine 3"


def test_clean_markdown_header_spacing():
    """Test proper spacing around headers."""
    markdown = "Text before\n# Header\nText after"
    cleaned = _clean_markdown(markdown)
    assert cleaned == "Text before\n\n# Header\n\nText after"


def test_clean_markdown_bullet_normalization():
    """Test bullet point normalization."""
    markdown = "• Item 1\n· Item 2\n- Item 3"
    cleaned = _clean_markdown(markdown)
    assert cleaned == "- Item 1\n- Item 2\n- Item 3"


def test_clean_markdown_code_blocks():
    """Test code block formatting."""
    markdown = "```python\n\nprint('hello')\n\n```"
    cleaned = _clean_markdown(markdown)
    assert cleaned == "```python\nprint('hello')\n```"


def test_clean_markdown_zero_width_spaces():
    """Test removal of zero-width spaces."""
    markdown = "Text with\u200bzero width space"
    cleaned = _clean_markdown(markdown)
    assert cleaned == "Text withzero width space"


def test_clean_markdown_trailing_whitespace():
    """Test removal of trailing whitespace."""
    markdown = "Line 1   \nLine 2  \nLine 3    "
    cleaned = _clean_markdown(markdown)
    assert cleaned == "Line 1\nLine 2\nLine 3"


def test_clean_markdown_empty_input():
    """Test cleaning empty markdown."""
    assert _clean_markdown("") == ""
    assert _clean_markdown(None) == ""


@pytest.mark.asyncio
async def test_get_available_workers(conversion_service):
    """Test getting available workers count."""
    workers = conversion_service.get_available_workers()
    assert workers == 2


@pytest.mark.asyncio
async def test_conversion_error_handling(conversion_service):
    """Test error handling in conversion."""
    # Test with invalid content that might cause an error
    with pytest.raises(Exception):
        await conversion_service.convert_async(
            file_content=None,  # Invalid content
            filename="test.txt"
        )