from typing import Any

import psycopg


class DatabaseSchemaLoader:
    """
    Loads the schema of the NovaMart PostgreSQL database.

    The loader retrieves:
    - tables
    - columns
    - data types
    - primary keys
    - foreign keys
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "novamart",
        user: str = "postgres",
        password: str = "",
    ):
        if not password:
            try:
                from backend.app.database_config import load_database_config
                cfg = load_database_config()
                password = str(cfg.get("password") or "")
                if host == "localhost" and cfg.get("host"):
                    host = str(cfg["host"])
                if port == 5432 and cfg.get("port"):
                    port = int(cfg["port"])
                if database == "novamart" and cfg.get("database"):
                    database = str(cfg["database"])
                if user == "postgres" and cfg.get("user"):
                    user = str(cfg["user"])
            except Exception:
                pass

        self.connection_string = (
            f"host={host} "
            f"port={port} "
            f"dbname={database} "
            f"user={user} "
            f"password={password}"
        )

    def get_tables(self) -> list[str]:
        """
        Return all user-defined tables in the public schema.
        """

        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return [row[0] for row in rows]

    def get_columns(self, table_name: str) -> list[dict[str, Any]]:
        """
        Return column information for a specific table.
        """

        query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
        """

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (table_name,))
                rows = cursor.fetchall()

        return [
            {
                "column_name": row[0],
                "data_type": row[1],
                "is_nullable": row[2],
            }
            for row in rows
        ]

    def get_primary_keys(self) -> dict[str, list[str]]:
        """
        Return primary key columns for all tables.
        """

        query = """
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.ordinal_position;
        """

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        primary_keys: dict[str, list[str]] = {}

        for table_name, column_name in rows:
            primary_keys.setdefault(table_name, []).append(column_name)

        return primary_keys

    def get_foreign_keys(self) -> list[dict[str, str]]:
        """
        Return foreign-key relationships between tables.
        """

        query = """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY
            tc.table_name,
            kcu.column_name;
        """

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return [
            {
                "source_table": row[0],
                "source_column": row[1],
                "target_table": row[2],
                "target_column": row[3],
            }
            for row in rows
        ]

    def load_schema(self) -> dict[str, Any]:
        """
        Load the complete NovaMart database schema.
        """

        tables = self.get_tables()
        primary_keys = self.get_primary_keys()
        foreign_keys = self.get_foreign_keys()

        schema: dict[str, Any] = {
            "database": "novamart",
            "tables": {},
            "foreign_keys": foreign_keys,
        }

        for table_name in tables:
            schema["tables"][table_name] = {
                "columns": self.get_columns(table_name),
                "primary_keys": primary_keys.get(table_name, []),
            }

        return schema