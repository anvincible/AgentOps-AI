import pytest

from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.orchestration.verification_agent import VerificationAgent
from backend.app.orchestration.analysis_agent import AnalysisAgent
from backend.app.orchestration.answer_composer import AnswerComposer
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

    @staticmethod
    def select_relevant_evidence(_evidence, _question):
        return []


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


_HYBRID_QUESTION = "What are the CMP-021 campaign metrics and recommended strategy?"


def _campaign_metrics():
    return {
        "sql": "SELECT campaign_id, revenue_generated, conversions FROM marketing_campaigns WHERE campaign_id = %s;",
        "validation": {"valid": True},
        "query_plan": {"intent": "CAMPAIGN_PERFORMANCE", "entity_id": "CMP-021"},
        "result": {
            "columns": ["campaign_id", "revenue_generated", "conversions"],
            "rows": [["CMP-021", 5270000, 3812]],
        },
    }


def _campaign_strategy_evidence():
    evidence = [
        {
            "document_id": "DOC-MKT-024", "chunk_id": "DOC-MKT-024-006",
            "filename": "campaign_postmortem.docx", "title": "Campaign Postmortem CMP-021",
            "document_type": "MARKETING", "department": "Marketing / Business Operations",
            "related_entity_ids": ["CMP-021"], "similarity": 0.8,
            "content": (
                "Future campaigns should compare conversion efficiency, customer segment quality, "
                "and incremental revenue before increasing spend."
            ),
        },
        {
            "document_id": "DOC-MKT-024", "chunk_id": "DOC-MKT-024-008",
            "filename": "campaign_postmortem.docx", "title": "Campaign Postmortem CMP-021",
            "document_type": "MARKETING", "department": "Marketing / Business Operations",
            "related_entity_ids": ["CMP-021"], "similarity": 0.75,
            "content": (
                "Target segment alignment, campaign objective, channel selection, and "
                "conversion-oriented creative are factors to investigate."
            ),
        },
        {
            "document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002",
            "filename": "returns_policy.pdf", "title": "Returns Policy",
            "document_type": "POLICIES", "department": "Marketing / Business Operations",
            "related_entity_ids": [], "similarity": 0.31,
            "content": "Customers can return eligible items within thirty days for a refund.",
        },
    ]
    return {
        "evidence": evidence,
        "sources": [
            {key: item.get(key) for key in (
                "document_id", "chunk_id", "filename", "title", "document_type",
                "department", "page_number", "paragraph_number",
            )}
            for item in evidence
        ],
    }


def _hybrid_orchestrator(sql_result=None, sql_error=None, rag_result=None, rag_error=None):
    obj = _orchestrator("BOTH", sql_error, rag_error, sql_result, rag_result)
    obj.answer_composer = AnswerComposer()
    obj.verification_agent = VerificationAgent()
    if rag_error is not None:
        def fail_retrieval(_question):
            raise rag_error
        obj.rag_agent.retrieve = fail_retrieval
    elif rag_result is not None:
        obj.rag_agent.retrieve = lambda _question: rag_result
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


def test_hybrid_sql_success_rag_failure_returns_metrics_without_strategy_claims():
    obj = _hybrid_orchestrator(
        sql_result=_campaign_metrics(),
        rag_error=RuntimeError("private retrieval stack detail"),
    )
    result = obj.answer(_HYBRID_QUESTION)

    assert result["route"] == "BOTH"
    assert result["sql"]["result"]["rows"] == [["CMP-021", 5270000, 3812]]
    assert "Document retrieval could not be completed" in result["answer"]
    assert "Future campaigns should compare" not in result["answer"]
    assert "private retrieval stack detail" not in result["answer"]
    assert result["verification"]["verified"] is False


def test_hybrid_rag_success_sql_failure_returns_no_database_metrics():
    obj = _hybrid_orchestrator(
        sql_error=RuntimeError("private database stack detail"),
        rag_result=_campaign_strategy_evidence(),
    )
    result = obj.answer(_HYBRID_QUESTION)

    assert "sql" not in result
    assert "Future campaigns should compare conversion efficiency" in result["answer"]
    assert "The database query could not be completed" in result["answer"]
    assert "5,270,000" not in result["answer"]
    assert "private database stack detail" not in result["answer"]
    assert result["analysis"]["status"] == "insufficient_evidence"
    assert result["verification"]["verified"] is False


def test_hybrid_both_agents_failing_returns_controlled_insufficient_response():
    obj = _hybrid_orchestrator(
        sql_error=RuntimeError("private SQL trace"),
        rag_error=RuntimeError("private RAG trace"),
    )
    result = obj.answer(_HYBRID_QUESTION)

    assert "sql" not in result and "rag" not in result
    assert "could not retrieve evidence" in result["answer"].lower()
    assert "database query could not be completed" in result["answer"].lower()
    assert "Document retrieval could not be completed" in result["answer"]
    assert "private SQL trace" not in result["answer"]
    assert "private RAG trace" not in result["answer"]
    assert result["verification"]["verified"] is False


@pytest.mark.parametrize("validation", [None, {"valid": False}])
def test_hybrid_unvalidated_sql_rows_are_not_composed(validation):
    sql_result = _campaign_metrics()
    sql_result["result"]["rows"] = [["CMP-021", 987654321, 999999]]
    sql_result["validation"] = validation
    obj = _hybrid_orchestrator(
        sql_result=sql_result,
        rag_result=_campaign_strategy_evidence(),
    )
    result = obj.answer(_HYBRID_QUESTION)

    assert "sql" not in result
    assert "987,654,321" not in result["answer"]
    assert "structured-data query did not pass SQL validation" in result["answer"]
    assert "Future campaigns should compare conversion efficiency" in result["answer"]
    assert result["analysis"]["status"] == "insufficient_evidence"
    assert result["verification"]["verified"] is False


def test_hybrid_irrelevant_rag_candidates_are_not_claimed_as_used_sources():
    obj = _hybrid_orchestrator(
        sql_result=_campaign_metrics(),
        rag_result=_campaign_strategy_evidence(),
    )
    result = obj.answer(_HYBRID_QUESTION)
    analysis_evidence = result["analysis"]["evidence"]
    selected = obj.answer_composer.select_relevant_evidence(
        result["rag"]["evidence"], _HYBRID_QUESTION
    )

    used_keys = {
        (item["document_id"], item["chunk_id"])
        for item in analysis_evidence["document_sources"]
    }
    retrieved_keys = {
        (item["document_id"], item["chunk_id"])
        for item in analysis_evidence["retrieved_document_sources"]
    }
    selected_keys = {(item["document_id"], item["chunk_id"]) for item in selected}
    assert used_keys == selected_keys
    assert ("DOC-POL-001", "DOC-POL-001-002") in retrieved_keys
    assert ("DOC-POL-001", "DOC-POL-001-002") not in used_keys
    assert result["verification"]["verified"] is True


def test_hybrid_no_relevant_rag_evidence_has_no_document_claim_or_used_source():
    irrelevant = {
        "evidence": [{
            "document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002",
            "title": "Returns Policy", "filename": "returns_policy.pdf",
            "content": "Customers may return eligible items within thirty days.",
            "related_entity_ids": [], "similarity": 0.31,
        }],
        "sources": [{"document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002"}],
    }
    obj = _hybrid_orchestrator(sql_result=_campaign_metrics(), rag_result=irrelevant)
    result = obj.answer(_HYBRID_QUESTION)

    assert "return eligible items" not in result["answer"]
    assert "campaign strategy/recommendation" in result["answer"].lower()
    assert result["analysis"]["evidence"]["document_sources"] == []
    assert result["verification"]["verified"] is False
