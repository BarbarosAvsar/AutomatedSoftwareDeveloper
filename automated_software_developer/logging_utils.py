"""Logging configuration helpers for AutoSD."""

from __future__ import annotations

import logging
from pathlib import Path

_LOGGER_NAME = "autosd"


def _close_handlers(logger: logging.Logger) -> None:
    """Detach and close all handlers currently bound to the logger."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def configure_logging(*, log_file: Path, verbose: bool) -> logging.Logger:
    """Configure file logging for AutoSD CLI and return the logger.

    Logging is reconfigured on every CLI invocation and the target file is
    truncated so each run has an isolated log history.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    _close_handlers(logger)

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    log_path = log_file.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger


def get_logger() -> logging.Logger:
    """Return the AutoSD logger (configured or with null handler)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
