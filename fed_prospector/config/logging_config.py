"""Structured logging setup."""

import logging
from logging.handlers import RotatingFileHandler
import sys
from config import settings


def setup_logging(name="fed_prospector"):
    """Configure structured logging with console and optional file output."""
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler
    file_handler = RotatingFileHandler(
        settings.LOG_DIR / "fed_prospector.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
