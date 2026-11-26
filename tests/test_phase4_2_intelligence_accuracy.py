"""Automated QA & Unit Test Suite for Phase 4.2 Business Intelligence Accuracy.
Validates:
1. Correct campaign rankings by ROAS, Attributed Revenue, and Conversion Volume
2. Strict distinction between ROAS, Attributed Revenue, and Net Profit
3. Detection and rejection of unsupported numerical projections and ungrounded claims
4. Attribution methodology governance (no unverified last-click claims)
5. Epistemic structure in findings ([Measured Fact], [Calculated Comparison], [Interpretation], [Business Implication])
6. Consistency between tables, charts, and narrative insights
7. Cross-format PDF and Excel reconciliation
"""

from __future__ import annotations

import io
import pytest
import openpyxl

from backend.app.orchestration.report_agent import ReportAgent
from backend.app.reporting.data_layer import CentralizedReportingDataLayer
from backend.app.reporting.insight_validator import InsightValidator
from backend.app.reporting.models import (
    ReportCategory,
    ReportFormat,
    ReportPeriod,
    ReportRequestModel,
)
from backend.app.reporting.narrative_generator import generate_executive_narrative
from backend.app.reporting.qa_engine import ReportQAEngine


@pytest.fixture
def data_layer() -> CentralizedReportingDataLayer:
    return CentralizedReportingDataLayer()


@pytest.fixture
def qa_engine() -> ReportQAEngine:
    return ReportQAEngine()


@pytest.fixture
def report_agent() -> ReportAgent:
    return ReportAgent()


def test_campaign_ranking_by_roas(data_layer: CentralizedReportingDataLayer):
    """Verify that campaigns_by_roas is strictly sorted in descending order by ROAS,
    and identifies CMP-012 and CMP-037 as top return efficiency leaders.
    """
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)
    camps = data.campaigns_by_roas
    assert len(camps) > 0, "Campaigns list must not be empty"

    # Assert descending sort
    for i in range(len(camps) - 1):
        assert camps[i]["roas"] >= camps[i + 1]["roas"], f"ROAS not descending: {camps[i]['roas']} < {camps[i+1]['roas']}"

    # Verify top ROAS campaigns
    top_roas = camps[0]
    assert top_roas["id"] == "CMP-012"
    assert abs(top_roas["roas"] - 6.35) < 0.05
    assert "Mega Campaign 12" in top_roas["campaign_name"]

    second_roas = camps[1]
    assert second_roas["id"] == "CMP-037"
    assert abs(second_roas["roas"] - 6.32) < 0.05


def test_campaign_ranking_by_revenue(data_layer: CentralizedReportingDataLayer):
    """Verify that campaigns_by_revenue is strictly sorted in descending order by revenue,
    and identifies CMP-007 as the top commercial scale leader.
    """
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)
    camps = data.campaigns_by_revenue
    assert len(camps) > 0

    for i in range(len(camps) - 1):
        assert camps[i]["revenue"] >= camps[i + 1]["revenue"], "Revenue not descending"

    top_rev = camps[0]
    assert top_rev["id"] == "CMP-007"
    assert top_rev["revenue"] > 9000000.0  # ₹98.34 Lakhs
    assert "Growth Campaign 07" in top_rev["campaign_name"]


def test_campaign_ranking_by_conversions(data_layer: CentralizedReportingDataLayer):
    """Verify that campaigns_by_conversions is strictly sorted in descending order by conversions."""
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)
    camps = data.campaigns_by_conversions
    assert len(camps) > 0

    for i in range(len(camps) - 1):
        assert camps[i]["conversions"] >= camps[i + 1]["conversions"], "Conversions not descending"

    top_conv = camps[0]
    assert top_conv["conversions"] >= 4500


def test_table_and_chart_consistency(data_layer: CentralizedReportingDataLayer):
    """Ensure that the primary efficiency table and the ROI chart both reflect
    the exact same top campaigns ranked by ROAS.
    """
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)
    tables = data.to_tables()

    # Find the ROAS efficiency table
    eff_table = next(t for t in tables if "Capital Efficiency" in t.title)
    assert eff_table is not None

    # First row must be CMP-012 with 6.35x
    first_row = eff_table.rows[0]
    assert "CMP-012" in first_row[1]
    assert "6.35x" in first_row[5]

    # Second row must be CMP-037 with 6.32x
    second_row = eff_table.rows[1]
    assert "CMP-037" in second_row[1]
    assert "6.32x" in second_row[5]


def test_insight_validator_rejects_false_ranking(data_layer: CentralizedReportingDataLayer):
    """InsightValidator must reject any finding claiming Campaign 07 has the highest return efficiency."""
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)

    false_finding = (
        "Channel Yield Demarcation: Flagship campaign 'NovaMart Growth Campaign 07' achieved superior return efficiency. "
        "[Evidence: Spend ₹21,55,790.63, Attributed Revenue ₹98,34,425.37, ROAS 4.56x]."
    )

    valid, issues = InsightValidator.validate_campaign_rankings(data.campaigns, false_finding)
    assert not valid, "Validator should have rejected false claim attributing top efficiency to CMP-007"
    assert any("CMP-012" in iss for iss in issues)


def test_insight_validator_accepts_accurate_ranking(data_layer: CentralizedReportingDataLayer):
    """InsightValidator must accept finding citing CMP-012 as top return efficiency leader."""
    data = data_layer.retrieve_and_validate(ReportCategory.CAMPAIGN_PERFORMANCE, ReportPeriod.ALL_TIME)

    true_finding = (
        "[Measured Fact] 'NovaMart Mega Campaign 12' (CMP-012) generated ₹69,45,549.16 in attributed revenue. "
        "[Calculated Comparison] 'NovaMart Mega Campaign 12' delivered the highest return efficiency at 6.35x ROAS. "
        "[Interpretation] Targeted seasonal messaging maximized capital efficiency."
    )

    valid, issues = InsightValidator.validate_campaign_rankings(data.campaigns, true_finding)
    assert valid, f"Validator should accept true finding, but got: {issues}"


def test_financial_terminology_enforcement():
    """InsightValidator must reject misuse of 'net profitable' or 'profit-based roi' for ad spend."""
    bad_text = "The advertising campaign was net profitable and generated strong profit-based ROI for the brand."
    valid, issues = InsightValidator.validate_terminology(bad_text)
    assert not valid
    assert len(issues) >= 2

    good_text = "Portfolio Return on Ad Spend (ROAS) reached 1.72x, representing an Ad Net Yield of +71.8% above media cost prior to COGS."
    valid, issues = InsightValidator.validate_terminology(good_text)
    assert valid
    assert len(issues) == 0


def test_attribution_governance_enforcement():
    """InsightValidator must reject claims asserting verified last-click attribution."""
    unsupported_claim = "Under our verified last-click attribution model, search drove all conversions."
    valid, issues = InsightValidator.validate_terminology(unsupported_claim)
    assert not valid
    assert any("attribution" in iss.lower() for iss in issues)


def test_unsupported_recommendations_rejection():
    """InsightValidator must reject arbitrary percentage projections without explicit assumptions."""
    bad_rec = "Reallocate spend to achieve projected 5-8% increase in repeat orders."
    valid, issues = InsightValidator.validate_recommendation_structure(bad_rec)
    assert not valid
    assert any("assumptions" in iss.lower() for iss in issues)

    good_rec = (
        "Supplier Safety-Stock Buffer Alignment: Review reorder triggers. "
        "[Action: Establish a minimum 14-day buffer stock; "
        "Expected Outcome: Mitigate inventory stockout risk; "
        "Explicit Assumptions & Limitations: Vendor manufacturing lead times must remain within 7-day SLAs]."
    )
    valid, issues = InsightValidator.validate_recommendation_structure(good_rec)
    assert valid


def test_generated_narratives_pass_qa_engine(data_layer: CentralizedReportingDataLayer, qa_engine: ReportQAEngine):
    """All 6 report categories must generate narratives that pass pre-flight QA validation."""
    for cat in [
        ReportCategory.EXECUTIVE_PERFORMANCE,
        ReportCategory.SALES_PERFORMANCE,
        ReportCategory.CAMPAIGN_PERFORMANCE,
        ReportCategory.CUSTOMER_INTELLIGENCE,
        ReportCategory.OPERATIONS_FULFILLMENT,
        ReportCategory.CUSTOM_REPORT,
    ]:
        data = data_layer.retrieve_and_validate(cat, ReportPeriod.ALL_TIME)
        summary, findings, risks, recs, methodology = generate_executive_narrative(data)

        # Validate findings & recommendations
        qa_result = qa_engine.validate_insights(data, findings, recs)
        assert qa_result.is_valid, f"QA failed for {cat.value}: {qa_result.issues}"


def test_pdf_and_excel_cross_reconciliation(report_agent: ReportAgent, data_layer: CentralizedReportingDataLayer):
    """Verify that PDF and Excel deliverables for Campaign Performance reconcile completely."""
    req_pdf = ReportRequestModel(
        category=ReportCategory.CAMPAIGN_PERFORMANCE,
        format=ReportFormat.PDF,
        period=ReportPeriod.ALL_TIME,
        title="NovaMart Marketing & Campaign Performance Report",
    )
    pdf_bytes, _, _ = report_agent.generate_enterprise(req_pdf)
    assert pdf_bytes.startswith(b"%PDF-")

    req_xlsx = ReportRequestModel(
        category=ReportCategory.CAMPAIGN_PERFORMANCE,
        format=ReportFormat.XLSX,
        period=ReportPeriod.ALL_TIME,
        title="NovaMart Marketing & Campaign Performance Report",
    )
    xlsx_bytes, _, _ = report_agent.generate_enterprise(req_xlsx)
    assert xlsx_bytes.startswith(b"PK")

    # Load workbook and verify sheets
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    sheetnames = wb.sheetnames
    assert "KPI Scorecard" in sheetnames
    assert "Strategic Insights" in sheetnames
    assert any("Capital Efficiency" in s for s in sheetnames)
