import pytest

from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.orchestration.verification_agent import VerificationAgent
from backend.app.orchestration.analysis_agent import AnalysisAgent
from backend.app.sql.sql_reasoner import SQLReasoner


class _Schema:
    def load_schema(self):
        columns = {
            "marketing_campaigns": (
                "campaign_id", "campaign_name", "actual_spend",
                "revenue_generated", "conversions", "clicks",
            ),
            "products": ("product_id", "product_name", "category", "brand", "stock_quantity", "price"),
            "order_items": ("product_id", "quantity", "item_total"),
            "customers": ("customer_id", "customer_segment", "city", "state", "country", "loyalty_tier", "acquisition_channel", "status"),
        }
        return {"tables": {table: {"columns": [
            {"column_name": name} for name in names
        ]} for table, names in columns.items()}}


def test_product_best_wording_requires_metric_clarification():
    result = _orchestrator("SQL").answer("Which product performed best?")
    assert result["route"] == "CLARIFY"
    assert "revenue" in result["clarification"]["options"]


def test_customer_distribution_without_dimension_is_clarified():
    result = _orchestrator("SQL").answer("Show customer distribution.")
    assert result["route"] == "CLARIFY"
    assert "segment" in result["clarification"]["options"]


@pytest.mark.parametrize(("question", "intent"), [
    ("Which product performed best by revenue?", "TOP_PRODUCTS_BY_REVENUE"),
    ("Which product performed best by quantity?", "TOP_PRODUCTS_BY_QUANTITY"),
])
def test_product_best_with_metric_selects_ranking_template(question, intent):
    plan = SQLReasoner(_Schema()).reason(question)
    assert plan["intent"] == intent


def test_customer_distribution_by_segment_uses_supported_template():
    plan = SQLReasoner(_Schema()).reason("Show customer distribution by segment.")
    assert plan["intent"] == "CUSTOMER_DISTRIBUTION"
    assert plan["dimension"] == "customer_segment"


@pytest.mark.parametrize(("question", "intent"), [
    ("Show campaign performance.", "CAMPAIGN_PERFORMANCE"),
    ("Summarize campaign performance.", "CAMPAIGN_SUMMARY"),
])
def test_campaign_summary_and_performance_are_not_roi_rankings(question, intent):
    plan = SQLReasoner(_Schema()).reason(question)
    assert plan["intent"] == intent


@pytest.mark.parametrize(("question", "metric"), [
    ("Rank campaigns by ROI", "roi_percent"),
    ("Rank campaigns by revenue", "revenue_generated"),
    ("Rank campaigns by conversions", "conversions"),
])
def test_campaign_ranking_metric_is_explicit(question, metric):
    plan = SQLReasoner(_Schema()).reason(question)
    assert plan["intent"] == "CAMPAIGN_RANKING"
    assert plan["campaign_metric"] == metric


class _Rag:
    @staticmethod
    def _explicit_document_type_filter(_question):
        return None

    def retrieve(self, _question):
        raise RuntimeError("private rag failure")


class _Sql:
    schema = {"tables": {"customers": {"columns": []}}}

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def answer(self, _question):
        if self.error:
            raise self.error
        return self.result


class _Composer:
    @staticmethod
    def compose(_response):
        return "SQL evidence: 42" if _response.get("sql") else "Document evidence: policy excerpt"


class _Verifier:
    @staticmethod
    def verify(answer, route, sql_result=None, rag_result=None, question=""):
        return VerificationAgent().verify(
            answer, route, sql_result, rag_result, question
        )


def _orchestrator(route, sql_error=None, rag_error=None, sql_result=None, rag_result=None):
    obj = Orchestrator.__new__(Orchestrator)
    obj.sql_agent = _Sql(sql_result, sql_error)
    obj.rag_agent = _Rag()
    if rag_result is not None:
        obj.rag_agent.retrieve = lambda _question: rag_result
    elif rag_error is None:
        obj.rag_agent.retrieve = lambda _question: {"evidence": [], "sources": []}
    obj.answer_composer = _Composer()
    obj.verification_agent = _Verifier()
    obj.analysis_agent = AnalysisAgent()
    obj._route_question = lambda _question: route
    return obj


def test_short_product_clarification_context_resolves_original_question():
    obj = _orchestrator("SQL")
    original = "Which product performed best?"
    context = {
        "original_question": original,
        "kind": "product_ranking_metric",
        "options": ["revenue", "quantity"],
    }
    result = obj.answer("By revenue", clarification_context=context)
    assert result["question"] == "Which product performed best? by revenue"
    assert result["route"] == "SQL"


def test_unrelated_question_does_not_consume_stale_clarification_context():
    context = {
        "original_question": "Which product performed best?",
        "kind": "product_ranking_metric",
        "options": ["revenue", "quantity"],
    }
    assert Orchestrator._resolve_clarification("What is the return rate?", context) is None


@pytest.mark.parametrize("metric", ["roi_percent", "revenue_generated", "conversions"])
def test_campaign_ranking_verification_checks_requested_metric(metric):
    from backend.app.orchestration.answer_composer import AnswerComposer

    columns = ["campaign_id", "campaign_name", "actual_spend", "revenue_generated", "conversions", "clicks"]
    if metric == "roi_percent":
        columns.append("roi_percent")
    result = {
        "sql": f"SELECT ... ORDER BY {metric} DESC LIMIT 10;",
        "validation": {"valid": True},
        "query_plan": {"intent": "CAMPAIGN_RANKING", "campaign_metric": metric},
        "result": {"columns": columns, "rows": [
            ["CMP-1", "One", 100, 500, 10, 20] + ([400.0] if metric == "roi_percent" else []),
            ["CMP-2", "Two", 200, 400, 8, 18] + ([100.0] if metric == "roi_percent" else []),
        ]},
    }
    answer = AnswerComposer()._compose_sql(result, result["query_plan"])
    verified = VerificationAgent().verify(answer, "SQL", sql_result=result, question="Rank campaigns")
    assert verified["verified"] is True
    assert f"Ranking rows are ordered by {metric}." in verified["checks"]


def test_campaign_summary_verification_does_not_require_ranking_order():
    from backend.app.orchestration.answer_composer import AnswerComposer

    result = {
        "sql": "SELECT COUNT(*) AS campaign_count, SUM(actual_spend) FROM marketing_campaigns;",
        "validation": {"valid": True},
        "query_plan": {"intent": "CAMPAIGN_SUMMARY"},
        "result": {
            "columns": ["campaign_count", "total_spend", "total_revenue", "total_conversions", "total_clicks"],
            "rows": [[3, 1000, 2500, 90, 1200]],
        },
    }
    answer = AnswerComposer()._compose_sql(result, result["query_plan"])
    verified = VerificationAgent().verify(answer, "SQL", sql_result=result, question="Show campaign performance")
    assert verified["verified"] is True
    assert not any("Ranking SQL" in issue for issue in verified["issues"])


@pytest.mark.parametrize(("route", "sql_error", "rag_error", "sql_result", "rag_result"), [
    ("SQL", RuntimeError("secret sql error"), None, None, None),
    ("RAG", None, RuntimeError("secret rag error"), None, None),
    ("BOTH", RuntimeError("secret sql error"), None, None, {"evidence": [], "sources": []}),
    ("BOTH", None, RuntimeError("secret rag error"), {"result": {"rows": [[42]]}, "validation": {"valid": True}}, None),
])
def test_agent_failures_are_controlled_and_hybrid_is_unverified(
    route, sql_error, rag_error, sql_result, rag_result
):
    obj = _orchestrator(route, sql_error, rag_error, sql_result, rag_result)
    result = obj.answer("What is the policy and customer count?")
    assert "secret" not in result["answer"]
    if route == "BOTH":
        assert result["verification"]["verified"] is False
