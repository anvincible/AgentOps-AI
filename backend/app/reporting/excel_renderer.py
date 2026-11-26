"""Universal openpyxl Excel Report Renderer for AgentOps AI.
Generates multi-worksheet corporate Excel workbooks with executive styling,
numeric cell formatting (₹ currency, %, #,##0), frozen panes, and structured tables.
"""

from __future__ import annotations

import io
from typing import Any, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.reporting.models import ReportDocument, ReportKpiItem, ReportTable


class OpenPyXLExcelRenderer:
    """Renders enterprise-grade multi-sheet Excel workbooks using openpyxl."""

    def __init__(self) -> None:
        # Corporate Palette
        self.navy_fill = PatternFill(start_color="081426", end_color="081426", fill_type="solid")
        self.subhead_fill = PatternFill(start_color="141C2B", end_color="141C2B", fill_type="solid")
        self.light_gray_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        self.accent_blue_fill = PatternFill(start_color="397BFF", end_color="397BFF", fill_type="solid")
        self.kpi_card_fill = PatternFill(start_color="0D1527", end_color="0D1527", fill_type="solid")

        self.font_title = Font(name="Calibri", size=15, bold=True, color="081426")
        self.font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
        self.font_section = Font(name="Calibri", size=11, bold=True, color="081426")
        self.font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        self.font_body = Font(name="Calibri", size=10, color="1E293B")
        self.font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
        self.font_kpi_val = Font(name="Calibri", size=13, bold=True, color="00CFE8")
        self.font_kpi_label = Font(name="Calibri", size=9, bold=True, color="94A3B8")

        thin_side = Side(border_style="thin", color="CBD5E1")
        self.cell_border = Border(top=thin_side, left=thin_side, right=thin_side, bottom=thin_side)

    def render(self, doc_data: ReportDocument) -> bytes:
        """Render a full ReportDocument model into Excel (.xlsx) byte stream."""
        wb = openpyxl.Workbook()

        # Sheet 1: Executive Summary & Overview
        ws_exec = wb.active
        ws_exec.title = "Executive Summary"
        self._populate_executive_sheet(ws_exec, doc_data)

        # Sheet 2: KPI Scorecard
        if doc_data.kpi_cards:
            ws_kpi = wb.create_sheet(title="KPI Scorecard")
            self._populate_kpi_sheet(ws_kpi, doc_data.kpi_cards)

        # Sheet 3..N: Detailed Tabular Datasets
        if doc_data.tables:
            existing_sheet_titles = set(wb.sheetnames)
            for idx, tbl in enumerate(doc_data.tables):
                t_lower = tbl.title.lower()
                if "capital efficiency" in t_lower or "ranked by roas" in t_lower:
                    short_name = "Campaign Capital Efficiency"
                elif "commercial scale" in t_lower or "ranked by attributed revenue" in t_lower:
                    short_name = "Campaign Commercial Scale"
                elif "channel summary" in t_lower or "media allocation" in t_lower:
                    short_name = "Marketing Channel Summary"
                elif "underperforming" in t_lower or "below portfolio" in t_lower:
                    short_name = "Underperforming Campaigns"
                elif "merchandise category" in t_lower or "revenue contribution by" in t_lower:
                    short_name = "Category Revenue Share"
                elif "return incidence" in t_lower or "return breakdown" in t_lower or "category return" in t_lower:
                    short_name = "Category Returns Breakdown"
                elif "pricing & revenue reconciliation" in t_lower or "pricing reconciliation" in t_lower:
                    short_name = "SKU Pricing Reconciliation"
                elif "skus by net revenue" in t_lower or "skus by gross revenue" in t_lower or "top performing skus" in t_lower:
                    short_name = "Top Performing SKUs"
                elif "monthly sales" in t_lower or "timeline" in t_lower:
                    short_name = "Monthly Timeline Trajectory"
                elif "loyalty tier" in t_lower:
                    short_name = "Customer Loyalty Tiers"
                elif "return drivers" in t_lower:
                    short_name = "Return Drivers Breakdown"
                elif "carrier" in t_lower:
                    short_name = "Carrier SLA Performance"
                else:
                    short_name = tbl.title.replace(":", " ").replace("/", " ").replace("?", "").replace("*", "").replace("[", "").replace("]", "")[:28].strip()

                if short_name in existing_sheet_titles:
                    short_name = f"{short_name[:24]}_{idx+1}"
                existing_sheet_titles.add(short_name)
                ws_tbl = wb.create_sheet(title=short_name or f"Analytics {idx+1}")
                self._populate_table_sheet(ws_tbl, tbl)

        # Sheet: Strategic Insights
        ws_obs = wb.create_sheet(title="Strategic Insights")
        self._populate_observations_sheet(ws_obs, doc_data)

        # Sheet: Methodology & Sources
        ws_prov = wb.create_sheet(title="Audit & Sources")
        self._populate_sources_sheet(ws_prov, doc_data)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    def _auto_fit_columns(self, ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
        """Adjust column widths based on cell content length."""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > 60:
                    max_len = max(max_len, 35)
                else:
                    max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 48)

    def _populate_executive_sheet(self, ws: openpyxl.worksheet.worksheet.Worksheet, doc: ReportDocument) -> None:
        ws.views.sheetView[0].showGridLines = True

        # Header Block
        ws["A1"] = doc.title
        ws["A1"].font = self.font_title

        period_text = doc.period.value.replace("_", " ").title()
        ws["A2"] = f"Reporting Window: {period_text} | NovaMart Enterprise Business Intelligence | Classification: Executive Confidential"
        ws["A2"].font = self.font_subtitle

        ws["A3"] = f"Generated: {doc.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
        ws["A3"].font = Font(name="Calibri", size=9, italic=True, color="94A3B8")

        # Executive Summary Section
        ws["A5"] = "EXECUTIVE SUMMARY & OPERATIONAL CONTEXT"
        ws["A5"].font = self.font_section
        ws["A5"].fill = self.light_gray_fill

        ws["A6"] = str(doc.executive_summary)
        ws["A6"].font = self.font_body
        ws["A6"].alignment = Alignment(wrap_text=True)
        ws.merge_cells("A6:G7")

        # Key Highlights
        if doc.kpi_cards:
            ws["A9"] = "KEY PERFORMANCE SCORECARD HIGHLIGHTS"
            ws["A9"].font = self.font_section

            headers = ["Indicator Name", "Metric Value", "Audit Context", "Directional Status"]
            for col_idx, h in enumerate(headers, 1):
                cell = ws.cell(row=10, column=col_idx, value=h)
                cell.font = self.font_header
                cell.fill = self.navy_fill
                cell.alignment = Alignment(horizontal="center" if col_idx == 2 else "left")

            for row_idx, kpi in enumerate(doc.kpi_cards[:6], 11):
                c1 = ws.cell(row=row_idx, column=1, value=kpi.label)
                c2 = ws.cell(row=row_idx, column=2, value=str(kpi.value))
                c3 = ws.cell(row=row_idx, column=3, value=kpi.subtitle or "Verified Ledger")
                c4 = ws.cell(row=row_idx, column=4, value=kpi.change or "Verified Baseline")

                c1.font = self.font_bold
                c2.font = Font(name="Calibri", size=11, bold=True, color="397BFF")
                c3.font = self.font_subtitle
                c4.font = self.font_body

                c2.alignment = Alignment(horizontal="right")
                for cell in (c1, c2, c3, c4):
                    cell.border = self.cell_border
                    if row_idx % 2 == 0:
                        cell.fill = self.light_gray_fill

        self._auto_fit_columns(ws)

    def _populate_kpi_sheet(self, ws: openpyxl.worksheet.worksheet.Worksheet, kpis: List[ReportKpiItem]) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        headers = ["KPI Indicator", "Primary Metric Value", "Change / Trend", "Verification Context"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = self.font_header
            cell.fill = self.navy_fill
            cell.alignment = Alignment(horizontal="left", vertical="center")

        for row_idx, kpi in enumerate(kpis, 2):
            c1 = ws.cell(row=row_idx, column=1, value=kpi.label)
            c2 = ws.cell(row=row_idx, column=2, value=str(kpi.value))
            c3 = ws.cell(row=row_idx, column=3, value=kpi.change or "Baseline")
            c4 = ws.cell(row=row_idx, column=4, value=kpi.subtitle or "System Ledger")

            c1.font = self.font_bold
            c2.font = Font(name="Calibri", size=11, bold=True, color="081426")
            c3.font = self.font_body
            c4.font = self.font_subtitle

            c2.alignment = Alignment(horizontal="right")

            for cell in (c1, c2, c3, c4):
                cell.border = self.cell_border
                if row_idx % 2 == 1:
                    cell.fill = self.light_gray_fill

        self._auto_fit_columns(ws)

    def _populate_table_sheet(self, ws: openpyxl.worksheet.worksheet.Worksheet, tbl: ReportTable) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        # Headers
        for col_idx, col_name in enumerate(tbl.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = self.font_header
            cell.fill = self.navy_fill
            cell.alignment = Alignment(horizontal="left", vertical="center")

        # Rows
        for row_idx, row_data in enumerate(tbl.rows, 2):
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = self.font_body
                cell.border = self.cell_border

                if row_idx % 2 == 1:
                    cell.fill = self.light_gray_fill

                # Numeric & Currency Formatting
                if isinstance(val, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
                    cell.number_format = "#,##0.00" if isinstance(val, float) else "#,##0"
                elif isinstance(val, str):
                    if val.startswith("₹"):
                        cell.alignment = Alignment(horizontal="right")
                    elif val.endswith("%"):
                        cell.alignment = Alignment(horizontal="right")

        if getattr(tbl, "footnote", None):
            fn_row = len(tbl.rows) + 3
            cell = ws.cell(row=fn_row, column=1, value=tbl.footnote)
            cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")

        self._auto_fit_columns(ws)

    def _populate_observations_sheet(self, ws: openpyxl.worksheet.worksheet.Worksheet, doc: ReportDocument) -> None:
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = "STRATEGIC OBSERVATIONS & EXECUTIVE RECOMMENDATIONS"
        ws["A1"].font = self.font_title

        # Key Findings
        ws["A3"] = "1. VERIFIED BUSINESS FINDINGS"
        ws["A3"].font = self.font_section
        ws["A3"].fill = self.light_gray_fill
        curr_row = 4
        for driver in doc.key_drivers:
            cell = ws.cell(row=curr_row, column=1, value=f"• {driver}")
            cell.font = self.font_body
            curr_row += 1

        # Operational Risks
        curr_row += 1
        ws.cell(row=curr_row, column=1, value="2. OPERATIONAL CONSIDERATIONS & RISKS").font = self.font_section
        ws.cell(row=curr_row, column=1).fill = self.light_gray_fill
        curr_row += 1
        for risk in doc.risk_observations:
            cell = ws.cell(row=curr_row, column=1, value=f"• [Risk] {risk}")
            cell.font = Font(name="Calibri", size=10, color="DC2626")
            curr_row += 1

        # Recommendations
        if doc.recommendations:
            curr_row += 1
            ws.cell(row=curr_row, column=1, value="3. PRESCRIPTIVE STRATEGIC RECOMMENDATIONS").font = self.font_section
            ws.cell(row=curr_row, column=1).fill = self.light_gray_fill
            curr_row += 1
            for idx, rec in enumerate(doc.recommendations, 1):
                cell = ws.cell(row=curr_row, column=1, value=f"{idx}. {rec}")
                cell.font = self.font_bold
                curr_row += 1

        self._auto_fit_columns(ws)

    def _populate_sources_sheet(self, ws: openpyxl.worksheet.worksheet.Worksheet, doc: ReportDocument) -> None:
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A1"] = "DATA INTEGRITY, AUDIT PROVENANCE & METHODOLOGY"
        ws["A1"].font = self.font_title

        ws["A2"] = f"Methodology: {doc.methodology}"
        ws["A2"].font = self.font_body
        ws.merge_cells("A2:F3")
        ws["A2"].alignment = Alignment(wrap_text=True)

        ws["A4"] = "AUTHORITATIVE POLICY & GOVERNANCE CITATIONS"
        ws["A4"].font = self.font_section

        headers = ["Document / Policy Name", "Section / Title", "Audit Confidence", "Governance Excerpt"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col_idx, value=h)
            cell.font = self.font_header
            cell.fill = self.navy_fill

        curr_row = 6
        for src in doc.sources:
            c1 = ws.cell(row=curr_row, column=1, value=src.document_name)
            c2 = ws.cell(row=curr_row, column=2, value=src.title or "General Section")
            c3 = ws.cell(row=curr_row, column=3, value=f"{src.confidence_score*100:.0f}%" if src.confidence_score else "N/A")
            c4 = ws.cell(row=curr_row, column=4, value=src.excerpt)

            c1.font = self.font_bold
            c2.font = self.font_body
            c3.font = self.font_body
            c4.font = self.font_subtitle

            for c in (c1, c2, c3, c4):
                c.border = self.cell_border
                if curr_row % 2 == 1:
                    c.fill = self.light_gray_fill
            curr_row += 1

        self._auto_fit_columns(ws)
