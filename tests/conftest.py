from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _database_config() -> dict[str, str | int]:
    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    url = values.get("DATABASE_URL")

    if url:
        parsed = urlparse(str(url))
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


@pytest.fixture(scope="session")
def database_config() -> dict[str, str | int]:
    return _database_config()


@pytest.fixture(scope="session")
def database_connection(database_config):
    psycopg = pytest.importorskip("psycopg")
    try:
        connection = psycopg.connect(
            host=database_config["host"],
            port=database_config["port"],
            dbname=database_config["database"],
            user=database_config["user"],
            password=database_config["password"],
            connect_timeout=3,
        )
    except psycopg.Error as error:
        pytest.skip(f"PostgreSQL is unavailable: {error.__class__.__name__}")

    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def schema():
    def table(*columns: str) -> dict:
        return {"columns": [{"column_name": column} for column in columns]}

    return {
        "tables": {
            "marketing_campaigns": table(
                "campaign_id",
                "campaign_name",
                "actual_spend",
                "revenue_generated",
                "conversions",
                "clicks",
            ),
            "returns": table(
                "return_id",
                "return_reason",
                "return_status",
                "resolution_type",
                "return_date",
            ),
            "orders": table("order_id"),
            "customers": table("customer_id", "customer_name"),
        }
    }


class StaticSchemaLoader:
    def __init__(self, schema):
        self.schema = schema

    def load_schema(self):
        return self.schema


@pytest.fixture
def schema_loader(schema):
    return StaticSchemaLoader(schema)
