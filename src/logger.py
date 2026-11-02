"""Logging utilities for console progress steps and output/logs/run.log."""

import logging
from pathlib import Path
import config


def _get_file_logger() -> logging.Logger:
    """Return a configured file logger writing to config.LOG_PATH."""
    log_path = Path(config.LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("property_video_generator")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def log_step(message: str) -> None:
    """Print a user-facing step to the terminal and record it in run.log."""
    print(message)
    _get_file_logger().info(message)


def log_warning(message: str) -> None:
    """Print a warning message to the terminal and record it in run.log."""
    print(message)
    _get_file_logger().warning(message)


def log_debug(message: str) -> None:
    """Record debug details strictly to run.log."""
    _get_file_logger().debug(message)


def log_exception(exc: BaseException) -> None:
    """Record full traceback of an unexpected exception to run.log."""
    _get_file_logger().exception("Unexpected error occurred: %s", exc)