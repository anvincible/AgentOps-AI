from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import HTTPException

from backend.app.safe_logging import log_sanitized_exception


logger = logging.getLogger(__name__)


def check_database_readiness(
    database_config: dict[str, Any],
) -> dict[str, str]:
    """Confirm PostgreSQL accepts a lightweight, read-only query."""

    try:
        connection_config = dict(database_config)
        database_name = connection_config.pop("database", None)
        if database_name is not None:
            connection_config["dbname"] = database_name

        with psycopg.connect(
            **connection_config,
            connect_timeout=2,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("Readiness query returned no result.")
    except Exception as error:
        log_sanitized_exception(
            logger,
            "Database readiness check failed",
            error,
        )
        raise HTTPException(
            status_code=503,
            detail="Service is not ready.",
        ) from None

    return {"status": "ok", "service": "AgentOps AI"}
