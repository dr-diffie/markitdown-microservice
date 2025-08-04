# CLAUDE.md

## Project: MarkItDown Microservice

### Mission
Transform the Microsoft MarkItDown package into a production-ready FastAPI microservice that provides file-to-markdown conversion via REST API. The service must be secure, efficient, and containerized for deployment on Coolify.

### Context
- This is a fork of Microsoft's markitdown package (https://github.com/microsoft/markitdown)
- We're building an API wrapper around the existing conversion functionality
- The core conversion logic should remain untouched
- The service will run in Docker on Coolify infrastructure
- Performance is critical - must handle concurrent requests efficiently

### Technical Requirements

#### 1. API Design
- **POST /convert** - Main endpoint for file conversion
  - Accept file upload (multipart/form-data)
  - Accept optional parameters: `keep_data_uris`, `file_extension`, `mimetype`
  - Return JSON: `{markdown: str, title: str|null, metadata: dict}`
- **GET /health** - Health check endpoint
- **GET /docs** - Auto-generated API documentation
- **GET /supported-formats** - List supported file formats

#### 2. Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│   Queue     │────▶│   Worker    │
│   (async)   │     │ (asyncio)   │     │   Pool      │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Redis     │     │ MarkItDown  │
                    │  (optional) │     │   Core      │
                    └─────────────┘     └─────────────┘
```

#### 3. Performance Requirements
- Use `uvicorn` with multiple workers
- Implement multiprocessing pool for CPU-intensive conversions
- Async request handling with proper queuing
- Configurable concurrency limits
- Request timeout handling (default: 300s)

#### 4. Security Requirements
- File size limits (configurable, default: 100MB)
- File type validation before processing
- Rate limiting per IP
- Input sanitization
- No file system persistence (process in memory)
- Secure headers (CORS, CSP, etc.)

#### 5. Docker Configuration
- Multi-stage build for minimal image size
- Non-root user execution
- Health check configuration
- Resource limits (memory, CPU)
- Graceful shutdown handling

### Implementation Guide

#### Directory Structure
```
markitdown-microservice/
├── packages/
│   └── markitdown/          # Original package (unchanged)
├── microservice/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py    # API endpoints
│   │   │   └── models.py    # Pydantic models
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py    # Settings management
│   │   │   ├── security.py  # Security middleware
│   │   │   └── logging.py   # Logging setup
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── converter.py # Conversion service
│   │   │   └── worker.py    # Worker pool management
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── cleanup.py   # Markdown post-processing
│   ├── requirements.txt
│   └── tests/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

#### Key Implementation Files

##### 1. `microservice/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.api import routes
from app.core import config, security, logging
from app.services.worker import WorkerPool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.worker_pool = WorkerPool(config.WORKER_COUNT)
    await app.state.worker_pool.start()
    yield
    # Shutdown
    await app.state.worker_pool.shutdown()

app = FastAPI(
    title="MarkItDown Microservice",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(security.SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Routes
app.include_router(routes.router)
```

##### 2. `microservice/app/api/routes.py`
```python
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from app.api.models import ConversionResponse, ConversionRequest
from app.services.converter import ConversionService

router = APIRouter()

@router.post("/convert", response_model=ConversionResponse)
async def convert_file(
    request: Request,
    file: UploadFile = File(...),
    keep_data_uris: bool = False,
    file_extension: str = None,
    mimetype: str = None
):
    # Size validation
    # Type validation
    # Queue conversion task
    # Return result
    pass

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/supported-formats")
async def supported_formats():
    return {
        "formats": [
            {"extension": ".pdf", "mimetype": "application/pdf"},
            {"extension": ".docx", "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            # ... etc
        ]
    }
```

##### 3. `microservice/app/core/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    REQUEST_TIMEOUT: int = 300  # 5 minutes
    
    # Worker Settings
    WORKER_COUNT: int = 4
    MAX_QUEUE_SIZE: int = 100
    
    # Security
    ALLOWED_ORIGINS: list = ["*"]
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Features
    ENABLE_REDIS: bool = False
    REDIS_URL: str = "redis://localhost:6379"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
```

##### 4. `microservice/app/services/converter.py`
```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from markitdown import MarkItDown
import io

class ConversionService:
    def __init__(self, max_workers: int = 4):
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        self.markitdown = MarkItDown()
    
    async def convert_async(self, file_content: bytes, options: dict) -> dict:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._convert_sync,
            file_content,
            options
        )
        return result
    
    def _convert_sync(self, file_content: bytes, options: dict) -> dict:
        # Actual conversion logic
        stream = io.BytesIO(file_content)
        result = self.markitdown.convert_stream(stream, **options)
        return {
            "markdown": self._clean_markdown(result.markdown),
            "title": result.title,
            "metadata": {}  # Additional metadata if needed
        }
    
    def _clean_markdown(self, markdown: str) -> str:
        # Post-processing logic
        # Remove excessive newlines
        # Fix formatting issues
        # etc.
        return markdown
```

##### 5. `Dockerfile`
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY microservice/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy markitdown package
COPY packages/markitdown /build/markitdown
RUN pip install --no-cache-dir --user -e ./markitdown[all]

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY microservice/app /app/app

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

##### 6. `docker-compose.yml`
```yaml
version: '3.8'

services:
  markitdown-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MAX_FILE_SIZE=104857600
      - WORKER_COUNT=4
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    restart: unless-stopped
```

### Critical Implementation Notes

1. **Memory Management**
   - Process files in streaming mode when possible
   - Implement cleanup after each conversion
   - Monitor memory usage and implement circuit breakers

2. **Error Handling**
   - Graceful degradation for unsupported formats
   - Proper error messages with status codes
   - Timeout handling for long conversions

3. **Performance Optimization**
   - Use process pool for CPU-bound conversions
   - Implement request queuing to prevent overload
   - Consider caching for repeated conversions (if Redis enabled)

4. **Security Hardening**
   - Validate file magic numbers, not just extensions
   - Implement virus scanning (optional)
   - Log all conversion attempts with metadata

5. **Monitoring**
   - Prometheus metrics endpoint
   - Structured logging with correlation IDs
   - Performance tracking per file type

### Testing Strategy

1. **Unit Tests**
   - Test each converter wrapper
   - Test security validations
   - Test error scenarios

2. **Integration Tests**
   - Test full conversion flow
   - Test concurrent requests
   - Test resource limits

3. **Load Tests**
   - Simulate high concurrency
   - Test with large files
   - Measure response times

### Deployment Checklist

- [ ] Environment variables configured
- [ ] Resource limits set appropriately
- [ ] Health checks passing
- [ ] Logs properly configured
- [ ] Monitoring dashboards ready
- [ ] Rate limiting tested
- [ ] Security headers verified
- [ ] Graceful shutdown tested
- [ ] Backup/recovery plan documented

### Performance Targets

- Concurrent requests: 100+
- Average response time: <5s for documents <10MB
- Memory usage: <2GB under normal load
- CPU usage: <80% with 4 workers
- Success rate: >99.9%

### Known Limitations

1. File size limit of 100MB (configurable)
2. Timeout of 5 minutes per conversion
3. No persistent storage (stateless)
4. Limited to formats supported by MarkItDown

### Quick Start Commands

```bash
# Build and run locally
docker-compose up --build

# Run tests
docker run --rm markitdown-microservice pytest

# Check API docs
open http://localhost:8000/docs

# Test conversion
curl -X POST -F "file=@test.pdf" http://localhost:8000/api/v1/convert
```

This microservice wrapper maintains the original MarkItDown functionality while adding production-ready API capabilities, security, and performance optimizations suitable for deployment on Coolify.