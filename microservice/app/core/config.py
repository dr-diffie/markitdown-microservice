from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    REQUEST_TIMEOUT: int = 300  # 5 minutes
    
    # Worker Settings
    WORKER_COUNT: int = 4
    MAX_QUEUE_SIZE: int = 100
    
    # Security
    ALLOWED_ORIGINS: List[str] = ["*"]
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Features
    ENABLE_REDIS: bool = False
    REDIS_URL: str = "redis://localhost:6379"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Supported file extensions and mimetypes
    SUPPORTED_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", 
        ".xlsx", ".xls", ".csv", ".html", ".htm",
        ".epub", ".msg", ".mp3", ".m4a", ".wav",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".xml", ".rss", ".txt", ".md", ".json",
        ".ipynb", ".zip"
    ]
    
    # Application metadata
    APP_NAME: str = "MarkItDown Microservice"
    APP_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()