from __future__ import annotations

import logging
from pathlib import Path
import traceback


def log_sanitized_exception(
    logger: logging.Logger,
    message: str,
    error: Exception,
    *,
    level: int = logging.ERROR,
) -> None:
    """Log failure type and source locations without exception text or locals."""

    frames = traceback.extract_tb(error.__traceback__)
    locations = " -> ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
        for frame in frames[-5:]
    ) or "unavailable"
    logger.log(
        level,
        "%s (exception_type=%s, traceback=%s)",
        message,
        type(error).__name__,
        locations,
    )
