"""Enterprise Business Intelligence reporting engine test suite.
Validates ReportLab Platypus PDF generation, openpyxl Excel workbooks,
and CSV exports across all 6 report categories and operational periods.
"""

from io import BytesIO
from zipfile import ZipFile

import openpyxl
import pytest

from backend.app.orchestration.report_agent import ReportAgent
from backend.app.reporting.models import (
    ReportCategory,
    ReportFormat,
    ReportPeriod,
    ReportRequestModel,
    ReportSectionConfig,
)


@pytest.fixture
def agent():
    return ReportAgent()


def test_executive_performance_pdf_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.EXECUTIVE_PERFORMANCE,
        format=ReportFormat.PDF,
        period=ReportPeriod.ALL_TIME,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-executive-performance-")
    assert filename.endswith(".pdf")
    assert mime == "application/pdf"
    assert content.startswith(b"%PDF-")
    assert len(content) > 50000  # Matplotlib charts + Platypus layout


def test_sales_performance_xlsx_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.SALES_PERFORMANCE,
        format=ReportFormat.XLSX,
        period=ReportPeriod.THIS_YEAR,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-sales-performance-")
    assert filename.endswith(".xlsx")
    assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert content.startswith(b"PK")

    # Validate workbook structure with openpyxl
    wb = openpyxl.load_workbook(BytesIO(content))
    expected_sheets = {"Executive Summary", "KPI Scorecard", "Strategic Insights", "Audit & Sources"}
    sheet_names = set(wb.sheetnames)
    assert expected_sheets.issubset(sheet_names)
    # Check that KPI Sheet has data
    ws_kpi = wb["KPI Scorecard"]
    assert ws_kpi.max_row >= 4


def test_campaign_performance_pdf_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.CAMPAIGN_PERFORMANCE,
        format=ReportFormat.PDF,
        period=ReportPeriod.LAST_90_DAYS,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-campaign-performance-")
    assert filename.endswith(".pdf")
    assert content.startswith(b"%PDF-")


def test_customer_intelligence_pdf_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.CUSTOMER_INTELLIGENCE,
        format=ReportFormat.PDF,
        period=ReportPeriod.ALL_TIME,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-customer-intelligence-")
    assert filename.endswith(".pdf")
    assert content.startswith(b"%PDF-")


def test_operations_fulfillment_xlsx_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.OPERATIONS_FULFILLMENT,
        format=ReportFormat.XLSX,
        period=ReportPeriod.LAST_30_DAYS,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-operations-fulfillment-")
    assert filename.endswith(".xlsx")
    wb = openpyxl.load_workbook(BytesIO(content))
    assert "Executive Summary" in wb.sheetnames


def test_custom_report_csv_generation(agent):
    request = ReportRequestModel(
        category=ReportCategory.CUSTOM_REPORT,
        format=ReportFormat.CSV,
        period=ReportPeriod.LAST_7_DAYS,
        title="NovaMart Custom Executive Audit",
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert filename.startswith("novamart-custom-report-")
    assert filename.endswith(".csv")
    assert mime == "text/csv; charset=utf-8"
    csv_text = content.decode("utf-8-sig")
    assert "NovaMart Custom Executive Audit" in csv_text
    assert "SECTION:" in csv_text


def test_section_toggles_and_customization(agent):
    # Test report with charts disabled
    sections = ReportSectionConfig(include_charts=False, include_recommendations=False)
    request = ReportRequestModel(
        category=ReportCategory.EXECUTIVE_PERFORMANCE,
        format=ReportFormat.PDF,
        period=ReportPeriod.ALL_TIME,
        sections=sections,
    )
    content, filename, mime = agent.generate_enterprise(request)
    assert content.startswith(b"%PDF-")
