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
        status = "complete"

        campaign_comparison = (
            "campaign" in question_lower and self._asks_comparison(question_lower)
        )

        if self._is_monthly(records):
            records.sort(key=lambda row: self._label(row.get("sales_month", row.get("month"))))
        if campaign_comparison and len(records) > 2:
            return self._insufficient(
                "Campaign comparison supports exactly two separately identified campaigns; "
                "the supplied SQL result contains more than two.",
                evidence=evidence,
            )
        if campaign_comparison and len(records) == 2:
            campaign_ids = [record.get("campaign_id") for record in records]
            if not all(campaign_ids) or str(campaign_ids[0]) == str(campaign_ids[1]):
                return self._insufficient(
                    "Campaign comparison requires exactly two distinct campaign IDs.",
                    evidence=evidence,
                )
            chart, insights = self._compare_campaigns(records)
        elif self._is_monthly(records) and not self._asks_comparison(question_lower):
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
            if campaign_comparison:
                note = (
                    "Campaign-to-campaign comparison is unavailable: the SQL result "
                    "contains aggregate metrics, not separate labeled campaign rows."
                )
                insights.append(note)
                limitations.append(note)
                status = "partial"

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
            "status": status,
            "summary": summary,
            "insights": insights,
            "chart": chart,
            "evidence": evidence,
            "limitations": limitations,
        }

    @classmethod
    def _compare_campaigns(
        cls, records: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, list[str]]:
        labels = [
            f"{row['campaign_id']} — {row.get('campaign_name')}"
            if row.get("campaign_name")
            else str(row["campaign_id"])
            for row in records
        ]
        metric_fields = ("actual_spend", "revenue_generated", "conversions", "clicks")
        series = []
        insights = []
        for field in metric_fields:
            values = [cls._number(row.get(field)) for row in records]
            if any(value is None for value in values):
                continue
            numeric_values = [value for value in values if value is not None]
            series.append({
                "name": field.replace("_", " ").title(),
                "metric": field,
                "values": [round(value, 6) for value in numeric_values],
            })
            first, second = numeric_values[0], numeric_values[1]
            change = second - first
            pct = cls._percent_change(first, second)
            direction = "higher" if change > 0 else "lower" if change < 0 else "the same"
            pct_text = (
                f" ({abs(pct):,.2f}%)" if pct is not None
                else " (percentage change undefined because the first value is zero)"
            )
            insights.append(
                f"{labels[1]} has {cls._display(abs(change), field)} {direction} {field.replace('_', ' ')} "
                f"than {labels[0]}{pct_text}; values: {labels[0]} {cls._display(first, field)}, "
                f"{labels[1]} {cls._display(second, field)}."
            )
        chart = ({
            "type": "bar",
            "metric": "campaign_metrics",
            "labels": labels,
            "series": series,
        } if series else None)
        return chart, insights

    def analyze_business_summary(
        self,
        validated_results: list[dict[str, Any]],
        unavailable_areas: list[str] | None = None,
    ) -> dict[str, Any]:
        """Summarize selected KPI families from existing validated SQL results."""
        area_order = ("Sales", "Customers", "Returns", "Campaigns")
        by_intent = {
            "SALES_SUMMARY": "Sales",
            "CUSTOMER_COUNT": "Customers",
            "RETURN_RATE": "Returns",
            "CAMPAIGN_PERFORMANCE": "Campaigns",
            "CAMPAIGN_SUMMARY": "Campaigns",
        }
        fields_by_area = {
            "Sales": ("order_count", "total_revenue", "average_order_value"),
            "Customers": ("customer_count",),
            "Returns": ("return_count", "order_count", "return_rate_percent"),
            "Campaigns": (
                "campaign_count", "total_spend", "total_revenue",
                "total_conversions", "total_clicks",
            ),
        }
        area_metrics: dict[str, dict[str, Any]] = {}
        area_missing_fields: dict[str, list[str]] = {}
        evidence_items: list[dict[str, Any]] = []
        for item in validated_results:
            result = item.get("result") if isinstance(item, dict) else None
            if not isinstance(result, dict) or not (item.get("validation") or {}).get("valid"):
                continue
            columns, rows = result.get("columns") or [], result.get("rows") or []
            if not columns or not rows:
                continue
            plan = item.get("query_plan") or {}
            intent = str(plan.get("intent") or "UNKNOWN")
            area = by_intent.get(intent)
            if not area:
                continue
            record = self._record(columns, rows[0])
            expected_fields = fields_by_area[area]
            values = {
                field: self._number(record.get(field))
                for field in expected_fields if field in record
            }
            values = {field: value for field, value in values.items() if value is not None}
            if not values:
                area_missing_fields[area] = list(expected_fields)
                continue
            area_metrics[area] = values
            area_missing_fields[area] = [
                field for field in expected_fields if field not in values
            ]
            if (
                area == "Campaigns"
                and values.get("total_spend") == 0
                and "total_revenue" in values
            ):
                area_missing_fields[area].append("roi_zero_spend")
            evidence_items.append({
                "area": area,
                "query_intent": intent,
                "validated": True,
                "row_count": len(rows),
                "fields": list(columns),
                "values": values,
            })

        insights: list[str] = []
        for area in area_order:
            values = area_metrics.get(area)
            if not values:
                continue
            parts = [
                f"{field.replace('_', ' ').title()}: {self._display(value, field)}"
                for field, value in values.items()
            ]
            if area == "Campaigns":
                spend = values.get("total_spend")
                revenue = values.get("total_revenue")
                if spend is not None and revenue is not None and spend != 0:
                    roi = (revenue - spend) / spend * 100
                    parts.append(f"ROI: {roi:,.2f}%")
            insights.append(f"{area}: " + "; ".join(parts) + ".")

        unavailable = list(dict.fromkeys(unavailable_areas or []))
        unavailable.extend(area for area in area_order if area not in area_metrics and area not in unavailable)
        limitations = [f"KPI evidence unavailable for: {', '.join(unavailable)}."] if unavailable else []
        for area in area_order:
            missing = area_missing_fields.get(area, [])
            if not missing or area not in area_metrics:
                continue
            if "roi_zero_spend" in missing:
                limitations.append("Campaign ROI could not be calculated because aggregate campaign spend is zero.")
                missing = [field for field in missing if field != "roi_zero_spend"]
            if missing:
                limitations.append(
                    f"{area} KPI fields unavailable: "
                    + ", ".join(field.replace("_", " ") for field in missing)
                    + "."
                )
        covered = [area for area in area_order if area in area_metrics]
        coverage = []
        for area in area_order:
            if area not in area_metrics:
                area_status = "unavailable"
            elif area_missing_fields.get(area):
                area_status = "partial"
            else:
                area_status = "covered"
            coverage.append({"area": area, "status": area_status})
        status = (
            "complete" if all(item["status"] == "covered" for item in coverage)
            else "partial" if covered else "insufficient_evidence"
        )
        return {
            "status": status,
            "summary": (
                f"Retrieved some KPI evidence for {len(covered)} of {len(area_order)} requested business areas; "
                f"{sum(item['status'] == 'covered' for item in coverage)} areas have complete KPI coverage."
            ),
            "insights": insights,
            "chart": None,
            "coverage": coverage,
            "evidence": {
                "source": "NovaMart PostgreSQL database",
                "validated": bool(evidence_items) and len(evidence_items) == len(covered),
                "row_count": sum(item["row_count"] for item in evidence_items),
                "query_intents": [item["query_intent"] for item in evidence_items],
                "results": evidence_items,
                "document_sources": [],
            },
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
