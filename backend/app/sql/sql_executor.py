from typing import Any

import psycopg


class SQLExecutor:
    """
    Executes validated read-only SQL queries
    against the NovaMart PostgreSQL database.

    Phase 3.4 responsibilities:
    - Connect to PostgreSQL
    - Execute SELECT queries
    - Return column names and rows
    - Limit the number of returned rows
    - Close the database connection safely
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "novamart",
        user: str = "postgres",
        password: str = "",
        max_rows: int = 100,
    ):
        self.connection_string = (
            f"host={host} "
            f"port={port} "
            f"dbname={database} "
            f"user={user} "
            f"password={password}"
        )

        self.max_rows = max_rows

    def execute(
        self, sql: str, params: tuple[Any, ...] | list[Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a SELECT query and return the results.

        Returns:
            {
                "columns": [...],
                "rows": [...],
                "row_count": int
            }
        """

        if not sql or not sql.strip():
            raise ValueError("SQL query cannot be empty.")

        cleaned_sql = sql.strip()

        # ---------------------------------------------------------
        # Safety check
        # ---------------------------------------------------------

        if not cleaned_sql.upper().startswith("SELECT"):
            raise ValueError(
                "SQLExecutor only allows SELECT queries."
            )

        # ---------------------------------------------------------
        # Connect and execute
        # ---------------------------------------------------------

        with psycopg.connect(self.connection_string) as connection:

            with connection.cursor() as cursor:

                cursor.execute(cleaned_sql, params or ())

                rows = cursor.fetchmany(self.max_rows)

                columns = [
                    description.name
                    for description in cursor.description
                ]

        return {
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
        }
