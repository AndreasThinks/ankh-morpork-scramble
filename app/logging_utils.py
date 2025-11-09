"""Utilities for consistent structured logging across the project."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable, Optional

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_NOISY_LOGGERS: Iterable[str] = (
    "httpx",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastmcp",
)


def _parse_log_level(value: str | None, fallback: int) -> int:
    """Convert a string representation to a logging level."""

    if not value:
        return fallback

    try:
        level = getattr(logging, value.upper())
        if isinstance(level, int):
            return level
    except AttributeError:
        pass

    return fallback


def configure_root_logger(
    *,
    service_name: str,
    env_prefix: str = "",
    default_level: str = "INFO",
    default_log_dir: str = "logs",
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
) -> Optional[Path]:
    """Configure a root logger that streams to stdout and optionally to a file.

    Parameters
    ----------
    service_name:
        Identifier used for the on-disk log file name.
    env_prefix:
        Prefix used when reading environment variables (``{prefix}LOG_LEVEL`` and
        ``{prefix}LOG_DIR``). Falls back to the shared ``LOG_LEVEL`` / ``LOG_DIR``
        variables when not provided.
    default_level:
        Level applied when no environment variable is set.
    default_log_dir:
        Directory created for log files when ``LOG_DIR`` is not provided. This is
        ignored when the resolved directory string is empty (``""``).
    max_bytes / backup_count:
        Rotation settings for the file handler. When omitted the defaults are
        1 MiB and 5 backups respectively.

    Returns
    -------
    pathlib.Path | None
        The resolved log file path when file logging is active; otherwise ``None``.
    """

    resolved_level = _parse_log_level(
        os.getenv(f"{env_prefix}LOG_LEVEL") or os.getenv("LOG_LEVEL"),
        _parse_log_level(default_level, logging.INFO),
    )

    log_dir_setting = os.getenv(f"{env_prefix}LOG_DIR")
    if log_dir_setting is None:
        log_dir_setting = os.getenv("LOG_DIR", default_log_dir)

    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    handlers.append(stream_handler)

    log_path: Optional[Path] = None
    if log_dir_setting:
        log_dir = Path(log_dir_setting).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{service_name}.log"

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes or int(os.getenv("LOG_MAX_BYTES", 1_048_576)),
            backupCount=backup_count or int(os.getenv("LOG_BACKUP_COUNT", 5)),
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        handlers.append(file_handler)

    logging.basicConfig(handlers=handlers, level=resolved_level, force=True)

    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log_path
