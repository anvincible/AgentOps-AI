"""Universal Professional ReportLab Platypus PDF Report Renderer for AgentOps AI.
Generates multi-page, executive-grade business intelligence publications with
native Unicode typography (including Indian Rupee ₹), running headers/footers,
KPI scorecards, high-resolution static charts, structured tables, and citations.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.reporting.chart_generator import (
    generate_campaign_roi_chart,
    generate_category_donut_chart,
    generate_customer_tiers_chart,
    generate_revenue_trend_chart,
    generate_top_products_bar_chart,
)
from backend.app.reporting.design_system import PALETTE, RL_COLORS, register_unicode_fonts
from backend.app.reporting.models import (
    ReportCategory,
    ReportDocument,
    ReportKpiItem,
    ReportTable,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas computing accurate total page count ('Page X of Y')
    along with running executive headers and confidentiality footers.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(RL_COLORS["text_muted"])

        # Top running header (omitted on page 1)
        if self._pageNumber > 1:
            self.drawString(
                54,
                755,
                "AgentOps AI · NovaMart Enterprise Business Intelligence Report",
            )
            self.drawRightString(612 - 54, 755, datetime.now(timezone.utc).strftime("%B %d, %Y"))
            self.setStrokeColor(RL_COLORS["border_metallic"])
            self.setLineWidth(0.5)
            self.line(54, 747, 612 - 54, 747)

        # Bottom running footer (present on all pages)
        self.setStrokeColor(RL_COLORS["border_metallic"])
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45)

        self.drawString(
            54,
            33,
            "CONFIDENTIAL & PROPRIETARY — STRICTLY FOR INTERNAL NOVAMART EXECUTIVE USE",
        )
        self.drawRightString(
            612 - 54,
            33,
            f"Page {self._pageNumber} of {page_count}",
        )
        self.restoreState()


class ReportLabPdfRenderer:
    """Renders executive-grade multi-page BI PDF documents using ReportLab Platypus."""

    def __init__(self) -> None:
        self.font_reg, self.font_bold, self.font_italic = register_unicode_fonts()
        self.styles = getSampleStyleSheet()
        self._init_typography()

    def _init_typography(self) -> None:
        """Configures typography hierarchy using registered Unicode font family."""
        self.style_title = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Heading1"],
            fontName=self.font_bold,
            fontSize=21,
            leading=25,
            textColor=RL_COLORS["text_dark"],
            spaceAfter=3,
        )
        self.style_subtitle = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=9.5,
            leading=13.5,
            textColor=RL_COLORS["text_muted"],
            spaceAfter=10,
        )
        self.style_h2 = ParagraphStyle(
            "SectionH2",
            parent=self.styles["Heading2"],
            fontName=self.font_bold,
            fontSize=12,
            leading=16,
            textColor=RL_COLORS["text_dark"],
            spaceBefore=12,
            spaceAfter=5,
            keepWithNext=True,
        )
        self.style_body = ParagraphStyle(
            "BodyDark",
            parent=self.styles["BodyText"],
            fontName=self.font_reg,
            fontSize=8.5,
            leading=12.5,
            textColor=RL_COLORS["text_body"],
            spaceAfter=6,
        )
        self.style_kpi_label = ParagraphStyle(
            "KpiLabel",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#94A3B8"),
            alignment=1,
        )
        self.style_kpi_val = ParagraphStyle(
            "KpiVal",
            parent=self.styles["Normal"],
            fontName=self.font_bold,
            fontSize=13,
            leading=15,
            textColor=RL_COLORS["electric_cyan"],
            alignment=1,
        )
        self.style_kpi_sub = ParagraphStyle(
            "KpiSub",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=6.5,
            leading=8,
            textColor=RL_COLORS["text_muted"],
            alignment=1,
        )
        self.style_table_header = ParagraphStyle(
            "TableHeader",
            parent=self.styles["Normal"],
            fontName=self.font_bold,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=0,
        )
        self.style_table_cell = ParagraphStyle(
            "TableCell",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=7.5,
            leading=9.5,
            textColor=RL_COLORS["text_dark"],
            alignment=0,
        )
        self.style_table_cell_right = ParagraphStyle(
            "TableCellRight",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=7.5,
            leading=9.5,
            textColor=RL_COLORS["text_dark"],
            alignment=2,  # Right-aligned for metrics
        )
        self.style_bullet = ParagraphStyle(
            "BulletText",
            parent=self.styles["Normal"],
            fontName=self.font_reg,
            fontSize=8,
            leading=11.5,
            textColor=RL_COLORS["text_body"],
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=4,
        )

    def render(self, doc_data: ReportDocument) -> bytes:
        """Render a full ReportDocument model into PDF byte stream."""
        buffer = io.BytesIO()

        pdf = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        story: List[Any] = []

        # 1. Header & Title Block
        story.extend(self._build_header_block(doc_data))

        # 2. Executive Summary Box
        story.extend(self._build_executive_summary_box(doc_data))

        # 3. KPI Scorecard Block
        include_kpi = doc_data.request.sections.include_kpi_summary if doc_data.request else True
        if include_kpi and doc_data.kpi_cards:
            story.extend(self._build_kpi_scorecard(doc_data.kpi_cards))

        # 4. Charts Block
        include_charts = doc_data.request.sections.include_charts if doc_data.request else True
        if include_charts:
            chart_elements = self._build_charts_section(doc_data)
            if chart_elements:
                story.extend(chart_elements)

        # 5. Detailed Structured Tables
        include_tables = doc_data.request.sections.include_detailed_tables if doc_data.request else True
        if include_tables and doc_data.tables:
            story.extend(self._build_tables_section(doc_data.tables))

        # 6. Strategic Observations & Drivers
        story.extend(self._build_observations_section(doc_data))

        # 7. Recommendations
        include_recs = doc_data.request.sections.include_recommendations if doc_data.request else True
        if include_recs and doc_data.recommendations:
            story.extend(self._build_recommendations_section(doc_data.recommendations))

        # 8. Methodology & Sources / Citations
        include_src = doc_data.request.sections.include_sources if doc_data.request else True
        if include_src:
            story.extend(self._build_methodology_section(doc_data))

        # Build PDF using NumberedCanvas
        pdf.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()

    def _build_header_block(self, doc_data: ReportDocument) -> List[Any]:
        elements: List[Any] = []
        category_name = doc_data.category.value.replace("_", " ").upper()

        meta_table = Table(
            [
                [
                    Paragraph(
                        f"<b>ENTERPRISE INTELLIGENCE DELIVERABLE</b> &nbsp;|&nbsp; {category_name}",
                        ParagraphStyle(
                            "MetaTag",
                            fontName=self.font_bold,
                            fontSize=7.5,
                            textColor=RL_COLORS["royal_blue"],
                        ),
                    ),
                    Paragraph(
                        f"Generated: {doc_data.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
                        ParagraphStyle(
                            "MetaDate",
                            fontName=self.font_reg,
                            fontSize=7.5,
                            textColor=RL_COLORS["text_muted"],
                            alignment=2,
                        ),
                    ),
                ]
            ],
            colWidths=[320, 184],
        )
        meta_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 3))

        # Document Title
        elements.append(Paragraph(doc_data.title, self.style_title))

        # Subtitle & Classification
        period_text = doc_data.period.value.replace("_", " ").title()
        subtitle_text = f"Scope: NovaMart Enterprise Portfolio &nbsp;•&nbsp; Reporting Window: <b>{period_text}</b> &nbsp;•&nbsp; Classification: <b>Executive Confidential</b>"
        elements.append(Paragraph(subtitle_text, self.style_subtitle))

        # Accent Divider Line
        elements.append(
            HRFlowable(
                width="100%",
                thickness=1.5,
                color=RL_COLORS["royal_blue"],
                spaceBefore=2,
                spaceAfter=10,
            )
        )

        return elements

    def _build_executive_summary_box(self, doc_data: ReportDocument) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Executive Summary & Commercial Context", self.style_h2))

        summary_p = Paragraph(str(doc_data.executive_summary), self.style_body)
        card_table = Table([[summary_p]], colWidths=[504])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                    ("LINELEFT", (0, 0), (-1, -1), 3, RL_COLORS["royal_blue"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 10))
        return elements

    def _build_kpi_scorecard(self, kpi_cards: List[ReportKpiItem]) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Core Performance Indicators (KPI Scorecard)", self.style_h2))

        # Group KPIs into rows of 4
        cards_per_row = 4
        rows = [kpi_cards[i : i + cards_per_row] for i in range(0, len(kpi_cards), cards_per_row)]
        col_width = 504.0 / 4

        table_data: List[List[Any]] = []
        for row in rows:
            row_cells: List[Any] = []
            for kpi in row:
                cell_content = [
                    Paragraph(kpi.label.upper(), self.style_kpi_label),
                    Spacer(1, 2),
                    Paragraph(str(kpi.value), self.style_kpi_val),
                    Spacer(1, 2),
                    Paragraph(kpi.subtitle or "Verified Ledger", self.style_kpi_sub),
                ]
                row_cells.append(cell_content)
            while len(row_cells) < 4:
                row_cells.append([])
            table_data.append(row_cells)

        card_table = Table(table_data, colWidths=[col_width] * 4)
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), RL_COLORS["midnight_navy"]),
                    ("BOX", (0, 0), (-1, -1), 1, RL_COLORS["border_metallic"]),
                    ("INNERGRID", (0, 0), (-1, -1), 1, RL_COLORS["border_metallic"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 10))
        return elements

    def _build_charts_section(self, doc_data: ReportDocument) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Visual Trend & Portfolio Diagnostics", self.style_h2))

        raw_metrics = doc_data.raw_metrics or {}
        cat = doc_data.category

        try:
            if cat in [ReportCategory.EXECUTIVE_PERFORMANCE, ReportCategory.SALES_PERFORMANCE, ReportCategory.BUSINESS_PERFORMANCE, ReportCategory.SALES_ANALYSIS]:
                trend_bytes = generate_revenue_trend_chart(
                    raw_metrics.get("timeline", []),
                    width=4.0,
                    height=2.2,
                )
                donut_bytes = generate_category_donut_chart(
                    raw_metrics.get("categories", []),
                    width=3.0,
                    height=2.2,
                )

                img_trend = Image(io.BytesIO(trend_bytes), width=285, height=155)
                img_donut = Image(io.BytesIO(donut_bytes), width=215, height=155)

                chart_grid = Table([[img_trend, img_donut]], colWidths=[287, 217])
                chart_grid.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ]
                    )
                )
                elements.append(chart_grid)

            elif cat == ReportCategory.CAMPAIGN_PERFORMANCE:
                camp_bytes = generate_campaign_roi_chart(
                    raw_metrics.get("campaigns", []),
                    width=6.8,
                    height=2.5,
                )
                img_camp = Image(io.BytesIO(camp_bytes), width=504, height=185)
                elements.append(img_camp)

            elif cat == ReportCategory.CUSTOMER_INTELLIGENCE:
                tier_bytes = generate_customer_tiers_chart(
                    raw_metrics.get("customer_tiers", []),
                    width=4.0,
                    height=2.2,
                )
                donut_bytes = generate_category_donut_chart(
                    raw_metrics.get("categories", []),
                    title="Category Affinities",
                    width=3.0,
                    height=2.2,
                )
                img_tier = Image(io.BytesIO(tier_bytes), width=285, height=155)
                img_donut = Image(io.BytesIO(donut_bytes), width=215, height=155)
                chart_grid = Table([[img_tier, img_donut]], colWidths=[287, 217])
                chart_grid.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ]
                    )
                )
                elements.append(chart_grid)

            else:
                top_bytes = generate_top_products_bar_chart(
                    raw_metrics.get("top_products", []),
                    width=6.8,
                    height=2.4,
                )
                img_top = Image(io.BytesIO(top_bytes), width=504, height=175)
                elements.append(img_top)

            elements.append(Spacer(1, 10))
        except Exception as e:
            elements.append(
                Paragraph(
                    f"<i>[Diagnostic Chart Rendering Temporarily Unavailable: {str(e)}]</i>",
                    self.style_body,
                )
            )

        return elements

    def _build_tables_section(self, tables: List[ReportTable]) -> List[Any]:
        elements: List[Any] = []

        for tbl in tables[:4]:  # Top 4 priority tables for comprehensive report coverage
            elements.append(Paragraph(tbl.title, self.style_h2))

            # Headers
            header_cells = [
                Paragraph(col, self.style_table_header) for col in tbl.columns
            ]
            rows: List[List[Any]] = [header_cells]

            # Rows (Up to 12 rows per table)
            for row in tbl.rows[:12]:
                row_cells: List[Any] = []
                for idx, val in enumerate(row):
                    val_str = str(val)
                    # Right-align if it looks like a metric/amount/percentage
                    is_numeric = val_str.startswith("₹") or val_str.endswith("%") or val_str.replace(",", "").replace(".", "").replace("+", "").replace("-", "").isdigit()
                    style = self.style_table_cell_right if (is_numeric and idx > 0) else self.style_table_cell
                    row_cells.append(Paragraph(val_str, style))
                rows.append(row_cells)

            num_cols = len(tbl.columns)
            # Dynamic proportional column widths for balanced layout and zero text crowding
            if num_cols == 8:
                col_widths = [86, 56, 56, 58, 58, 56, 68, 66]
            elif num_cols == 7:
                if "ID" in tbl.columns:
                    col_widths = [130, 45, 55, 65, 75, 60, 74]
                else:
                    col_widths = [134, 50, 60, 65, 65, 60, 70]
            elif num_cols == 6:
                col_widths = [134, 70, 70, 80, 80, 70]
            elif num_cols == 5:
                col_widths = [124, 105, 75, 105, 95]
            elif num_cols == 4:
                col_widths = [144, 110, 130, 120]
            elif num_cols == 3:
                col_widths = [204, 150, 150]
            else:
                col_width = 504.0 / num_cols if num_cols > 0 else 504.0
                col_widths = [col_width] * num_cols

            data_table = Table(rows, colWidths=col_widths, repeatRows=1)
            data_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), RL_COLORS["midnight_navy"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ]
                )
            )

            table_block = [data_table]
            if getattr(tbl, "footnote", None):
                footnote_style = ParagraphStyle(
                    "TableFootnote",
                    parent=self.styles["Normal"],
                    fontName=self.font_reg,
                    fontSize=6.5,
                    leading=9,
                    textColor=RL_COLORS["text_muted"],
                    spaceBefore=2,
                    spaceAfter=4,
                )
                table_block.append(Paragraph(tbl.footnote, footnote_style))
            elements.append(KeepTogether(table_block))
            elements.append(Spacer(1, 8))

        return elements

    def _build_observations_section(self, doc_data: ReportDocument) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Strategic Findings & Interpretations", self.style_h2))

        for finding in doc_data.key_drivers:
            elements.append(
                KeepTogether(
                    [
                        Paragraph(f"<b>• Strategic Observation:</b> {finding}", self.style_bullet),
                        Spacer(1, 3),
                    ]
                )
            )

        if doc_data.risk_observations:
            elements.append(Spacer(1, 4))
            for risk in doc_data.risk_observations:
                elements.append(
                    KeepTogether(
                        [
                            Paragraph(
                                f"<b>• Operational & Governance Consideration:</b> <font color='#DC2626'>{risk}</font>",
                                self.style_bullet,
                            ),
                            Spacer(1, 3),
                        ]
                    )
                )

        elements.append(Spacer(1, 8))
        return elements

    def _build_recommendations_section(self, recommendations: List[str]) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Prescriptive Strategic Recommendations (Qualified Scenarios)", self.style_h2))

        for idx, rec in enumerate(recommendations, 1):
            elements.append(
                KeepTogether(
                    [
                        Paragraph(f"<b>{idx}. Action Item:</b> {rec}", self.style_bullet),
                        Spacer(1, 3),
                    ]
                )
            )

        elements.append(Spacer(1, 8))
        return elements

    def _build_methodology_section(self, doc_data: ReportDocument) -> List[Any]:
        elements: List[Any] = []
        elements.append(Paragraph("Data Integrity, Methodology & Audit Sources", self.style_h2))

        elements.append(
            Paragraph(
                f"<b>Accounting & Verification Standards:</b> {doc_data.methodology}",
                self.style_body,
            )
        )

        if doc_data.sources:
            elements.append(Spacer(1, 4))
            elements.append(
                Paragraph("<b>Corporate Governance Citations:</b>", self.style_body)
            )
            for src in doc_data.sources:
                doc_title = src.title or src.document_name
                conf_pct = f" (Audit Confidence: {src.confidence_score * 100:.0f}%)" if src.confidence_score else ""
                elements.append(
                    Paragraph(
                        f"• <b>{doc_title}</b>: <i>\"{src.excerpt}\"</i>{conf_pct}",
                        self.style_bullet,
                    )
                )

        return elements
