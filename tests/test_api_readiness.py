import logging

import psycopg
import pytest
from fastapi import HTTPException

from backend.app.api import readiness


class _Cursor:
    def __init__(self):
        self.query = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query):
        self.query = query

    def fetchone(self):
        return (1,) if self.query == "SELECT 1" else None


class _Connection:
    def __init__(self):
        self.test_cursor = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.test_cursor


def test_readiness_executes_select_one_with_short_connection_timeout(monkeypatch):
    config = {
        "host": "clean-db",
        "port": 5432,
        "database": "novamart",
        "user": "readonly_user",
        "password": "test-only-password",
    }
    connection = _Connection()
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        return connection

    monkeypatch.setattr(readiness.psycopg, "connect", connect)

    result = readiness.check_database_readiness(config)

    assert result == {"status": "ok", "service": "AgentOps AI"}
    assert connection.test_cursor.query == "SELECT 1"
    assert calls == [{**config, "connect_timeout": 2}]


def test_unhealthy_database_returns_generic_503_and_sanitized_log(
    monkeypatch,
    caplog,
):
    secret_connection_string = "postgresql://reader:secret-value@db/novamart"

    def connect(**_kwargs):
        raise psycopg.OperationalError(
            f"connection failed for {secret_connection_string}"
        )

    monkeypatch.setattr(readiness.psycopg, "connect", connect)

    with caplog.at_level(logging.ERROR, logger=readiness.logger.name):
        with pytest.raises(HTTPException) as error:
            readiness.check_database_readiness({"host": "clean-db"})

    assert error.value.status_code == 503
    assert error.value.detail == "Service is not ready."
    assert "OperationalError" in caplog.text
    assert "Database readiness check failed" in caplog.text
    assert secret_connection_string not in caplog.text
    assert "secret-value" not in caplog.text
