"""Unified structured logger."""

from __future__ import annotations

import sys

from loguru import logger as _logger

from config import settings

_logger.remove()
_logger.add(
    sys.stdout,
    level=settings.hackknow_log_level,
    colorize=True,
    format=(
        "<green>{time:HH:mm:ss}</green> "
        "<level>{level: <8}</level> "
        "<cyan>{name}</cyan> "
        "<white>|</white> {message}"
    ),
)


def get_logger(name: str):
    return _logger.bind(name=name)
