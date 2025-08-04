import logging
import sys
from typing import Any, Dict
import json
from datetime import datetime
import traceback


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra'):
            for key, value in record.extra.items():
                if key not in log_data:
                    log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO"):
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Use structured formatter for production
    if log_level != "DEBUG":
        console_handler.setFormatter(StructuredFormatter())
    else:
        # Use simple formatter for development
        console_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
    
    # Configure root logger
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def __init__(self, correlation_id: str = None):
        self.correlation_id = correlation_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to record."""
        record.correlation_id = self.correlation_id or "no-correlation-id"
        return True


def get_logger(name: str, correlation_id: str = None) -> logging.Logger:
    """
    Get a logger with optional correlation ID.
    
    Args:
        name: Logger name
        correlation_id: Optional correlation ID for request tracking
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if correlation_id:
        # Add correlation ID filter
        correlation_filter = CorrelationIdFilter(correlation_id)
        logger.addFilter(correlation_filter)
    
    return logger