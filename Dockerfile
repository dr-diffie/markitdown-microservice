# Single stage build for simplicity
FROM python:3.11-slim

# Install runtime and build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    exiftool \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements and install as root (globally)
COPY microservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy markitdown package and install globally
COPY packages/markitdown /tmp/markitdown
RUN pip install --no-cache-dir /tmp/markitdown[all] && rm -rf /tmp/markitdown

# Copy application code
COPY microservice/app /app/app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV EXIFTOOL_PATH=/usr/bin/exiftool
ENV FFMPEG_PATH=/usr/bin/ffmpeg

# Change ownership of app directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health').read()" || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]