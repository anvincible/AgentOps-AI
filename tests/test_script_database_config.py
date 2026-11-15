"""Static and mocked checks for database helper-script configuration."""

import ast
from pathlib import Path

import pytest

from backend.app import database_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_FILES = (
    "test_rag_agent.py",
    "test_reasoner_generator.py",
    "test_retriever.py",
    "test_schema_inspector.py",
    "test_sql_agent.py",
    "test_sql_agent_cases.py",
    "test_sql_executor.py",
    "test_sql_pipeline.py",
    "test_vector_store.py",
)
CONNECTION_CONSTRUCTORS = {
    "RAGAgent",
    "DatabaseSchemaLoader",
    "Retriever",
    "SQLAgent",
    "SQLExecutor",
    "VectorStore",
}
PRESERVED_OPTIONS = {
    "test_rag_agent.py": ("top_k", 5),
    "test_retriever.py": ("top_k", 5),
    "test_sql_agent.py": ("max_rows", 100),
    "test_sql_agent_cases.py": ("max_rows", 100),
    "test_sql_executor.py": ("max_rows", 100),
    "test_sql_pipeline.py": ("max_rows", 100),
}


def _mock_configuration_source(monkeypatch, dotenv_values):
    for name in (
        "DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(database_config, "dotenv_values", lambda _path: dotenv_values)


@pytest.mark.unit
def test_shared_loader_accepts_mocked_settings_without_reading_env_file(monkeypatch):
    mocked_settings = {
        "DB_HOST": "fixture-db",
        "DB_PORT": "5544",
        "DB_NAME": "fixture_novamart",
        "DB_USER": "fixture_user",
        "DB_PASSWORD": "",
    }
    _mock_configuration_source(monkeypatch, mocked_settings)

    result = database_config.load_database_config(require_explicit=True)

    expected = {
        "host": "fixture-db",
        "port": 5544,
        "database": "fixture_novamart",
        "user": "fixture_user",
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise AssertionError("Shared loader did not use all mocked connection settings.")
    if "password" not in result:
        raise AssertionError("Shared loader did not return the password setting.")


@pytest.mark.unit
def test_shared_loader_raises_safe_error_when_configuration_is_missing(monkeypatch):
    _mock_configuration_source(monkeypatch, {})

    with pytest.raises(
        ValueError,
        match="Database configuration is missing or incomplete",
    ) as error:
        database_config.load_database_config(require_explicit=True)

    if "password" in str(error.value).lower():
        raise AssertionError("Missing-configuration error must not reveal credential details.")


@pytest.mark.unit
def test_shared_loader_preserves_environment_precedence(monkeypatch):
    _mock_configuration_source(monkeypatch, {
        "DB_HOST": "dotenv-host",
        "DB_PORT": "5432",
        "DB_NAME": "fixture_novamart",
        "DB_USER": "fixture_user",
    })
    monkeypatch.setenv("DB_HOST", "environment-host")

    result = database_config.load_database_config(require_explicit=True)

    if result.get("host") != "environment-host":
        raise AssertionError("Environment settings must continue to override dotenv settings.")


@pytest.mark.unit
def test_default_loader_fallback_behavior_remains_compatible(monkeypatch):
    _mock_configuration_source(monkeypatch, {})

    result = database_config.load_database_config()

    if result.get("host") != "localhost" or result.get("port") != 5432:
        raise AssertionError("Existing default database endpoint behavior changed.")
    if result.get("database") != "novamart" or result.get("user") != "postgres":
        raise AssertionError("Existing default database identity behavior changed.")
    if result.get("password"):
        raise AssertionError("Existing empty-password fallback behavior changed.")


@pytest.mark.unit
def test_all_nine_scripts_use_shared_configuration_without_password_literals():
    for filename in SCRIPT_FILES:
        path = PROJECT_ROOT / "scripts" / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        loader_calls = []
        constructors = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "load_database_config"
                    and any(
                        keyword.arg == "require_explicit"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    )
                ):
                    loader_calls.append(node)

                if isinstance(node.func, ast.Name) and node.func.id in CONNECTION_CONSTRUCTORS:
                    constructors.append(node)
                    if not any(
                        keyword.arg is None
                        and isinstance(keyword.value, ast.Name)
                        and keyword.value.id == "db_config"
                        for keyword in node.keywords
                    ):
                        raise AssertionError(f"{filename}: constructor bypasses shared configuration.")

                    if any(
                        keyword.arg == "password"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                        for keyword in node.keywords
                    ):
                        raise AssertionError(f"{filename}: literal password remains in a constructor.")

            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            if (
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and any(
                    isinstance(target, ast.Name)
                    and target.id.casefold() in {"password", "db_password"}
                    for target in targets
                )
            ):
                raise AssertionError(f"{filename}: literal password assignment remains.")

        if not loader_calls or not constructors:
            raise AssertionError(f"{filename}: expected shared loader or DB constructor was not found.")

        if filename in PRESERVED_OPTIONS:
            option, expected = PRESERVED_OPTIONS[filename]
            if not any(
                isinstance(node, ast.Call)
                and any(
                    keyword.arg == option
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == expected
                    for keyword in node.keywords
                )
                for node in ast.walk(tree)
            ):
                raise AssertionError(f"{filename}: expected {option} option was not preserved.")
