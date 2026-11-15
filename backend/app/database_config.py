from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_database_config(
    *, require_explicit: bool = False,
) -> dict[str, str | int]:
    """Load PostgreSQL settings; optionally reject fallback-only defaults."""
    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    database_url = values.get("DATABASE_URL")

    url_is_configured = False
    if database_url:
        parsed_url = urlparse(str(database_url))
        url_is_configured = (
            parsed_url.scheme in {"postgres", "postgresql"}
            and bool(parsed_url.hostname)
            and bool(parsed_url.path.strip("/"))
        )

    split_settings_are_configured = all(
        str(values.get(key) or "").strip()
        for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER")
    )
    if require_explicit and not (url_is_configured or split_settings_are_configured):
        raise ValueError(
            "Database configuration is missing or incomplete. Set DATABASE_URL "
            "or provide DB_HOST, DB_PORT, DB_NAME, and DB_USER."
        )

    if url_is_configured:
        parsed = urlparse(str(database_url))
        try:
            parsed_port = parsed.port
        except ValueError:
            if require_explicit:
                raise ValueError(
                    "Database configuration is invalid. Check DATABASE_URL or DB_PORT."
                ) from None
            raise
        if parsed.scheme in {"postgres", "postgresql"}:
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed_port or 5432,
                "database": parsed.path.lstrip("/") or "novamart",
                "user": unquote(parsed.username or "postgres"),
                "password": unquote(parsed.password or ""),
            }

    return {
        "host": str(values.get("DB_HOST") or "localhost"),
        "port": int(values.get("DB_PORT") or 5432),
        "database": str(values.get("DB_NAME") or "novamart"),
        "user": str(values.get("DB_USER") or "postgres"),
        "password": str(values.get("DB_PASSWORD") or ""),
    }
