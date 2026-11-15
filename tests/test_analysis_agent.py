from backend.app.orchestration.analysis_agent import AnalysisAgent


def _result(columns, rows, intent="TEST"):
    return {
        "query_plan": {"intent": intent},
        "validation": {"valid": True},
        "result": {"columns": columns, "rows": rows, "row_count": len(rows)},
    }


def test_kpi_summary_uses_only_present_sql_fields_and_computes_campaign_roi():
    result = _result(
        ["order_count", "total_revenue", "average_order_value"],
        [(50000, 4745475661.63, 94909.51)],
        "SALES_SUMMARY",
    )
    analysis = AnalysisAgent().analyze(result, "Summarize these sales KPIs")
    assert analysis["status"] == "complete"
    assert any("Order Count: 50,000" in item for item in analysis["insights"])
    assert any("₹4,745,475,661.63" in item for item in analysis["insights"])
    assert analysis["evidence"]["query_intent"] == "SALES_SUMMARY"

    campaign = _result(
        ["actual_spend", "revenue_generated", "conversions"],
        [(100, 150, 2)], "CAMPAIGN_PERFORMANCE",
    )
    campaign_analysis = AnalysisAgent().analyze(campaign, "Campaign spend and ROI")
    assert any("ROI (revenue less spend, divided by spend): 50.00%" in item
               for item in campaign_analysis["insights"])


def test_comparison_reports_exact_change_and_percentage_and_bar_chart():
    result = _result(
        ["product_name", "total_revenue"],
        [("Alpha", 100), ("Beta", 125)], "SALES_BY_PRODUCT",
    )
    analysis = AnalysisAgent().analyze(result, "Compare these products by revenue")
    assert analysis["status"] == "complete"
    assert "25.00%" in analysis["insights"][0]
    assert "25.00" in analysis["insights"][0]
    assert analysis["chart"] == {
        "type": "bar", "metric": "total_revenue", "labels": ["Alpha", "Beta"],
        "series": [{"name": "Total Revenue", "values": [100.0, 125.0]}],
    }


def test_zero_baseline_comparison_is_explicitly_undefined():
    result = _result(["category", "order_count"], [("A", 0), ("B", 4)])
    analysis = AnalysisAgent().analyze(result, "Compare these categories")
    assert "percentage change undefined because the comparison value is zero" in analysis["insights"][0]


def test_monthly_trend_orders_observations_and_produces_line_chart():
    result = _result(
        ["sales_month", "total_revenue"],
        [("2025-03-01", 300), ("2025-01-01", 100), ("2025-02-01", 200)],
        "SALES_BY_MONTH",
    )
    analysis = AnalysisAgent().analyze(result, "Show monthly revenue trend")
    assert analysis["status"] == "complete"
    assert "increased" in analysis["insights"][0]
    assert "200.00%" in analysis["insights"][0]
    assert analysis["chart"]["type"] == "line"
    assert analysis["chart"]["labels"] == ["2025-01-01", "2025-02-01", "2025-03-01"]


def test_trend_with_too_few_months_is_not_characterized():
    result = _result(["sales_month", "total_revenue"], [("2025-01-01", 1), ("2025-02-01", 2)])
    analysis = AnalysisAgent().analyze(result, "Show monthly revenue trend")
    assert analysis["status"] == "complete"
    assert "at least three observations" in analysis["insights"][0]
    assert analysis["chart"] is not None


def test_missing_or_invalid_evidence_is_reported_without_insight():
    agent = AnalysisAgent()
    assert agent.analyze(None)["status"] == "insufficient_evidence"
    invalid = _result(["customer_count"], [(10000,)])
    invalid["validation"]["valid"] = False
    assert agent.analyze(invalid)["insights"] == []
    empty = _result(["customer_count"], [])
    assert agent.analyze(empty)["status"] == "insufficient_evidence"


def test_source_attribution_retains_sql_intent_and_rag_document_refs():
    result = _result(["return_count", "order_count", "return_rate_percent"], [(3585, 50000, 7.17)], "RETURN_RATE")
    rag = {"sources": [{"document_id": "DOC-POL-001", "chunk_id": "003", "filename": "returns.pdf"}]}
    analysis = AnalysisAgent().analyze(result, "Calculate return rate and summarize its business impact", rag)
    assert analysis["evidence"]["source"] == "NovaMart PostgreSQL database"
    assert analysis["evidence"]["query_intent"] == "RETURN_RATE"
    assert analysis["evidence"]["validated"] is True
    assert analysis["evidence"]["document_sources"] == [
        {"document_id": "DOC-POL-001", "chunk_id": "003", "filename": "returns.pdf"}
    ]
    assert any("financial business impact cannot be quantified" in item
               for item in analysis["insights"])
