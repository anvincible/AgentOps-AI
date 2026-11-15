"""Evidence-grounded, deterministic business analysis over validated SQL rows."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class AnalysisAgent:
    """Summarize and compare SQL evidence without issuing database queries."""

    MONEY_FIELDS = {
        "total_revenue", "revenue_generated", "actual_spend", "total_spend",
        "average_order_value", "average_lifetime_value", "total_lifetime_value",
        "total_payment_amount", "average_payment_amount", "attributed_revenue",
        "average_price", "lowest_price", "highest_price",
    }
    LABEL_FIELDS = (
        "sales_month", "month", "period", "product_name", "category",
        "brand", "campaign_name", "campaign_id", "seller_name", "region",
        "customer_segment", "loyalty_tier", "acquisition_channel", "method",
    )
    METRIC_FIELDS = (
        "total_revenue", "revenue_generated", "total_spend", "actual_spend",
        "average_order_value", "order_count", "customer_count",
        "return_rate_percent", "roi_percent", "units_sold", "count",
        "return_count", "campaign_count", "conversions", "clicks", "ticket_count",
    )

    def analyze(
        self, sql_result: dict[str, Any] | None, question: str = "",
        rag_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze only a successful, validated SQL result; never query SQL."""
        rag_sources = [
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "filename": item.get("filename"),
            }
            for item in (rag_result or {}).get("sources", [])
        ]
        if not isinstance(sql_result, dict):
            return self._insufficient(
                "Structured SQL evidence is unavailable; document excerpts are not treated as numeric data.",
                evidence={"validated": False, "row_count": 0, "document_sources": rag_sources},
            )
        validation = sql_result.get("validation")
        result = sql_result.get("result") or {}
        columns = result.get("columns") or []
        rows = result.get("rows") or []
        if not isinstance(validation, dict) or not validation.get("valid"):
            return self._insufficient("The SQL evidence did not pass validation.")
        if not columns or not rows:
            return self._insufficient("The validated SQL result contains no rows to analyze.")

        records = [self._record(columns, row) for row in rows]
        records = [record for record in records if record]
        if not records:
            return self._insufficient("The SQL result could not be mapped to named columns.")

        plan = sql_result.get("query_plan") or {}
        intent = str(plan.get("intent") or "UNKNOWN")
        question_lower = question.casefold()
        evidence = {
            "source": "NovaMart PostgreSQL database",
            "query_intent": intent,
            "validated": True,
            "row_count": len(records),
            "fields": list(columns),
            "document_sources": rag_sources,
        }
        insights: list[str] = []
        limitations: list[str] = []
        chart = None

        if self._is_monthly(records):
            records.sort(key=lambda row: self._label(row.get("sales_month", row.get("month"))))
        if self._is_monthly(records) and not self._asks_comparison(question_lower):
            metric = self._select_metric(records, question_lower)
            if metric:
                chart = self._chart(records, metric, "line")
                if len(records) >= 3:
                    first, last = self._number(records[0].get(metric)), self._number(records[-1].get(metric))
                    if first is not None and last is not None:
                        change = last - first
                        pct = self._percent_change(first, last)
                        direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
                        if pct is None:
                            insights.append(
                                f"{metric.replace('_', ' ').title()} {direction} from "
                                f"{self._display(first, metric)} in {records[0].get('sales_month', records[0].get('month'))} "
                                f"to {self._display(last, metric)} in {records[-1].get('sales_month', records[-1].get('month'))}; "
                                "a percentage change is undefined because the starting value is zero."
                            )
                        else:
                            insights.append(
                                f"{metric.replace('_', ' ').title()} {direction} from "
                                f"{self._display(first, metric)} to {self._display(last, metric)} "
                                f"(change: {self._display(abs(change), metric)}) "
                                f"across the returned months ({abs(pct):,.2f}% change)."
                            )
                else:
                    note = "A monthly chart is available, but at least three observations are required to characterize a trend."
                    insights.append(note)
                    limitations.append(note)
        elif len(records) >= 2 and self._asks_comparison(question_lower):
            metric = self._select_metric(records, question_lower)
            label_field = self._select_label(records)
            if metric and label_field:
                chart = self._chart(records[:10], metric, "bar", label_field)
                left, right = records[0], records[1]
                before, after = self._number(left.get(metric)), self._number(right.get(metric))
                if before is not None and after is not None:
                    change, pct = after - before, self._percent_change(before, after)
                    left_label, right_label = str(left.get(label_field)), str(right.get(label_field))
                    direction = "higher" if change > 0 else "lower" if change < 0 else "the same"
                    pct_text = (
                        f" ({abs(pct):,.2f}%)" if pct is not None
                        else " (percentage change undefined because the comparison value is zero)"
                    )
                    insights.append(
                        f"{right_label} has {self._display(abs(change), metric)} {direction} {metric.replace('_', ' ')} "
                        f"than {left_label}{pct_text}; values: {left_label} {self._display(before, metric)}, "
                        f"{right_label} {self._display(after, metric)}."
                    )
        else:
            # KPI values are only reported when they are present in the returned rows.
            if len(records) == 1:
                record = records[0]
                for field in dict.fromkeys((*self.METRIC_FIELDS, *sorted(self.MONEY_FIELDS))):
                    if field in record and self._number(record[field]) is not None:
                        label = field.replace("_", " ").title()
                        insights.append(f"{label}: {self._display(self._number(record[field]), field)}.")
                spend = self._number(record.get("actual_spend", record.get("total_spend")))
                revenue = self._number(record.get("revenue_generated", record.get("total_revenue")))
                if (spend is not None and revenue is not None and spend != 0
                        and "roi_percent" not in record):
                    roi = (revenue - spend) / spend * 100
                    insights.append(f"ROI (revenue less spend, divided by spend): {roi:,.2f}%.")
                if ("return_rate_percent" in record and "impact" in question_lower
                        and not any(field in record for field in ("return_cost", "refund_amount", "lost_revenue"))):
                    note = "These rows measure return incidence only; financial business impact cannot be quantified from the returned fields."
                    insights.append(note)
                    limitations.append(note)
            metric = self._select_metric(records, question_lower)
            label_field = self._select_label(records)
            if len(records) > 1 and metric and label_field:
                chart = self._chart(records[:10], metric, "bar", label_field)

        if not insights and not chart:
            return self._insufficient(
                "The returned evidence does not contain enough compatible values for a business analysis.",
                evidence=evidence,
            )

        summary = (
            "Analysis is limited to the validated SQL rows shown with this answer. "
            "No values or missing time periods were inferred."
        )
        return {
            "status": "complete",
            "summary": summary,
            "insights": insights,
            "chart": chart,
            "evidence": evidence,
            "limitations": limitations,
        }

    @staticmethod
    def _insufficient(message: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "insufficient_evidence",
            "summary": message,
            "insights": [],
            "chart": None,
            "evidence": evidence or {"validated": False, "row_count": 0},
            "limitations": [message],
        }

    @staticmethod
    def _record(columns: list[Any], row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return {str(key).lower(): value for key, value in row.items()}
        try:
            return {str(column).lower(): value for column, value in zip(columns, row)}
        except TypeError:
            return {}

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            number = float(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            return None
        return number if number == number and abs(number) != float("inf") else None

    @classmethod
    def _is_monthly(cls, records: list[dict[str, Any]]) -> bool:
        return len(records) >= 1 and all(
            "sales_month" in row or "month" in row for row in records
        )

    @classmethod
    def _select_metric(cls, records: list[dict[str, Any]], question: str) -> str | None:
        available = set.intersection(*(set(record) for record in records)) if records else set()
        preferences = []
        if "roi" in question:
            preferences.append("roi_percent")
        if "return" in question or "refund" in question:
            preferences.append("return_rate_percent")
        if "order" in question:
            preferences.extend(("order_count", "average_order_value"))
        if "customer" in question:
            preferences.append("customer_count")
        if "quantity" in question or "units" in question:
            preferences.append("units_sold")
        if "spend" in question:
            preferences.extend(("total_spend", "actual_spend"))
        preferences.extend(cls.METRIC_FIELDS)
        return next((field for field in preferences if field in available), None)

    @classmethod
    def _select_label(cls, records: list[dict[str, Any]]) -> str | None:
        available = set.intersection(*(set(record) for record in records)) if records else set()
        return next((field for field in cls.LABEL_FIELDS if field in available), None)

    @staticmethod
    def _asks_comparison(question: str) -> bool:
        return any(word in question for word in ("compare", "comparison", "versus", " vs ", "difference"))

    @staticmethod
    def _percent_change(before: float, after: float) -> float | None:
        return None if before == 0 else (after - before) / abs(before) * 100

    @classmethod
    def _chart(
        cls, records: list[dict[str, Any]], metric: str, chart_type: str,
        label_field: str | None = None,
    ) -> dict[str, Any] | None:
        labels, values = [], []
        for index, record in enumerate(records):
            value = cls._number(record.get(metric))
            label_value = record.get(label_field) if label_field else record.get("sales_month", record.get("month"))
            if value is None or label_value is None:
                continue
            labels.append(cls._label(label_value))
            values.append(round(value, 6))
        if not values:
            return None
        return {
            "type": chart_type,
            "metric": metric,
            "labels": labels,
            "series": [{"name": metric.replace("_", " ").title(), "values": values}],
        }

    @staticmethod
    def _label(value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value)

    @classmethod
    def _display(cls, value: float, field: str) -> str:
        if field in cls.MONEY_FIELDS:
            return f"₹{value:,.2f}"
        if field.endswith("_percent") or field == "roi_percent":
            return f"{value:,.2f}%"
        return f"{value:,.2f}".rstrip("0").rstrip(".")
