"""Redacted, structured logging for er-audio-tool."""
from __future__ import annotations
import logging
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

TOKEN_PATTERN = re.compile(r"(token|auth|bearer|password|key)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE)


class RedactingFormatter(logging.Formatter):
    """Filters authentication tokens, raw secrets, and sensitive credentials from logs."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return TOKEN_PATTERN.sub(r"\1=***REDACTED***", msg)


def setup_logging(log_dir: Path, debug: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "er-audio-tool.log"

    logger = logging.getLogger("er_audio_tool")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if not logger.handlers:
        # File handler (5MB, 3 backups)
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(RedactingFormatter("[%(asctime)s] [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"))
        logger.addHandler(file_handler)

        # Stream handler
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(RedactingFormatter("[%(levelname)s] %(message)s"))
        logger.addHandler(stream_handler)

    return logger
