"""
app/logging_config.py — Structured logging setup with console and resilient file persistence.

Call configure_logging() once at application startup (in main.py lifespan).
Always writes structured logs to stdout (console) for serverless environments (e.g. Vercel / AWS Lambda),
and optionally attaches a rotating file handler when a writable directory is available.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with console handler and resilient file handler."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # 1. Console handler (always present, required for serverless stdout streaming)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # 2. Resilient file handler (try local logs, fallback to /tmp/logs, or skip if read-only)
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    target_dir = Path("/tmp/logs") if is_serverless else Path("logs")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = target_dir / "app.log"
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
    except OSError:
        # Read-only filesystem or permissions error; rely solely on console streaming
        pass

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
