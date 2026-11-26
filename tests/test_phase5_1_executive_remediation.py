"""Tests for Phase 5.1: Executive Report Defect Remediation & PDF-Level Validation.
Verifies campaign rankings, category concentration accuracy, category reach semantics,
SKU pricing reconciliation, trailing 12-month chart bounds, and document/PDF-level QA.
"""

from __future__ import annotations

import io
import pytest
import pymupdf

from backend.app.reporting.data_layer import CentralizedReportingDataLayer
from backend.app.reporting.models import (
    ReportCategory,
    ReportDocument,
    ReportFormat,
    ReportPeriod,
    ReportTable,
)
from backend.app.reporting.narrative_generator import generate_executive_narrative
from backend.app.reporting.pdf_renderer import ReportLabPdfRenderer
from backend.app.reporting.excel_renderer import OpenPyXLExcelRenderer
from backend.app.reporting.qa_engine import ReportQAEngine


@pytest.fixture(scope="module")
def executive_data():
    """Retrieve and validate Executive Performance data layer."""
    layer = CentralizedReportingDataLayer()
    return layer.retrieve_and_validate(ReportCategory.EXECUTIVE_PERFORMANCE, ReportPeriod.ALL_TIME)


@pytest.fixture(scope="module")
def campaign_data():
    """Retrieve and validate Campaign Performance data layer."""
    layer = CentralizedReportingDataLayer()
    return layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)


@pytest.fixture(scope="module")
def executive_doc(executive_data):
    """Compile full Executive Performance ReportDocument."""
    summary, findings, risks, recs, methodology = generate_executive_narrative(executive_data)
    return ReportDocument(
        title="NovaMart Executive Business Performance Report",
        category=ReportCategory.EXECUTIVE_PERFORMANCE,
        period=ReportPeriod.ALL_TIME,
        executive_summary=summary,
        key_drivers=findings,
        risk_observations=risks,
        recommendations=recs,
        methodology_and_sources=methodology,
        kpi_cards=executive_data.to_kpi_cards(),
        tables=executive_data.to_tables(),
        raw_metrics={
            "categories": executive_data.categories,
            "timeline": executive_data.timeline,
            "top_products": executive_data.top_products,
            "campaigns": executive_data.campaigns,
        },
    )


@pytest.fixture(scope="module")
def executive_pdf_bytes(executive_doc):
    """Render executive PDF bytes."""
    renderer = ReportLabPdfRenderer()
    return renderer.render(executive_doc)


# ---------------------------------------------------------------------------
# 1. Campaign Ranking in Executive and Campaign Reports
# ---------------------------------------------------------------------------
def test_campaign_ranking_values_and_order(executive_data):
    """Verify exact campaign ROAS rankings: CMP-012 (6.35x), CMP-037 (6.32x), CMP-007 (4.56x), CMP-003 (4.51x)."""
    by_roas = executive_data.campaigns_by_roas
    assert len(by_roas) >= 4, "Expected at least 4 campaigns in dataset"

    # Verify top 4 campaigns
    assert by_roas[0]["id"] == "CMP-012"
    assert pytest.approx(by_roas[0]["roas"], 0.05) == 6.35

    assert by_roas[1]["id"] == "CMP-037"
    assert pytest.approx(by_roas[1]["roas"], 0.05) == 6.32

    assert by_roas[2]["id"] == "CMP-007"
    assert pytest.approx(by_roas[2]["roas"], 0.05) == 4.56

    assert by_roas[3]["id"] == "CMP-003"
    assert pytest.approx(by_roas[3]["roas"], 0.05) == 4.51

    # Verify strictly descending order across the entire list
    for i in range(len(by_roas) - 1):
        assert by_roas[i]["roas"] >= by_roas[i + 1]["roas"], (
            f"Campaigns not strictly sorted descending at index {i}: {by_roas[i]['id']} ({by_roas[i]['roas']}) < {by_roas[i+1]['id']} ({by_roas[i+1]['roas']})"
        )


def test_executive_tables_include_campaign_table(executive_doc):
    """Verify that Executive Report tables include Top Marketing Campaigns by Capital Efficiency."""
    titles = [t.title for t in executive_doc.tables]
    assert any("Top Marketing Campaigns by Capital Efficiency" in t for t in titles), (
        f"Campaign table missing from Executive Report tables: {titles}"
    )

    # Check that Table 3 is the campaign table
    camp_tbl = next(t for t in executive_doc.tables if "Top Marketing Campaigns by Capital Efficiency" in t.title)
    assert "ROAS (x)" in camp_tbl.columns or "ROAS" in camp_tbl.columns
    assert "ID" in camp_tbl.columns

    # Verify top rows in the table
    first_row = camp_tbl.rows[0]
    id_col = camp_tbl.columns.index("ID")
    assert first_row[id_col] == "CMP-012"

    second_row = camp_tbl.rows[1]
    assert second_row[id_col] == "CMP-037"


# ---------------------------------------------------------------------------
# 2. Category Concentration Accuracy & Rejection of Outdated Claims
# ---------------------------------------------------------------------------
def test_category_concentration_matches_data(executive_data, executive_doc):
    """Verify category concentration statements match actual data (Electronics: 46.93%, Sports: 11.11%)."""
    cat_map = {c["category"]: c["share_pct"] for c in executive_data.categories}
    elec_share = cat_map.get("Electronics", 0.0)
    sports_share = cat_map.get("Sports", 0.0)

    assert pytest.approx(elec_share, 0.1) == 46.93
    assert pytest.approx(sports_share, 0.1) == 11.11

    combined_top2 = elec_share + sports_share
    assert pytest.approx(combined_top2, 0.1) == 58.04

    # Verify that executive summary & findings use dynamic figures
    summary_and_findings = executive_doc.executive_summary + " " + " ".join(executive_doc.key_drivers)
    assert "46.9%" in summary_and_findings or "46.93%" in summary_and_findings
    assert "58.0%" in summary_and_findings or "58.04%" in summary_and_findings

    # Assert static outdated claims are completely absent
    assert "65%" not in summary_and_findings
    assert "appliances" not in summary_and_findings.lower()


# ---------------------------------------------------------------------------
# 3. Category Order Reach Semantics & Table 1 Footnote
# ---------------------------------------------------------------------------
def test_table1_order_reach_semantics(executive_doc):
    """Verify Table 1 renames column to 'Orders Containing Category' and includes reach footnote."""
    cat_tbl = next(t for t in executive_doc.tables if "Revenue Contribution by Merchandise Category" in t.title)
    assert "Orders Containing Category" in cat_tbl.columns
    assert "Order Volume" not in cat_tbl.columns

    # Footnote explaining multi-item basket reach
    assert cat_tbl.footnote is not None
    assert "105,974" in cat_tbl.footnote
    assert "50,000" in cat_tbl.footnote
    assert "2.50 SKUs" in cat_tbl.footnote


# ---------------------------------------------------------------------------
# 4. Complete SKU Pricing Reconciliation & Table 2
# ---------------------------------------------------------------------------
def test_table2_sku_pricing_reconciliation(executive_doc):
    """Verify Table 2 provides complete discount reconciliation columns and equation footnote."""
    sku_tbl = next(t for t in executive_doc.tables if "Top Performing SKUs with Pricing Reconciliation" in t.title)
    expected_cols = [
        "Product Name",
        "SKU ID",
        "Category",
        "Units Sold",
        "List Unit Price",
        "Gross List Value",
        "Discounts Applied",
        "Net Billed Revenue",
    ]
    assert sku_tbl.columns == expected_cols

    # Verify footnote
    assert sku_tbl.footnote is not None
    assert "Gross List Value = Units Sold" in sku_tbl.footnote
    assert "Net Billed Revenue = Gross List Value" in sku_tbl.footnote

    # Verify mathematical relationship in top row
    top_row = sku_tbl.rows[0]
    units_sold = int(top_row[3].replace(",", ""))
    # Clean currency values
    list_price = float(top_row[4].replace("₹", "").replace(",", ""))
    gross_list_val = float(top_row[5].replace("₹", "").replace(",", ""))
    discounts = float(top_row[6].replace("₹", "").replace(",", ""))
    net_revenue = float(top_row[7].replace("₹", "").replace(",", ""))

    # Gross List Value = Units Sold * List Unit Price
    calc_gross = units_sold * list_price
    assert abs(calc_gross - gross_list_val) < 1.0, f"Gross List mismatch: {calc_gross} vs {gross_list_val}"

    # Net Billed Revenue = Gross List Value - Discounts Applied
    calc_net = gross_list_val - discounts
    assert abs(calc_net - net_revenue) < 1.0, f"Net Revenue mismatch: {calc_net} vs {net_revenue}"


# ---------------------------------------------------------------------------
# 5. Reporting Window Bounds on Charts
# ---------------------------------------------------------------------------
def test_chart_trailing_12_month_bounds(executive_data):
    """Verify that chart title generates explicit data-derived bounds (2025-09 to 2026-08)."""
    from backend.app.reporting.chart_generator import generate_revenue_trend_chart

    chart_bytes = generate_revenue_trend_chart(executive_data.timeline)
    assert len(chart_bytes) > 5000, "Chart image bytes suspiciously small"

    # Bounds in timeline
    slice_12 = executive_data.timeline[-12:]
    start_m, end_m = slice_12[0]["month"], slice_12[-1]["month"]
    assert start_m == "2025-09"
    assert end_m == "2026-08"


# ---------------------------------------------------------------------------
# 6. Absence of Speculative Inferences & Arbitrary Projections
# ---------------------------------------------------------------------------
def test_absence_of_unsupported_projections(executive_doc):
    """Verify no '3-5% AOV uplift' or ungrounded claims in text."""
    full_narrative = (
        executive_doc.executive_summary
        + " "
        + " ".join(executive_doc.key_drivers)
        + " "
        + " ".join(executive_doc.risk_observations)
        + " "
        + " ".join(executive_doc.recommendations)
    )
    assert "3-5%" not in full_narrative
    assert "3–5%" not in full_narrative
    assert "aov uplift" not in full_narrative.lower()

    # Recommendations must follow empirical test framework
    for rec in executive_doc.recommendations:
        assert "[Action:" in rec
        assert "Expected Outcome:" in rec
        assert "Explicit Assumptions & Limitations:" in rec


# ---------------------------------------------------------------------------
# 7. Document-Level QA Engine Validation
# ---------------------------------------------------------------------------
def test_qa_engine_validates_document_pass(executive_doc, executive_data):
    """Verify that qa_engine.validate_document() passes with 0 issues."""
    qa = ReportQAEngine()
    result = qa.validate_document(executive_doc, executive_data)
    assert result.is_valid is True, f"Document QA failed: {result.issues}"
    assert len(result.issues) == 0


def test_qa_engine_detects_deliberate_table_sorting_defect():
    """Verify QA engine catches an unsorted ROAS table."""
    qa = ReportQAEngine()
    defect_table = ReportTable(
        title="Top Marketing Campaigns by Capital Efficiency (Ranked by ROAS)",
        columns=["Campaign Name", "ID", "Channel", "Spend", "Revenue", "ROAS (x)", "Net Yield"],
        rows=[
            ["Campaign A", "CMP-001", "Email", "₹10,000", "₹30,000", "3.00x", "+200%"],
            ["Campaign B", "CMP-002", "Social", "₹10,000", "₹50,000", "5.00x", "+400%"],  # Unsorted!
        ],
    )
    doc = ReportDocument(
        title="Defect Report",
        category=ReportCategory.EXECUTIVE_PERFORMANCE,
        period=ReportPeriod.ALL_TIME,
        tables=[defect_table],
    )
    result = qa.validate_document(doc)
    assert result.is_valid is False
    assert any("not sorted descending by ROAS" in issue for issue in result.issues)


def test_qa_engine_detects_deliberate_missing_reconciliation_columns():
    """Verify QA engine catches Top SKUs table missing Gross List Value."""
    qa = ReportQAEngine()
    defect_table = ReportTable(
        title="Top Performing SKUs with Pricing Reconciliation",
        columns=["Product Name", "SKU ID", "Category", "Units Sold", "Discounts Applied", "Net Billed Revenue"],  # Missing Gross List Value
        rows=[],
    )
    doc = ReportDocument(
        title="Defect Report",
        category=ReportCategory.EXECUTIVE_PERFORMANCE,
        period=ReportPeriod.ALL_TIME,
        tables=[defect_table],
    )
    result = qa.validate_document(doc)
    assert result.is_valid is False
    assert any("missing required reconciliation column: 'gross list value'" in issue for issue in result.issues)


# ---------------------------------------------------------------------------
# 8. Rendered PDF-Level Inspection via PyMuPDF
# ---------------------------------------------------------------------------
def test_pdf_level_inspection_and_qa(executive_pdf_bytes, executive_doc):
    """Verify PyMuPDF extracts and validates actual rendered PDF contents."""
    qa = ReportQAEngine()
    qa_result = qa.validate_file(executive_pdf_bytes, ReportFormat.PDF, doc=executive_doc)
    assert qa_result.is_valid is True, f"PDF-level QA failed: {qa_result.issues}"

    pdf_doc = pymupdf.open(stream=executive_pdf_bytes, filetype="pdf")
    assert len(pdf_doc) >= 3, f"Expected at least 3 pages, found {len(pdf_doc)}"

    full_text = " ".join(page.get_text() for page in pdf_doc)

    # 1. Campaign table and ordered campaigns present
    assert "Top Marketing Campaigns by Capital Efficiency" in full_text
    assert "CMP-012" in full_text
    assert "CMP-037" in full_text
    assert "CMP-007" in full_text
    assert "CMP-003" in full_text

    pos_012 = full_text.find("CMP-012")
    pos_037 = full_text.find("CMP-037")
    pos_007 = full_text.find("CMP-007")
    pos_003 = full_text.find("CMP-003")
    assert pos_012 < pos_037 < pos_007 < pos_003, "Campaigns not ordered CMP-012 < CMP-037 < CMP-007 < CMP-003 in PDF text"

    # 2. Table 1 Reach semantics present
    assert "Orders Containing" in full_text
    assert "105,974" in full_text

    # 3. Table 2 Pricing reconciliation present
    assert "Gross List Value" in full_text
    assert "Discounts Applied" in full_text
    assert "Net Billed" in full_text

    # 4. Forbidden claims absent
    assert "3-5%" not in full_text
    assert "3–5%" not in full_text
    assert "over 65%" not in full_text


# ---------------------------------------------------------------------------
# 9. Excel Render Inspection
# ---------------------------------------------------------------------------
def test_excel_level_inspection(executive_doc):
    """Verify Excel workbook renders with full reconciliation and footnotes."""
    renderer = OpenPyXLExcelRenderer()
    xlsx_bytes = renderer.render(executive_doc)
    assert len(xlsx_bytes) > 5000

    qa = ReportQAEngine()
    qa_result = qa.validate_file(xlsx_bytes, ReportFormat.XLSX, doc=executive_doc)
    assert qa_result.is_valid is True, f"Excel QA failed: {qa_result.issues}"
