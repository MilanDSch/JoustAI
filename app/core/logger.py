"""Centralized logging configuration for the JoustAI application."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "joust.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with console and rotating file handlers.

    Calling this multiple times with the same name returns the same logger
    (standard logging behaviour), and handlers are only attached once.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler (INFO and above)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console)

    # Rotating file handler (DEBUG and above)
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger
