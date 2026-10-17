"""Application logging setup."""

from __future__ import annotations

import logging
import sys

from backend.app.core.config import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    logger = logging.getLogger("sentinelai")
    if logger.handlers:
        logger.setLevel(settings.log_level)
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
    return logger
