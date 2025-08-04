# MarkItDown Microservice

[![PyPI](https://img.shields.io/pypi/v/markitdown.svg)](https://pypi.org/project/markitdown/)
![PyPI - Downloads](https://img.shields.io/pypi/dd/markitdown)
[![Built by AutoGen Team](https://img.shields.io/badge/Built%20by-AutoGen%20Team-blue)](https://github.com/microsoft/autogen)

This is a production-ready FastAPI microservice wrapper around Microsoft's MarkItDown package, providing REST API access to document-to-markdown conversion capabilities.

## Features

- **REST API** for file-to-markdown conversion
- **Production-ready** with security, rate limiting, and monitoring
- **High performance** with async processing and worker pools
- **Containerized** with Docker for easy deployment
- **Supports all MarkItDown formats**: PDF, Word, PowerPoint, Excel, Images, Audio, HTML, and more

## Quick Start

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/microsoft/markitdown.git
cd markitdown-microservice

# Start the service
docker-compose up --build

# The API will be available at http://localhost:8000
```

### Using Docker

```bash
# Build the image
docker build -t markitdown-microservice .

# Run the container
docker run -p 8000:8000 markitdown-microservice

# Access the API at http://localhost:8000
```

## API Documentation

Once running, you can access:
- Interactive API docs: http://localhost:8000/docs
- API specification: http://localhost:8000/openapi.json
- Health check: http://localhost:8000/api/v1/health

## API Endpoints

### Convert File
**POST** `/api/v1/convert`

Convert a file to markdown format.

```bash
# Example: Convert a PDF
curl -X POST -F "file=@document.pdf" http://localhost:8000/api/v1/convert

# With options
curl -X POST \
  -F "file=@document.pdf" \
  -F "keep_data_uris=true" \
  http://localhost:8000/api/v1/convert
```

**Parameters:**
- `file` (required): The file to convert
- `keep_data_uris` (optional): Preserve data URIs in output
- `file_extension` (optional): Override file extension
- `mimetype` (optional): Override MIME type

**Response:**
```json
{
  "markdown": "# Document Title\n\nContent...",
  "title": "Document Title",
  "metadata": {}
}
```

### Health Check
**GET** `/api/v1/health`

Check service health and available workers.

```bash
curl http://localhost:8000/api/v1/health
```

### Supported Formats
**GET** `/api/v1/supported-formats`

List all supported file formats.

```bash
curl http://localhost:8000/api/v1/supported-formats
```

## Configuration

The service can be configured via environment variables:

```env
# API Configuration
API_PREFIX=/api/v1
MAX_FILE_SIZE=104857600  # 100MB in bytes
REQUEST_TIMEOUT=300      # 5 minutes in seconds

# Worker Configuration
WORKER_COUNT=4
MAX_QUEUE_SIZE=100

# Security Configuration
ALLOWED_ORIGINS=*
RATE_LIMIT_PER_MINUTE=60

# Logging Configuration
LOG_LEVEL=INFO
```

Copy `.env.example` to `.env` and modify as needed.

## Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r microservice/requirements.txt
pip install -e packages/markitdown[all]

# Run the service
cd microservice
uvicorn app.main:app --reload
```

### Running Tests

```bash
cd microservice
pytest tests/
```

## Production Deployment

### Coolify Deployment

1. Create a new service in Coolify
2. Connect your Git repository
3. Set the build pack to Dockerfile
4. Configure environment variables as needed
5. Deploy!

### Security Features

- Rate limiting (60 requests/minute by default)
- File size validation (100MB default limit)
- File type validation with magic number checking
- Security headers (CORS, CSP, HSTS, etc.)
- Request ID tracking for debugging
- Non-root container execution

### Performance Optimization

- Process pool for CPU-intensive conversions
- Async request handling
- Configurable worker count
- Request queuing to prevent overload
- Graceful shutdown handling

## Architecture

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

## Monitoring

The service provides:
- Structured JSON logging
- Request correlation IDs
- Performance metrics in response headers
- Health check endpoint for monitoring

## Known Limitations

1. File size limit of 100MB (configurable)
2. Request timeout of 5 minutes (configurable)
3. No persistent storage (stateless)
4. Limited to formats supported by MarkItDown

## Contributing

This project is part of the Microsoft MarkItDown repository. Please see the main repository for contribution guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file in the root repository for details.

## Original MarkItDown Package

This microservice is built on top of the [MarkItDown](https://github.com/microsoft/markitdown) package. For more information about the core conversion functionality, supported formats, and Python API usage, please refer to the original package documentation.