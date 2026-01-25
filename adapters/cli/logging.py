"""CLI logging configuration - redirects all logs to file for clean console output."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_cli_logging() -> Path:
    """Configure logging to redirect all output to ~/.clara/cli.log.

    This creates a clean console experience where only conversation
    (You: / Clara:) appears on screen, while all debug/info logs from
    libraries (mem0, httpx, anthropic, etc.) go to a file.

    Returns:
        Path to the log file (~/.clara/cli.log)
    """
    # Create ~/.clara directory if it doesn't exist
    log_dir = Path.home() / ".clara"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "cli.log"

    # Set up file handler with DEBUG level
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Clear all handlers from root logger and add only file handler
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(file_handler)
    root.setLevel(logging.DEBUG)

    # Suppress console output from these loggers
    # Set handlers to file-only and disable propagation
    noisy_loggers = [
        "mem0",
        "httpx",
        "anthropic",
        "openai",
        "clara_core",
        "db",
        "sqlalchemy.engine",
    ]

    for logger_name in noisy_loggers:
        lib_logger = logging.getLogger(logger_name)
        lib_logger.handlers.clear()
        lib_logger.addHandler(file_handler)
        lib_logger.propagate = False
        lib_logger.setLevel(logging.DEBUG)

    return log_file
