from typing import Any


class VerificationAgent:
    """
    Performs basic deterministic checks on composed answers.

    This first version checks for a non-empty answer and verifies
    that SQL/RAG routes have corresponding evidence where required.
    It does not claim to prove the truth of every answer statement.
    """

    def verify(
        self,
        answer: str,
        route: str,
        sql_result: dict[str, Any] | None = None,
        rag_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        checks: list[str] = []

        if not answer or not answer.strip():
            issues.append("The answer is empty.")
        else:
            checks.append("Answer is non-empty.")

        if route == "CHAT":
            checks.append("Greeting route does not require database evidence.")

        elif route == "SQL":
            result = (sql_result or {}).get("result", {})
            rows = result.get("rows", [])

            if rows:
                checks.append("SQL evidence contains result rows.")
            else:
                issues.append("SQL route returned no result rows.")

        elif route == "RAG":
            evidence = (rag_result or {}).get("evidence", [])

            if evidence:
                checks.append("RAG evidence contains retrieved documents.")
            else:
                issues.append("RAG route returned no document evidence.")

        elif route == "BOTH":
            sql_data = (sql_result or {}).get("result", {})
            sql_rows = sql_data.get("rows", [])
            rag_evidence = (rag_result or {}).get("evidence", [])

            if sql_rows:
                checks.append("Hybrid answer contains SQL result rows.")
            else:
                issues.append("Hybrid route returned no SQL result rows.")

            if rag_evidence:
                checks.append("Hybrid answer contains document evidence.")
            else:
                issues.append("Hybrid route returned no document evidence.")

        else:
            issues.append(f"Unknown route: {route}")

        return {
            "verified": len(issues) == 0,
            "route": route,
            "checks": checks,
            "issues": issues,
        }
