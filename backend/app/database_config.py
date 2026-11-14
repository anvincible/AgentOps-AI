from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_database_config() -> dict[str, str | int]:
    """Load PostgreSQL connection settings from .env and environment variables."""
    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    database_url = values.get("DATABASE_URL")

    if database_url:
        parsed = urlparse(str(database_url))
        if parsed.scheme in {"postgres", "postgresql"}:
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
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
