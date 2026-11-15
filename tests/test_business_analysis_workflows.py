"""Focused workflow tests runnable directly when pytest is unavailable."""

from backend.app.orchestration.analysis_agent import AnalysisAgent
from backend.app.orchestration.answer_composer import AnswerComposer
from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.orchestration.verification_agent import VerificationAgent
from backend.app.sql.sql_generator import SQLGenerator
from backend.app.sql.sql_reasoner import SQLReasoner
from backend.app.sql.sql_validator import SQLValidator


def _sql_result(intent, columns, rows):
    return {
        "query_plan": {"intent": intent},
        "sql": "SELECT validated_fixture_rows;",
        "validation": {"valid": True},
        "result": {"columns": columns, "rows": rows, "row_count": len(rows)},
    }


def _summary_results():
    return {
        "What is total sales revenue and average order value?": _sql_result(
            "SALES_SUMMARY", ["order_count", "total_revenue", "average_order_value"],
            [[50000, 4745475661.63, 94909.51]],
        ),
        "How many customers are there?": _sql_result(
            "CUSTOMER_COUNT", ["customer_count"], [[10000]],
        ),
        "What is the return rate?": _sql_result(
            "RETURN_RATE", ["return_count", "order_count", "return_rate_percent"],
            [[3585, 50000, 7.17]],
        ),
        "Show campaign performance.": _sql_result(
            "CAMPAIGN_PERFORMANCE",
            ["campaign_count", "total_spend", "total_revenue", "total_conversions", "total_clicks"],
            [[50, 85756152.26, 147362008.86, 63337, 2062509]],
        ),
    }


class _SQLAgent:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def answer(self, question):
        self.calls.append(question)
        response = self.responses[question]
        if isinstance(response, Exception):
            raise response
        return response


class _RAGAgent:
    @staticmethod
    def _explicit_document_type_filter(_question):
        return None

    @staticmethod
    def retrieve(_question):
        return {"evidence": [], "sources": []}


def _orchestrator(responses):
    obj = Orchestrator.__new__(Orchestrator)
    obj.sql_agent = _SQLAgent(responses)
    obj.rag_agent = _RAGAgent()
    obj.answer_composer = AnswerComposer()
    obj.verification_agent = VerificationAgent()
    obj.analysis_agent = AnalysisAgent()
    return obj


def test_business_summary_routes_to_sql_and_reports_only_retrieved_areas():
    responses = _summary_results()
    obj = _orchestrator(responses)
    result = obj.answer("Summarize NovaMart's business performance.")

    assert result["route"] == "SQL"
    assert len(obj.sql_agent.calls) == 4
    assert result["verification"]["verified"] is True
    assert result["verification"]["business_summary"]["verified"] is True
    assert result["verification"]["business_summary"]["analysis_consistent"] is True
    assert result["verification"]["business_summary"]["validated_component_count"] == 4
    assert result["analysis"]["status"] == "complete"
    assert [item["status"] for item in result["analysis"]["coverage"]] == [
        "covered", "covered", "covered", "covered",
    ]
    assert len(result["analysis"]["evidence"]["results"]) == 4
    assert any("Customers: Customer Count: 10,000" in item for item in result["analysis"]["insights"])
    assert any("Returns:" in item and "7.17%" in item for item in result["analysis"]["insights"])


def test_business_summary_partial_failures_are_explicit_and_unqueried_data_omitted():
    responses = _summary_results()
    responses["How many customers are there?"]["validation"]["valid"] = False
    responses["What is the return rate?"] = RuntimeError("private database details")
    obj = _orchestrator(responses)
    result = obj.answer("Summarize NovaMart's business performance.")

    analysis = result["analysis"]
    assert result["route"] == "SQL"
    assert analysis["status"] == "partial"
    assert analysis["coverage"][1:3] == [
        {"area": "Customers", "status": "unavailable"},
        {"area": "Returns", "status": "unavailable"},
    ]
    assert "KPI evidence unavailable for: Customers, Returns." in analysis["limitations"]
    assert not any("Customer Count" in item or "Return Rate" in item or "Return Count" in item
                   for item in analysis["insights"])
    assert "private database details" not in result["answer"]
    summary_verification = result["verification"]["business_summary"]
    assert result["verification"]["verified"] is False
    assert summary_verification["coverage_status"] == "partial"
    assert summary_verification["analysis_consistent"] is True
    assert summary_verification["validated_component_count"] == 2


def test_combined_summary_consistency_check_rejects_mismatched_evidence_metadata():
    result = _orchestrator(_summary_results()).answer(
        "Summarize NovaMart's business performance."
    )
    analysis = result["analysis"]
    analysis["evidence"]["row_count"] += 1
    checked = VerificationAgent.verify_business_summary(analysis)
    assert checked["verified"] is False
    assert checked["analysis_consistent"] is False
    assert checked["coverage_status"] == "complete"


def test_period_scoped_business_summary_clarifies_instead_of_returning_all_time_data():
    responses = _summary_results()
    obj = _orchestrator(responses)
    for question in (
        "Summarize NovaMart's business performance for 2025.",
        "Summarize NovaMart's business performance over the last six months.",
    ):
        clarification = obj.answer(question)
        assert clarification["route"] == "CLARIFY"
        assert "time period consistently" in clarification["answer"]
        assert clarification["clarification"]["kind"] == "business_summary_period"
        assert clarification["clarification"]["options"] == ["all-time summary"]
    assert obj.sql_agent.calls == []
    clarification = obj.answer("Summarize NovaMart's business performance for 2025.")
    resolved = obj.answer("all-time summary", clarification_context=clarification["clarification"])
    assert resolved["question"] == "Summarize NovaMart's business performance."
    assert resolved["route"] == "SQL"
    assert len(obj.sql_agent.calls) == 4


def test_business_summary_period_clarification_accepts_natural_affirmative_replies():
    replies = (
        "All-time data is acceptable.",
        "Yes, use all-time data.",
        "Use the all-time summary.",
        "All time is fine.",
    )
    for reply in replies:
        orchestrator = _orchestrator(_summary_results())
        clarification = orchestrator.answer(
            "Summarize NovaMart's business performance for 2025."
        )
        assert clarification["route"] == "CLARIFY"
        assert orchestrator.sql_agent.calls == []
        resolved = orchestrator.answer(
            reply, clarification_context=clarification["clarification"]
        )
        assert resolved["question"] == "Summarize NovaMart's business performance."
        assert resolved["route"] == "SQL"
        assert resolved["analysis"]["status"] == "complete"
        assert len(orchestrator.sql_agent.calls) == 4


def test_business_summary_clarification_rejects_unrelated_and_stale_context():
    orchestrator = _orchestrator(_summary_results())
    pending = orchestrator.answer(
        "Summarize NovaMart's business performance for 2025."
    )["clarification"]
    assert Orchestrator._resolve_clarification("What is the return policy?", pending) is None
    assert Orchestrator._resolve_clarification("No, don't use all-time data.", pending) is None
    assert Orchestrator._resolve_clarification("All-time is not acceptable.", pending) is None
    assert Orchestrator._resolve_clarification("All time is fine.", None) is None
    assert Orchestrator._resolve_clarification(
        "All time is fine.",
        {
            **pending,
            "original_question": "What is the return policy?",
        },
    ) is None
    unrelated = orchestrator.answer(
        "What is the return policy?", clarification_context=pending
    )
    expired = orchestrator.answer("All time is fine.")
    assert unrelated["route"] == "RAG"
    assert expired["route"] != "SQL"
    assert orchestrator.sql_agent.calls == []


def test_existing_sales_template_parameterizes_supported_year_filter_but_summary_refuses_partial_period():
    class SchemaLoader:
        @staticmethod
        def load_schema():
            columns = ("order_id", "total_amount", "order_date")
            return {"tables": {"orders": {"columns": [
                {"column_name": column} for column in columns
            ]}}}

    loader = SchemaLoader()
    plan = SQLReasoner(loader).reason("What are sales and average order value in 2025?")
    sql, params = SQLGenerator(loader).generate_query(plan)
    validation = SQLValidator(loader.load_schema()).validate(sql)
    assert plan["intent"] == "SALES_SUMMARY"
    assert plan["date_filter"] == {"start_year": 2025, "end_year": 2025}
    assert "o.order_date >= %s AND o.order_date < %s" in sql
    assert params[0].isoformat() == "2025-01-01"
    assert params[1].isoformat() == "2026-01-01"
    assert validation["valid"] is True
    orchestrator = _orchestrator(_summary_results())
    result = orchestrator.answer("Summarize NovaMart's business performance for 2025.")
    assert result["route"] == "CLARIFY"
    assert orchestrator.sql_agent.calls == []


def test_business_summary_zero_campaign_spend_marks_roi_unavailable():
    analysis = AnalysisAgent().analyze_business_summary([
        _sql_result(
            "CAMPAIGN_PERFORMANCE",
            ["campaign_count", "total_spend", "total_revenue", "total_conversions", "total_clicks"],
            [[50, 0, 1500, 10, 100]],
        ),
    ])
    assert analysis["status"] == "partial"
    assert analysis["coverage"][3] == {"area": "Campaigns", "status": "partial"}
    assert any("spend is zero" in item for item in analysis["limitations"])
    assert not any("ROI:" in item for item in analysis["insights"])


def test_campaign_comparison_without_two_targets_clarifies_and_followup_uses_supported_plan():
    responses = {
        "Compare campaigns CMP-021 and CMP-022.": _sql_result(
            "CAMPAIGN_COMPARISON",
            ["campaign_id", "campaign_name", "actual_spend", "revenue_generated", "conversions", "clicks"],
            [
                ["CMP-021", "Campaign 21", 1000, 1500, 10, 100],
                ["CMP-022", "Campaign 22", 1200, 1800, 12, 120],
            ],
        )
    }
    obj = _orchestrator(responses)
    question = "Compare campaign performance and highlight important differences."
    clarification = obj.answer(question)

    assert clarification["route"] == "CLARIFY"
    context = clarification["clarification"]
    assert context["kind"] == "campaign_comparison_targets"
    assert "two campaign IDs" in context["prompt"]
    assert obj.sql_agent.calls == []
    assert Orchestrator._resolve_clarification(
        "What happened to CMP-021 and CMP-022?", context
    ) is None

    result = obj.answer("CMP-021 and CMP-022", clarification_context=context)
    assert result["question"] == "Compare campaigns CMP-021 and CMP-022."
    assert result["route"] == "SQL"
    assert result["sql"]["query_plan"]["intent"] == "CAMPAIGN_COMPARISON"
    assert result["analysis"]["chart"]["labels"] == [
        "CMP-021 — Campaign 21", "CMP-022 — Campaign 22",
    ]
    assert {series["metric"] for series in result["analysis"]["chart"]["series"]} == {
        "actual_spend", "revenue_generated", "conversions", "clicks",
    }
    assert result["verification"]["verified"] is True


def test_direct_campaign_analysis_with_more_than_two_rows_is_explicitly_unsupported():
    result = AnalysisAgent().analyze(
        _sql_result(
            "CAMPAIGN_COMPARISON",
            ["campaign_id", "campaign_name", "actual_spend", "revenue_generated", "conversions", "clicks"],
            [
                ["CMP-021", "Campaign 21", 1000, 1500, 10, 100],
                ["CMP-022", "Campaign 22", 1200, 1800, 12, 120],
                ["CMP-023", "Campaign 23", 900, 1300, 8, 90],
            ],
        ),
        "Compare campaigns CMP-021, CMP-022, and CMP-023.",
    )
    assert result["status"] == "insufficient_evidence"
    assert result["chart"] is None
    assert result["insights"] == []
    assert "exactly two" in result["limitations"][0]


def test_two_campaign_ids_reuse_the_validated_individual_campaign_template():
    class SchemaLoader:
        @staticmethod
        def load_schema():
            # Names confirmed from the live public.marketing_campaigns schema.
            columns = (
                "campaign_id", "campaign_name", "actual_spend",
                "revenue_generated", "conversions", "clicks",
            )
            return {"tables": {"marketing_campaigns": {"columns": [
                {"column_name": column} for column in columns
            ]}}}

    loader = SchemaLoader()
    plan = SQLReasoner(loader).reason("Compare campaigns CMP-021 and CMP-022.")
    sql, params = SQLGenerator(loader).generate_query(plan)
    validation = SQLValidator(loader.load_schema()).validate(sql)

    assert plan["intent"] == "CAMPAIGN_COMPARISON"
    assert plan["entity_ids"] == ["CMP-021", "CMP-022"]
    assert all(column in sql for column in ("campaign_id", "campaign_name", "actual_spend"))
    assert "FROM marketing_campaigns" in sql
    assert "campaign_count" not in sql
    assert params == ()
    assert validation["valid"] is True


def test_aggregate_campaign_result_cannot_verify_requested_campaign_comparison():
    question = "Compare campaign performance and highlight important differences."
    sql_result = _sql_result(
        "CAMPAIGN_PERFORMANCE",
        ["campaign_count", "total_spend", "total_revenue", "total_conversions", "total_clicks"],
        [[50, 1000, 1500, 10, 100]],
    )
    answer = AnswerComposer().compose({"route": "SQL", "question": question, "sql": sql_result})
    verification = VerificationAgent().verify(answer, "SQL", sql_result=sql_result, question=question)
    analysis = AnalysisAgent().analyze(sql_result, question)

    assert verification["verified"] is False
    assert any("aggregate evidence is insufficient" in issue for issue in verification["issues"])
    assert analysis["status"] == "partial"
    assert analysis["chart"] is None
    assert any("not separate labeled campaign rows" in item for item in analysis["limitations"])


def test_campaign_comparison_verification_checks_requested_ids():
    question = "Compare campaigns CMP-021 and CMP-022."
    sql_result = _sql_result(
        "CAMPAIGN_COMPARISON",
        ["campaign_id", "campaign_name", "actual_spend", "revenue_generated", "conversions", "clicks"],
        [
            ["CMP-021", "Campaign 21", 1000, 1500, 10, 100],
            ["CMP-023", "Campaign 23", 900, 1300, 8, 90],
        ],
    )
    sql_result["query_plan"]["entity_ids"] = ["CMP-021", "CMP-022"]
    answer = AnswerComposer().compose({"route": "SQL", "question": question, "sql": sql_result})
    verification = VerificationAgent().verify(answer, "SQL", sql_result=sql_result, question=question)
    assert verification["verified"] is False
    assert any("do not match the requested campaign IDs" in issue for issue in verification["issues"])


def test_monthly_trend_product_comparison_and_return_rate_are_preserved():
    agent = AnalysisAgent()
    monthly = agent.analyze(_sql_result(
        "SALES_BY_MONTH", ["sales_month", "total_revenue"],
        [["2025-02-01", 120], ["2025-01-01", 100], ["2025-03-01", 150]],
    ), "Show monthly revenue trend")
    product = agent.analyze(_sql_result(
        "TOP_PRODUCTS_BY_REVENUE", ["product_name", "total_revenue"],
        [["Alpha", 100], ["Beta", 125]],
    ), "Compare the top products by revenue")
    returns = agent.analyze(_sql_result(
        "RETURN_RATE", ["return_count", "order_count", "return_rate_percent"],
        [[3585, 50000, 7.17]],
    ), "Calculate the return rate and summarize its business impact")

    assert monthly["chart"]["labels"] == ["2025-01-01", "2025-02-01", "2025-03-01"]
    assert monthly["chart"]["type"] == "line"
    assert product["chart"]["type"] == "bar"
    assert "25.00%" in product["insights"][0]
    assert any("7.17%" in item for item in returns["insights"])
    assert any("financial business impact cannot be quantified" in item for item in returns["limitations"])
    assert Orchestrator._route_question("What is the return policy?") == "RAG"
    assert Orchestrator._route_question(
        "What are the CMP-021 campaign metrics and recommended strategy?"
    ) == "BOTH"


def test_rag_and_hybrid_answer_verification_paths_remain_available():
    rag_result = {
        "evidence": [{
            "document_id": "DOC-POLICY-001",
            "chunk_id": "DOC-POLICY-001-001",
            "title": "NovaMart Policy Notes",
            "filename": "policy.txt",
            "content": "The policy document explains procedures for customers and discusses customer count information there.",
            "similarity": 0.9,
        }],
        "sources": [{
            "document_id": "DOC-POLICY-001",
            "chunk_id": "DOC-POLICY-001-001",
            "title": "NovaMart Policy Notes",
            "filename": "policy.txt",
        }],
    }
    composer = AnswerComposer()
    verifier = VerificationAgent()
    rag_question = "What does the policy say?"
    rag_answer = composer.compose({"route": "RAG", "question": rag_question, "rag": rag_result})
    rag_verification = verifier.verify(
        rag_answer, "RAG", rag_result=rag_result, question=rag_question
    )
    assert rag_verification["verified"] is True

    sql_result = _sql_result("CUSTOMER_COUNT", ["customer_count"], [[10000]])
    hybrid_question = "What does the policy say and how many customers are there?"
    hybrid_answer = composer.compose({
        "route": "BOTH", "question": hybrid_question,
        "sql": sql_result, "rag": rag_result,
    })
    hybrid_verification = verifier.verify(
        hybrid_answer, "BOTH", sql_result=sql_result,
        rag_result=rag_result, question=hybrid_question,
    )
    assert hybrid_verification["verified"] is True
