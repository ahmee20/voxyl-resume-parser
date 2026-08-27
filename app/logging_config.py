"""
app/logging_config.py — Structured logging setup with console and file persistence.

Call configure_logging() once at application startup (in main.py lifespan).
Writes structured logs to both stdout (console) and logs/app.log (file).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with both console and rotating file handlers."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / "app.log"

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # 1. Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # 2. Rotating File handler (max 10MB per file, up to 5 backups)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger.addHandler(file_handler)

    # Structlog pipeline configuration
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
