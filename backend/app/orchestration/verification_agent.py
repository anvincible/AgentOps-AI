import re
from typing import Any

from backend.app.orchestration.answer_composer import AnswerComposer


class VerificationAgent:
    """Check that composed answers are reproducible from their evidence."""

    RANKING_METRICS = {
        "TOP_PRODUCTS_BY_QUANTITY": "units_sold",
        "TOP_PRODUCTS_BY_REVENUE": "total_revenue",
        "CAMPAIGN_RANKING": "roi_percent",
        "CAMPAIGN_ROI": "roi_percent",
        "SELLER_PERFORMANCE": "total_revenue",
    }

    def __init__(self) -> None:
        self.composer = AnswerComposer()

    def verify(
        self,
        answer: str,
        route: str,
        sql_result: dict[str, Any] | None = None,
        rag_result: dict[str, Any] | None = None,
        question: str = "",
    ) -> dict[str, Any]:
        issues: list[str] = []
        checks: list[str] = []

        if not answer or not answer.strip():
            issues.append("The answer is empty.")
        else:
            checks.append("Answer is non-empty.")

        if route == "CHAT":
            checks.append("No factual data claim requires external evidence.")
        elif route == "CLARIFY":
            if "?" in answer:
                checks.append("The response requests clarification without asserting facts.")
            else:
                issues.append("Clarification response does not ask a question.")
        elif route in {"SQL", "BOTH"}:
            self._verify_sql(answer, sql_result, route, question, checks, issues)

        if route in {"RAG", "BOTH"}:
            self._verify_rag(answer, rag_result, route, question, checks, issues)

        if route == "BOTH" and sql_result and rag_result:
            expected = self.composer.compose({
                "route": "BOTH",
                "question": question,
                "sql": sql_result,
                "rag": rag_result,
            })
            if answer != expected:
                issues.append("Hybrid answer contains claims outside the composed SQL rows and retrieved excerpts.")
            else:
                checks.append("Hybrid answer is exactly composed from SQL rows and retrieved excerpts.")

        if route not in {"CHAT", "CLARIFY", "SQL", "RAG", "BOTH"}:
            issues.append(f"Unknown route: {route}")

        return {
            "verified": not issues,
            "route": route,
            "checks": checks,
            "issues": issues,
        }

    def _verify_sql(
        self,
        answer: str,
        sql_result: dict[str, Any] | None,
        route: str,
        question: str,
        checks: list[str],
        issues: list[str],
    ) -> None:
        if not sql_result:
            issues.append("SQL evidence is unavailable.")
            return

        validation = sql_result.get("validation")
        if validation is None:
            issues.append("SQL validation evidence is unavailable.")
        elif not validation.get("valid", False):
            issues.append("SQL evidence did not pass SQL validation.")
        else:
            checks.append("SQL query passed validation.")

        rows = (sql_result.get("result") or {}).get("rows", [])
        if not rows:
            issues.append("SQL route returned no result rows.")
        else:
            expected = self.composer.compose({
                "route": route,
                "question": question,
                "sql": sql_result,
                "rag": {},
            }) if route == "SQL" else self.composer._compose_sql(
                sql_result, sql_result.get("query_plan", {})
            )
            actual_sql_answer = answer
            if route == "BOTH":
                actual_sql_answer = self.composer._compose_sql(
                    sql_result, sql_result.get("query_plan", {})
                )
                if actual_sql_answer not in answer:
                    # Hybrid composition uses a table-like bullet stream; test
                    # each SQL claim against the deterministic SQL rendering.
                    missing = [
                        line for line in expected.splitlines()
                        if line.startswith("- **") and line not in answer
                    ]
                    if missing:
                        issues.append("A SQL claim is not reproduced by the returned rows.")
                    else:
                        checks.append("SQL claims match returned rows.")
                else:
                    checks.append("SQL claims match returned rows.")
            elif answer != expected:
                issues.append("SQL answer contains a claim or value not reproduced from returned rows.")
            else:
                checks.append("SQL answer values match the returned rows.")

            plan = sql_result.get("query_plan", {})
            metric = self.RANKING_METRICS.get(plan.get("intent"))
            if metric:
                sql = str(sql_result.get("sql", ""))
                columns = (sql_result.get("result") or {}).get("columns", [])
                order_match = re.search(
                    r"\bORDER\s+BY\b(.*?)(?:LIMIT\b|;|$)",
                    sql,
                    re.IGNORECASE | re.DOTALL,
                )
                if not order_match:
                    issues.append("Ranking SQL has no ORDER BY clause.")
                elif not re.search(
                    rf"\b{re.escape(metric)}\b\s+DESC\b",
                    order_match.group(1),
                    re.IGNORECASE,
                ):
                    issues.append(f"Ranking SQL does not sort by {metric} descending.")
                elif metric not in columns:
                    issues.append(f"Ranking result is missing metric {metric}.")
                else:
                    index = columns.index(metric)
                    try:
                        values = [float(row[index]) for row in rows]
                    except (TypeError, ValueError, IndexError):
                        issues.append("Ranking metric values could not be checked.")
                    else:
                        if values != sorted(values, reverse=True):
                            issues.append("Ranking rows are not ordered by the expected metric.")
                        else:
                            checks.append(f"Ranking rows are ordered by {metric}.")

    def _verify_rag(
        self,
        answer: str,
        rag_result: dict[str, Any] | None,
        route: str,
        question: str,
        checks: list[str],
        issues: list[str],
    ) -> None:
        evidence = (rag_result or {}).get("evidence", [])
        if not evidence:
            issues.append("RAG route returned no document evidence.")
            return

        expected = self.composer._compose_rag(rag_result or {}, question)
        if route == "RAG":
            matches = answer == expected
        else:
            marker = "**Supporting Document Evidence**"
            body = answer.split(marker, 1)[1].strip() if marker in answer else ""
            expected_body = expected
            intro = "Based on the available documents:"
            if expected_body.startswith(intro):
                expected_body = expected_body[len(intro):].strip()
            matches = bool(body) and body == expected_body

        if not matches:
            issues.append("RAG answer contains content not reproduced from retrieved excerpts.")
        else:
            checks.append("RAG answer text matches retrieved excerpts.")

        selected = self.composer.select_relevant_evidence(evidence, question)
        missing_facets = self.composer._missing_document_facets(
            question, selected
        )
        if missing_facets:
            issues.append(
                "Requested document coverage is incomplete: "
                + ", ".join(missing_facets)
                + "."
            )
        else:
            requested_facets = self.composer._requested_document_facets(question)
            if requested_facets:
                checks.append("Every explicitly requested document facet is represented.")

        missing_aspects = self.composer._missing_material_aspects(
            question, selected
        )
        if missing_aspects:
            issues.append(
                "Retrieved evidence does not support every requested material aspect: "
                + ", ".join(missing_aspects)
                + "."
            )

        source_rows = (rag_result or {}).get("sources", [])
        source_keys = {
            (item.get("document_id"), item.get("chunk_id"))
            for item in source_rows
        }
        for item in selected:
            key = (item.get("document_id"), item.get("chunk_id"))
            if not key[0] or not key[1] or key not in source_keys:
                issues.append("A cited document reference does not match retrieved source metadata.")
                break
        else:
            if selected:
                checks.append("Document references match retrieved document and chunk IDs.")
            else:
                issues.append("No substantive retrieved excerpt supports the answer.")
