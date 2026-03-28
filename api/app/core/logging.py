from __future__ import annotations

import logging
import sys

from .config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_level = logging.DEBUG if settings.environment != "production" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)

    if settings.environment == "production":
        try:
            from pythonjsonlogger.json import JsonFormatter

            formatter = JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            )
            handler.setFormatter(formatter)
        except ImportError:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    logging.basicConfig(level=log_level, handlers=[handler])


__all__ = ["configure_logging"]
