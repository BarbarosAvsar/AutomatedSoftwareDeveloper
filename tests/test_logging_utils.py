"""Tests for CLI logging configuration behavior."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.logging_utils import configure_logging


def test_configure_logging_overwrites_previous_run_log(tmp_path: Path) -> None:
    """Each configure call should start a fresh log file for the new run."""
    log_path = tmp_path / "autosd.log"

    first_logger = configure_logging(log_file=log_path, verbose=False)
    first_logger.info("from first run")

    second_logger = configure_logging(log_file=log_path, verbose=False)
    second_logger.info("from second run")

    content = log_path.read_text(encoding="utf-8")

    assert "from second run" in content
    assert "from first run" not in content
