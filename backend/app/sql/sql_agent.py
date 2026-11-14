from typing import Any

from backend.app.sql.schema_inspector import DatabaseSchemaLoader
from backend.app.sql.sql_reasoner import SQLReasoner
from backend.app.sql.sql_generator import SQLGenerator
from backend.app.sql.sql_validator import SQLValidator
from backend.app.sql.sql_executor import SQLExecutor


class SQLAgent:
    """
    Complete SQL question-answering pipeline.

    Flow:

        Natural-language question
                    ↓
             SQL Reasoner
                    ↓
              Query Plan
                    ↓
             SQL Generator
                    ↓
             SQL Validator
                    ↓
             SQL Executor
                    ↓
              Database Result
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
        # ---------------------------------------------------------
        # Database schema
        # ---------------------------------------------------------

        self.schema_loader = DatabaseSchemaLoader(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

        # ---------------------------------------------------------
        # Reasoner
        # ---------------------------------------------------------

        self.reasoner = SQLReasoner(
            self.schema_loader
        )

        # ---------------------------------------------------------
        # SQL Generator
        # ---------------------------------------------------------

        self.generator = SQLGenerator(
            self.schema_loader
        )

        # ---------------------------------------------------------
        # SQL Validator
        # ---------------------------------------------------------

        self.schema = self.generator.get_schema()

        self.validator = SQLValidator(
            self.schema
        )

        # ---------------------------------------------------------
        # SQL Executor
        # ---------------------------------------------------------

        self.executor = SQLExecutor(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            max_rows=max_rows,
        )

    def answer(self, question: str) -> dict[str, Any]:
        """
        Process a natural-language question through the
        complete SQL pipeline.
        """

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        # ---------------------------------------------------------
        # Step 1: Reason about the question
        # ---------------------------------------------------------

        query_plan = self.reasoner.reason(question)

        # ---------------------------------------------------------
        # Step 2: Generate SQL
        # ---------------------------------------------------------

        generated_sql, query_params = self.generator.generate_query(
            query_plan
        )

        # ---------------------------------------------------------
        # Step 3: Validate SQL
        # ---------------------------------------------------------

        validation_result = self.validator.validate(
            generated_sql
        )

        if not validation_result["valid"]:
            raise ValueError(
                "Generated SQL failed validation: "
                f"{validation_result['errors']}"
            )

        # ---------------------------------------------------------
        # Step 4: Execute SQL
        # ---------------------------------------------------------

        execution_result = self.executor.execute(generated_sql, query_params)

        # ---------------------------------------------------------
        # Step 5: Return complete pipeline result
        # ---------------------------------------------------------

        return {
            "question": question,
            "query_plan": query_plan,
            "sql": generated_sql,
            "sql_params": query_params,
            "validation": validation_result,
            "result": execution_result,
        }
