"""Focused report-generation tests using explicit SQL-result fixtures."""

from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from backend.app.api.report_endpoint import build_report_response
from backend.app.orchestration.report_agent import ReportAgent


def _sql_result(intent, columns, rows):
    return {
        "query_plan": {"intent": intent},
        "sql": "SELECT validated_fixture_rows;",
        "validation": {"valid": True, "errors": []},
        "result": {"columns": columns, "rows": rows, "row_count": len(rows)},
    }


def _business_response(partial=False):
    areas = ["Sales", "Customers", "Returns", "Campaigns"]
    intents = ["SALES_SUMMARY", "CUSTOMER_COUNT", "RETURN_RATE", "CAMPAIGN_PERFORMANCE"]
    values = [
        {"order_count": 50000, "total_revenue": 4745475661.63, "average_order_value": 94909.51},
        {"customer_count": 10000},
        {"return_count": 3585, "order_count": 50000, "return_rate_percent": 7.17},
        {"campaign_count": 50, "total_spend": 85756152.26, "total_revenue": 147362008.86,
         "total_conversions": 63337, "total_clicks": 2062509},
    ]
    components = [
        {
            "area": area,
            "query_intent": intent,
            "status": "query_failed" if partial and area == "Returns" else "validated",
            "sql_validated": not (partial and area == "Returns"),
            "result_nonempty": not (partial and area == "Returns"),
        }
        for area, intent in zip(areas, intents)
    ]
    evidence_results = [
        {"area": area, "query_intent": intent, "validated": True, "row_count": 1,
         "fields": list(area_values), "values": area_values}
        for area, intent, area_values in zip(areas, intents, values)
        if not (partial and area == "Returns")
    ]
    statuses = [
        {"area": area, "status": "unavailable" if partial and area == "Returns" else "covered"}
        for area in areas
    ]
    return {
        "route": "SQL",
        "answer": "Sales summary fixture.",
        "sql": _sql_result("SALES_SUMMARY", ["order_count"], [[50000]]),
        "analysis": {
            "status": "partial" if partial else "complete",
            "summary": "Retrieved KPI evidence for business areas.",
            "insights": ["Customers: 10,000.", "Returns: 7.17%."] if not partial else ["Customers: 10,000."],
            "limitations": ["Returns KPI evidence unavailable."] if partial else [],
            "coverage": statuses,
            "evidence": {
                "source": "NovaMart PostgreSQL database",
                "validated": True,
                "row_count": len(evidence_results),
                "results": evidence_results,
                "components": components,
            },
        },
        "verification": {
            "verified": not partial,
            "issues": ["Business-summary evidence coverage is partial."] if partial else [],
            "business_summary": {
                "verified": not partial,
                "coverage_status": "partial" if partial else "complete",
                "analysis_consistent": True,
                "issues": ["Returns unavailable."] if partial else [],
            },
        },
    }


def _answer_fixture(question):
    if question == "Summarize NovaMart's business performance.":
        return _business_response()
    if question == "Show the monthly revenue trend.":
        rows = [
            ["2025-01-01", 100, 1000.25],
            ["2025-02-01", 120, 1300.50],
        ]
        return {
            "route": "SQL",
            "sql": _sql_result("SALES_BY_MONTH", ["sales_month", "order_count", "total_revenue"], rows),
            "analysis": {"insights": ["Revenue increased across the returned months."], "limitations": []},
            "verification": {"verified": True, "checks": ["SQL claims match rows."], "issues": []},
        }
    if question == "Show campaign performance.":
        result = _sql_result("CAMPAIGN_PERFORMANCE", ["campaign_count", "total_spend", "total_revenue"], [[50, 1000.0, 1800.0]])
    else:
        result = _sql_result(
            "CAMPAIGN_RANKING",
            ["campaign_id", "campaign_name", "roi_percent", "actual_spend", "revenue_generated"],
            [["CMP-021", "Campaign 21", 80.0, 1000.0, 1800.0], ["CMP-022", "Campaign 22", 50.0, 2000.0, 3000.0]],
        )
    return {
        "route": "SQL",
        "sql": result,
        "analysis": {"insights": ["Validated campaign results returned."], "limitations": []},
        "verification": {"verified": True, "checks": ["SQL claims match rows."], "issues": []},
    }


def _assert_pdf_xref_is_valid(content):
    startxref_marker = b"startxref\n"
    position = content.rfind(startxref_marker)
    assert position >= 0
    xref_offset = int(content[position + len(startxref_marker):].splitlines()[0])
    assert content[xref_offset:xref_offset + 4] == b"xref"
    lines = content[xref_offset:].splitlines()
    object_count = int(lines[1].split()[1])
    for object_number, entry in enumerate(lines[3:3 + object_count - 1], start=1):
        object_offset = int(entry[:10])
        assert content[object_offset:].startswith(f"{object_number} 0 obj".encode("ascii"))


def test_business_performance_report_contains_validated_kpis_and_component_sources():
    content, filename, media_type = ReportAgent().generate(
        "business_performance", "pdf", _answer_fixture
    )
    assert filename.endswith(".pdf")
    assert media_type == "application/pdf"
    assert content.startswith(b"%PDF-1.4")
    assert b"%%EOF" in content
    assert b"4745475661.63".hex().upper().encode() in content
    assert b"10,000".hex().upper().encode() in content
    assert b"CAMPAIGN_PERFORMANCE".hex().upper().encode() in content
    _assert_pdf_xref_is_valid(content)


def test_sales_report_is_a_valid_xlsx_with_numeric_monthly_rows():
    content, filename, media_type = ReportAgent().generate(
        "sales_analysis", "xlsx", _answer_fixture
    )
    assert filename.endswith(".xlsx")
    assert media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with ZipFile(BytesIO(content)) as workbook:
        assert workbook.testzip() is None
        required = {
            "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels", "xl/styles.xml", "xl/worksheets/sheet1.xml",
        }
        assert required.issubset(set(workbook.namelist()))
        for name in workbook.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(workbook.read(name))
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet2.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        numeric_values = [node.text for node in sheet.findall(".//x:v", namespace)]
        strings = [node.text for node in sheet.findall(".//x:t", namespace)]
        assert "1000.25" in numeric_values
        assert "1300.5" in numeric_values
        assert "2025-01-01" in strings
        all_xml = " ".join(
            workbook.read(name).decode("utf-8")
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet")
        )
        assert "SALES_BY_MONTH" in all_xml


def test_campaign_report_contains_aggregate_and_individual_ranking_data():
    content, _, _ = ReportAgent().generate(
        "campaign_performance", "xlsx", _answer_fixture
    )
    with ZipFile(BytesIO(content)) as workbook:
        sheet_xml = "\n".join(
            workbook.read(name).decode("utf-8")
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet")
        )
    assert "CMP-021" in sheet_xml
    assert "80.0" in sheet_xml
    assert "campaign_count" in sheet_xml
    assert "Top Campaigns by ROI" in sheet_xml
    assert "CAMPAIGN_RANKING" in sheet_xml


def test_partial_business_report_labels_unavailable_area_and_verification_limits():
    content, _, _ = ReportAgent().generate(
        "business_performance", "xlsx", lambda _question: _business_response(partial=True)
    )
    with ZipFile(BytesIO(content)) as workbook:
        contents = " ".join(
            workbook.read(name).decode("utf-8")
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet")
        )
    assert "Returns" in contents
    assert "unavailable" in contents
    assert "partial" in contents
    assert "not fully verified" in contents


def test_unsupported_results_produce_explicit_insufficient_report_without_claims():
    def unsupported(_question):
        return {
            "route": "SQL",
            "answer": "Unsupported query.",
            "verification": {"verified": False, "issues": ["SQL evidence unavailable."]},
        }

    content, _, _ = ReportAgent().generate("sales_analysis", "pdf", unsupported)
    assert content.startswith(b"%PDF-1.4")
    assert b"No validated data rows were returned.".hex().upper().encode() in content
    assert b"No nonempty SQL result".hex().upper().encode() in content
    _assert_pdf_xref_is_valid(content)


def test_report_api_helper_sets_attachment_headers_and_pdf_content_type():
    response = build_report_response(
        ReportAgent(), "sales_analysis", "pdf", _answer_fixture
    )
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment; filename=\"novamart-sales-analysis-")
    assert bytes(response.body).startswith(b"%PDF-1.4")


def test_report_api_helper_sets_xlsx_attachment_type_and_filename():
    response = build_report_response(
        ReportAgent(), "campaign_performance", "xlsx", _answer_fixture
    )
    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="novamart-campaign-performance-'
    )
    assert bytes(response.body).startswith(b"PK")
