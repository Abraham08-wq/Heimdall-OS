import sys
from loguru import logger
from app.core.config import settings

def setup_logging():
    """Reroutes standard logging to Loguru and configures formats."""
    logger.remove()
    
    # JSON format for production (audit trail friendly)
    # Human-readable for development
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        enqueue=True,
        colorize=True
    )
    
    logger.info("Logging initialized", project=settings.PROJECT_NAME)

# Create a logger instance for imports
log = logger
