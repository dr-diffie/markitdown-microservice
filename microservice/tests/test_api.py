import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
import io
import os


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["message"] == "MarkItDown Microservice"


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get(f"{settings.API_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "workers_available" in data


def test_supported_formats_endpoint():
    """Test supported formats endpoint."""
    response = client.get(f"{settings.API_PREFIX}/supported-formats")
    assert response.status_code == 200
    data = response.json()
    assert "formats" in data
    assert len(data["formats"]) > 0
    # Check format structure
    first_format = data["formats"][0]
    assert "extension" in first_format
    assert "mimetype" in first_format
    assert "description" in first_format


def test_convert_text_file():
    """Test converting a simple text file."""
    content = b"Hello, World!\nThis is a test file."
    file = io.BytesIO(content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("test.txt", file, "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data
    assert "Hello, World!" in data["markdown"]
    assert "This is a test file." in data["markdown"]


def test_convert_with_keep_data_uris():
    """Test conversion with keep_data_uris parameter."""
    content = b"Test content with data URIs"
    file = io.BytesIO(content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("test.txt", file, "text/plain")},
        data={"keep_data_uris": "true"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data


def test_convert_with_file_extension_override():
    """Test conversion with file extension override."""
    content = b"Test content"
    file = io.BytesIO(content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("test.bin", file, "application/octet-stream")},
        data={"file_extension": ".txt"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data


def test_convert_unsupported_file_type():
    """Test converting an unsupported file type."""
    content = b"\x00\x01\x02\x03"  # Binary content
    file = io.BytesIO(content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("test.xyz", file, "application/octet-stream")}
    )
    
    assert response.status_code == 415
    data = response.json()
    assert "detail" in data


def test_convert_file_size_limit():
    """Test file size limit validation."""
    # Create content larger than limit
    large_content = b"x" * (settings.MAX_FILE_SIZE + 1)
    file = io.BytesIO(large_content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("large.txt", file, "text/plain")}
    )
    
    assert response.status_code == 413
    data = response.json()
    assert "detail" in data
    assert "size exceeds" in data["detail"]


def test_convert_missing_file():
    """Test conversion with missing file."""
    response = client.post(f"{settings.API_PREFIX}/convert")
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_convert_html_file():
    """Test converting an HTML file."""
    html_content = b"""
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Hello World</h1>
        <p>This is a test paragraph.</p>
    </body>
    </html>
    """
    file = io.BytesIO(html_content)
    
    response = client.post(
        f"{settings.API_PREFIX}/convert",
        files={"file": ("test.html", file, "text/html")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data
    assert "Hello World" in data["markdown"]
    assert "test paragraph" in data["markdown"]


def test_rate_limiting():
    """Test rate limiting functionality."""
    # This test would need to be adjusted based on actual rate limit settings
    # and would require mocking or adjusting the rate limit for testing
    pass


def test_cors_headers():
    """Test CORS headers are present."""
    response = client.options(
        f"{settings.API_PREFIX}/convert",
        headers={"Origin": "http://example.com"}
    )
    
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_security_headers():
    """Test security headers are present."""
    response = client.get("/")
    
    assert "x-content-type-options" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "x-frame-options" in response.headers
    assert response.headers["x-frame-options"] == "DENY"
    assert "x-xss-protection" in response.headers
    assert "strict-transport-security" in response.headers
    assert "content-security-policy" in response.headers


def test_request_id_header():
    """Test request ID header is added."""
    response = client.get("/")
    
    assert "x-request-id" in response.headers
    # Verify it's a valid UUID format
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36  # Standard UUID length with hyphens