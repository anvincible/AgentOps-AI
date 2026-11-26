"""CSV report renderer for AgentOps AI.
Exports structured tabular report data to UTF-8 CSV with RFC 4180 compliance.
"""

from __future__ import annotations

import csv
import io
from typing import Any

try:
    from backend.app.reporting.models import ReportDocument
except ImportError:
    from app.reporting.models import ReportDocument


class CsvRenderer:
    """Renders tabular data from a ReportDocument into CSV format."""

    def render(self, doc_data: ReportDocument) -> bytes:
        """Render the primary table or KPI scorecard of a ReportDocument into CSV bytes."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Meta Header
        writer.writerow([f"# AgentOps AI Report: {doc_data.title}"])
        writer.writerow([f"# Scope: NovaMart Enterprise | Period: {doc_data.period.value} | Generated: {doc_data.generated_at.isoformat()}"])
        writer.writerow([])

        if doc_data.tables:
            # Export primary table
            for idx, tbl in enumerate(doc_data.tables):
                writer.writerow([f"# SECTION: {tbl.title}"])
                writer.writerow(tbl.columns)
                for row in tbl.rows:
                    writer.writerow(row)
                writer.writerow([])
        elif doc_data.kpi_cards:
            # Fallback to KPI cards
            writer.writerow(["# SECTION: Key Performance Indicators"])
            writer.writerow(["Metric", "Value", "Subtitle", "Change"])
            for kpi in doc_data.kpi_cards:
                writer.writerow([kpi.label, kpi.value, kpi.subtitle or "", kpi.change or ""])

        # UTF-8 with BOM for clean loading in Microsoft Excel
        return output.getvalue().encode("utf-8-sig")
