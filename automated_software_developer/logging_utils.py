"""Logging configuration helpers for AutoSD."""

from __future__ import annotations

import logging
from pathlib import Path

_LOGGER_NAME = "autosd"
_CONFIGURED = False


def configure_logging(*, log_file: Path, verbose: bool) -> logging.Logger:
    """Configure file logging for AutoSD CLI and return the logger."""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        if verbose:
            logger.setLevel(logging.DEBUG)
        return logger

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    log_path = log_file.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    """Return the AutoSD logger (configured or with null handler)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
