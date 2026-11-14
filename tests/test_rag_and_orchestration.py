import pytest

from backend.app.orchestration.answer_composer import AnswerComposer
from backend.app.orchestration.verification_agent import VerificationAgent
from backend.app.rag.rag_agent import RAGAgent
from backend.app.rag.retriever import Retriever


@pytest.mark.unit
def test_retriever_entity_and_keyword_scoring():
    item = {
        "title": "Campaign CMP-021 Postmortem",
        "filename": "campaign_postmortem_CMP-021.docx",
        "content": "CMP-021 generated revenue after the campaign.",
        "related_entity_ids": ["CMP-021"],
        "similarity": 0.4,
    }

    assert Retriever._has_entity_match("Results for CMP-021", item)
    assert Retriever._calculate_relevance("Results for CMP-021", item) > 0.4


@pytest.mark.unit
def test_rag_retrieval_returns_ranked_evidence_and_source_metadata():
    class FakeRetriever:
        def search(self, query, top_k):
            return [
                {
                    "chunk_id": "DOC-1-001",
                    "document_id": "DOC-1",
                    "filename": "campaign.docx",
                    "title": "Campaign CMP-021",
                    "document_type": "report",
                    "page_number": None,
                    "paragraph_number": 3,
                    "related_entity_ids": ["CMP-021"],
                    "content": (
                        "Campaign CMP-021 generated 5,270,000 revenue "
                        "from 3,812 conversions."
                    ),
                    "similarity": 0.8,
                }
            ]

    agent = RAGAgent.__new__(RAGAgent)
    agent.retriever = FakeRetriever()
    agent.top_k = 1

    response = agent.retrieve("What were the results of CMP-021?")

    assert response["evidence"][0]["entity_match"] is True
    assert response["sources"] == [
        {
            "document_id": "DOC-1",
            "filename": "campaign.docx",
            "title": "Campaign CMP-021",
            "document_type": "report",
            "page_number": None,
            "paragraph_number": 3,
            "chunk_id": "DOC-1-001",
        }
    ]


@pytest.mark.unit
def test_answer_composition_formats_sql_and_rag_evidence():
    answer = AnswerComposer().compose(
        {
            "route": "BOTH",
            "question": "What were the results of campaign CMP-021?",
            "sql": {
                "result": {
                    "columns": ["campaign_id", "roi_percent"],
                    "rows": [["CMP-021", 186.41]],
                }
            },
            "rag": {
                "evidence": [
                    {
                        "document_id": "DOC-1",
                        "title": "Campaign report",
                        "content": (
                            "Campaign CMP-021 exceeded its revenue target "
                            "with strong conversion performance."
                        ),
                    }
                ]
            },
        }
    )

    assert "Database Results" in answer
    assert "**Campaign:** CMP-021" in answer
    assert "**ROI:** 186.41%" in answer
    assert "Supporting Document Evidence" in answer


@pytest.mark.unit
def test_verification_requires_route_evidence():
    verifier = VerificationAgent()
    composer = AnswerComposer()
    sql_result = {
        "validation": {"valid": True},
        "query_plan": {"intent": "CUSTOMER_COUNT"},
        "result": {"columns": ["customer_count"], "rows": [[12]]},
    }
    verified = verifier.verify(
        composer.compose({"route": "SQL", "sql": sql_result}),
        "SQL",
        sql_result=sql_result,
    )
    unverified = verifier.verify(
        "Revenue was reported.",
        "RAG",
        rag_result={"evidence": []},
    )

    assert verified["verified"] is True
    assert unverified["verified"] is False
    assert "document evidence" in unverified["issues"][0]


@pytest.mark.unit
def test_verifier_rejects_sql_claim_not_in_rows():
    verifier = VerificationAgent()
    sql_result = {
        "validation": {"valid": True},
        "query_plan": {"intent": "CUSTOMER_COUNT"},
        "result": {"columns": ["customer_count"], "rows": [[12]]},
    }
    result = verifier.verify(
        "Here is what I found:\n- **Customers:** 120",
        "SQL",
        sql_result=sql_result,
    )
    assert result["verified"] is False
    assert "not reproduced from returned rows" in result["issues"][0]


@pytest.mark.unit
def test_verifier_checks_ranking_order_and_metric():
    verifier = VerificationAgent()
    sql_result = {
        "sql": "SELECT product_name, units_sold FROM products ORDER BY units_sold DESC;",
        "validation": {"valid": True},
        "query_plan": {"intent": "TOP_PRODUCTS_BY_QUANTITY"},
        "result": {
            "columns": ["product_name", "units_sold"],
            "rows": [["Product A", 2], ["Product B", 9]],
        },
    }
    answer = AnswerComposer().compose({"route": "SQL", "sql": sql_result})
    result = verifier.verify(answer, "SQL", sql_result=sql_result)
    assert result["verified"] is False
    assert "not ordered by the expected metric" in result["issues"][-1]


@pytest.mark.unit
def test_verifier_rejects_rag_claim_outside_retrieved_excerpt():
    verifier = VerificationAgent()
    evidence = {
        "question": "What does the return policy say about refunds?",
        "evidence": [{
            "document_id": "DOC-1",
            "chunk_id": "DOC-1-001",
            "title": "Return Policy",
            "filename": "return_policy.pdf",
            "content": "Refunds are issued after returned items pass the inspection process.",
        }],
        "sources": [{"document_id": "DOC-1", "chunk_id": "DOC-1-001"}],
    }
    result = verifier.verify(
        "The refund is guaranteed within five days.",
        "RAG",
        rag_result=evidence,
        question=evidence["question"],
    )
    assert result["verified"] is False
    assert "not reproduced from retrieved excerpts" in result["issues"][0]


@pytest.mark.unit
def test_verifier_requires_retrieved_source_reference():
    verifier = VerificationAgent()
    evidence = {
        "evidence": [{
            "document_id": "DOC-1",
            "chunk_id": "DOC-1-001",
            "title": "Return Policy",
            "filename": "return_policy.pdf",
            "content": "Refunds are issued after returned items pass the inspection process.",
        }],
        "sources": [{"document_id": "DOC-2", "chunk_id": "DOC-2-004"}],
    }
    answer = AnswerComposer().compose({
        "route": "RAG",
        "question": "What does the return policy say?",
        "rag": evidence,
    })
    result = verifier.verify(answer, "RAG", rag_result=evidence, question="What does the return policy say?")
    assert result["verified"] is False
    assert "does not match retrieved source metadata" in result["issues"][0]


@pytest.mark.unit
def test_rag_selection_rejects_uncovered_specific_question_aspect():
    evidence = [{
        "document_id": "DOC-1",
        "chunk_id": "DOC-1-001",
        "title": "Return Policy",
        "filename": "return_policy.pdf",
        "content": "Refunds are issued after returned items pass the inspection process.",
    }]
    selected = AnswerComposer().select_relevant_evidence(
        evidence,
        "What does the policy say about interplanetary refunds?",
    )
    assert selected == []


@pytest.mark.unit
def test_orchestrator_clarifies_material_sql_ambiguities():
    from types import SimpleNamespace
    from backend.app.orchestration.orchestrator import Orchestrator

    orchestrator = object.__new__(Orchestrator)
    orchestrator.sql_agent = SimpleNamespace(schema={"tables": {"customers": {"columns": [
        {"column_name": "customer_id"}, {"column_name": "age"},
    ]}}})
    orchestrator.rag_agent = SimpleNamespace(
        _explicit_document_type_filter=lambda _question: None
    )
    assert "calendar year" in orchestrator._clarification_needed("sales last year")
    assert "city, state, or country" in orchestrator._clarification_needed("customers by location")
    assert "quantity sold or by revenue" in orchestrator._clarification_needed("top products")
    assert "is present in the database" in orchestrator._clarification_needed("customers by age")
    assert "ROI, revenue, spend, or conversions" in orchestrator._clarification_needed("top campaigns")
    assert "specific filter is not supported" in orchestrator._clarification_needed("orders where payment status is failed")


@pytest.mark.unit
def test_conflicting_document_excerpts_remain_attributed_and_qualified():
    question = "What does the return policy say?"
    evidence = {
        "evidence": [
            {
                "document_id": "DOC-1", "chunk_id": "DOC-1-1",
                "title": "Return Policy A", "filename": "policy_a.pdf",
                "content": "Eligible returns must be requested within 30 calendar days of delivery.",
            },
            {
                "document_id": "DOC-2", "chunk_id": "DOC-2-1",
                "title": "Return Policy B", "filename": "policy_b.pdf",
                "content": "Eligible returns must be requested within 14 calendar days of delivery.",
            },
        ],
        "sources": [
            {"document_id": "DOC-1", "chunk_id": "DOC-1-1"},
            {"document_id": "DOC-2", "chunk_id": "DOC-2-1"},
        ],
    }
    answer = AnswerComposer().compose({"route": "RAG", "question": question, "rag": evidence})
    assert "any differences have not been reconciled" in answer
    assert "Return Policy A" in answer and "Return Policy B" in answer
    assert VerificationAgent().verify(answer, "RAG", rag_result=evidence, question=question)["verified"]


@pytest.mark.unit
def test_paraphrase_synonyms_retain_supported_return_policy_evidence():
    evidence = [{
        "document_id": "DOC-POL-001",
        "chunk_id": "DOC-POL-001-002",
        "title": "Return Refund Policy",
        "filename": "return_refund_policy.pdf",
        "document_type": "POLICIES",
        "content": (
            "Eligible products may generally be returned within 30 calendar "
            "days, subject to product-specific conditions."
        ),
    }]
    selected = AnswerComposer().select_relevant_evidence(
        evidence,
        "How long after buying something can a customer send it back for a refund?",
    )
    assert [item["document_id"] for item in selected] == ["DOC-POL-001"]


@pytest.mark.unit
def test_explicit_policy_facets_select_both_documents_and_verify_coverage():
    question = "What do the return policy and customer service policy say about refunds?"
    evidence = {
        "evidence": [
            {
                "document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002",
                "title": "Return Refund Policy", "filename": "return_refund_policy.pdf",
                "document_type": "POLICIES",
                "content": "Eligible returns may receive a refund within 30 calendar days.",
                "similarity": 0.55,
            },
            {
                "document_id": "DOC-POL-003", "chunk_id": "DOC-POL-003-004",
                "title": "Customer Service Policy", "filename": "customer_service_policy.pdf",
                "document_type": "POLICIES",
                "content": "Customer support handles refund disputes and escalations after reviewing customer account details.",
                "similarity": 0.40,
            },
        ],
        "sources": [
            {"document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002"},
            {"document_id": "DOC-POL-003", "chunk_id": "DOC-POL-003-004"},
        ],
    }
    answer = AnswerComposer().compose({"route": "RAG", "question": question, "rag": evidence})
    result = VerificationAgent().verify(
        answer, "RAG", rag_result=evidence, question=question
    )
    assert "Return Refund Policy" in answer
    assert "Customer Service Policy" in answer
    assert result["verified"] is True
    assert "Every explicitly requested document facet is represented." in result["checks"]


@pytest.mark.unit
def test_incomplete_multi_document_answer_is_qualified_and_unverified():
    question = "What do the return policy and customer service policy say about refunds?"
    evidence = {
        "evidence": [{
            "document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002",
            "title": "Return Refund Policy", "filename": "return_refund_policy.pdf",
            "document_type": "POLICIES",
            "content": "Eligible returns may receive a refund within 30 calendar days.",
        }],
        "sources": [{"document_id": "DOC-POL-001", "chunk_id": "DOC-POL-001-002"}],
    }
    answer = AnswerComposer().compose({"route": "RAG", "question": question, "rag": evidence})
    result = VerificationAgent().verify(
        answer, "RAG", rag_result=evidence, question=question
    )
    assert "not evidence for every requested document" in answer
    assert result["verified"] is False
    assert "customer service policy" in result["issues"][-1]


@pytest.mark.unit
def test_return_policy_plus_count_routes_hybrid_and_eligibility_routes_rag():
    from backend.app.orchestration.orchestrator import Orchestrator

    assert Orchestrator._route_question(
        "What does the return policy say, and how many returns were recorded?"
    ) == "BOTH"
    assert Orchestrator._route_question(
        "Can customers return lunar purchases for a refund?"
    ) == "RAG"


@pytest.mark.unit
def test_document_type_filter_requires_explicit_request():
    assert RAGAgent._explicit_document_type_filter(
        "Only policy documents: what does the return policy say?"
    ) == ["POLICIES"]
    assert RAGAgent._explicit_document_type_filter(
        "What does the return policy say?"
    ) is None


@pytest.mark.unit
def test_paraphrased_shipping_question_selects_both_requested_aspects():
    question = "How long does shipping take, and what happens if delivery is delayed?"
    evidence = [
        {
            "document_id": "DOC-POL-002", "chunk_id": "DOC-POL-002-001",
            "title": "Shipping Policy", "filename": "shipping_policy.pdf",
            "content": "Standard shipping delivery usually takes 3 to 5 business days after dispatch.",
        },
        {
            "document_id": "DOC-OPS-004", "chunk_id": "DOC-OPS-004-004",
            "title": "Delivery Exception SOP", "filename": "delivery_exception_SOP.pdf",
            "content": "When a delivery delay is reported, support checks carrier scans and contacts customers with a revised estimate.",
        },
    ]
    selected = AnswerComposer().select_relevant_evidence(evidence, question)
    assert {item["document_id"] for item in selected} == {"DOC-POL-002", "DOC-OPS-004"}


# ---------------------------------------------------------------------------
# Auto-routing regression tests
# ---------------------------------------------------------------------------

from backend.app.orchestration.orchestrator import Orchestrator


@pytest.mark.unit
@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are the return resolutions?", "SQL"),
        ("What strategy was recommended for campaign CMP-021?", "RAG"),
        ("What was the performance of campaign CMP-021?", "SQL"),
        ("What are the CMP-021 campaign metrics and recommended strategy?", "BOTH"),
        ("What is the NovaMart return and refund policy?", "RAG"),
        (
            "What were the results of campaign CMP-021 and what strategy "
            "was recommended?",
            "BOTH",
        ),
        ("Hello", "CHAT"),
        ("How many returns were made?", "SQL"),
        ("What are the return reasons?", "SQL"),
        ("What is the return rate?", "SQL"),
    ],
)
def test_auto_routing(question, expected):
    assert Orchestrator._route_question(question) == expected


@pytest.mark.unit
@pytest.mark.unit
def test_manual_mode_is_not_supported():
    import inspect

    parameters = inspect.signature(
        Orchestrator.answer
    ).parameters

    assert "mode" not in parameters


@pytest.mark.unit
def test_return_reasons_route_to_sql():
    assert (
        Orchestrator._route_question(
            "What are the return reasons?"
        )
        == "SQL"
    )


# ---------------------------------------------------------------------------
# BOTH evidence relevance: campaign-ID questions
# ---------------------------------------------------------------------------

_PAD = " The campaign delivered measurable results across channels this quarter."


def _chunk(doc_id, title, filename, content, entities, similarity=0.5):
    return {
        "chunk_id": f"{doc_id}-001",
        "document_id": doc_id,
        "filename": filename,
        "title": title,
        "document_type": "report",
        "page_number": None,
        "paragraph_number": 1,
        "related_entity_ids": entities,
        "content": content + _PAD,
        "similarity": similarity,
    }


_OTHER_CAMPAIGNS = [
    _chunk(
        "DOC-007", "Campaign Postmortem CMP-007",
        "campaign_postmortem_CMP-007.docx",
        "Campaign CMP-007 underperformed because of weak targeting.",
        ["CMP-007"], 0.9,
    ),
    _chunk(
        "DOC-012", "Campaign Postmortem CMP-012",
        "campaign_postmortem_CMP-012.docx",
        "Campaign CMP-012 overspent its budget on display ads.",
        ["CMP-012"], 0.9,
    ),
    _chunk(
        "DOC-034", "Campaign Postmortem CMP-034",
        "campaign_postmortem_CMP-034.docx",
        "Campaign CMP-034 had high click volume but low conversions.",
        ["CMP-034"], 0.9,
    ),
]

_CMP021_DOC = _chunk(
    "DOC-021", "Campaign Postmortem CMP-021",
    "campaign_postmortem_CMP-021.docx",
    "Campaign CMP-021 exceeded its revenue target with strong conversions.",
    ["CMP-021"], 0.5,
)

_MULTI_REPORT = _chunk(
    "DOC-Q2", "Campaign Performance Q2",
    "campaign_performance_Q2.pdf",
    "Campaign CMP-021 led the quarter while CMP-007, CMP-012 and CMP-034 "
    "trailed on revenue and conversions.",
    ["CMP-021", "CMP-007", "CMP-012", "CMP-034"], 0.5,
)


def _rag_agent_returning(chunks):
    class FakeRetriever:
        def search(self, query, top_k):
            return list(chunks)

    agent = RAGAgent.__new__(RAGAgent)
    agent.retriever = FakeRetriever()
    agent.top_k = 5
    return agent


@pytest.mark.unit
def test_cmp021_question_excludes_other_campaign_sources():
    question = "What strategy was recommended for campaign CMP-021?"
    agent = _rag_agent_returning(_OTHER_CAMPAIGNS + [_CMP021_DOC])

    result = agent.retrieve(question)

    ids = {source["document_id"] for source in result["sources"]}
    assert ids == {"DOC-021"}


@pytest.mark.unit
def test_cmp021_strategy_query_expansion_is_source_specific():
    question = (
        "What were the results of campaign CMP-021 and what strategy "
        "was recommended?"
    )
    expanded = RAGAgent._expand_retrieval_query(question)

    assert "Future campaigns should compare conversion efficiency" in expanded
    other_campaign = RAGAgent._expand_retrieval_query(
        "What strategy was recommended for campaign CMP-022?"
    )
    assert "Future campaigns should compare conversion efficiency" not in other_campaign


@pytest.mark.unit
@pytest.mark.parametrize("question", [
    (
        "What were the results of campaign CMP-021 and what strategy "
        "was recommended?"
    ),
    "What are the CMP-021 campaign metrics and recommended strategy?",
])
def test_cmp021_strategy_composition_requires_both_postmortem_facets(question):
    evidence = [
        {
            "chunk_id": "DOC-MKT-024-006",
            "document_id": "DOC-MKT-024",
            "filename": "campaign_postmortem_CMP-021.docx",
            "title": "Campaign Postmortem Cmp-021",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "The report highlights alignment between the target segment, "
                "campaign objective, channel selection, and conversion-oriented "
                "creative as factors to investigate. These are analytical "
                "observations for the synthetic dataset, not claims about a "
                "real company."
            ),
            "similarity": 0.62,
        },
        {
            "chunk_id": "DOC-MKT-024-008",
            "document_id": "DOC-MKT-024",
            "filename": "campaign_postmortem_CMP-021.docx",
            "title": "Campaign Postmortem Cmp-021",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Future campaigns should compare conversion efficiency, "
                "customer segment quality, and incremental revenue before "
                "increasing spend."
            ),
            "similarity": 0.67,
        },
        {
            "chunk_id": "DOC-MKT-002-001",
            "document_id": "DOC-MKT-002",
            "filename": "campaign_strategy.pdf",
            "title": "Campaign Strategy",
            "content": (
                "CMP-021 Campaigns should define a measurable objective, "
                "target segment, target region, and conversion event."
            ),
            "similarity": 0.8,
        },
    ]
    composer = AnswerComposer()
    selected = composer.select_relevant_evidence(evidence, question)

    assert [item["chunk_id"] for item in selected] == [
        "DOC-MKT-024-006", "DOC-MKT-024-008"
    ]
    assert composer._missing_document_facets(question, selected) == []
    assert "campaign strategy/recommendation" in composer._missing_document_facets(
        question, selected[:1]
    )
    assert "campaign factors to investigate" in composer._missing_document_facets(
        question, selected[1:]
    )
    if "metrics" in question:
        assert composer.select_relevant_evidence(evidence[:1], question) == []
        assert composer.select_relevant_evidence(evidence[1:2], question) == []

    sql_result = {
        "sql": (
            "SELECT campaign_id, campaign_name, actual_spend, "
            "revenue_generated, conversions, clicks "
            "FROM marketing_campaigns WHERE campaign_id = 'CMP-021';"
        ),
        "validation": {"valid": True},
        "query_plan": {
            "intent": "CAMPAIGN_PERFORMANCE",
            "entity_id": "CMP-021",
            "filters": [{"column": "campaign_id", "operator": "=", "value": "CMP-021"}],
        },
        "result": {
            "columns": [
                "campaign_id", "campaign_name", "actual_spend",
                "revenue_generated", "conversions", "clicks",
            ],
            "rows": [["CMP-021", "NovaMart campaign 21", 100.0, 250.0, 12, 50]],
        },
    }
    rag_result = {
        "evidence": evidence,
        "sources": [
            {"document_id": row["document_id"], "chunk_id": row["chunk_id"]}
            for row in evidence
        ],
    }
    answer = composer.compose({
        "route": "BOTH",
        "question": question,
        "sql": sql_result,
        "rag": rag_result,
    })
    verification = VerificationAgent().verify(
        answer,
        "BOTH",
        sql_result=sql_result,
        rag_result=rag_result,
        question=question,
    )
    assert "not establish them as causes of CMP-021's results" in answer
    assert "future-campaign recommendation" in answer.lower()
    assert verification["verified"] is True


@pytest.mark.unit
def test_cmp021_composition_never_presents_other_campaigns():
    question = "What were the results of campaign CMP-021?"
    evidence = _OTHER_CAMPAIGNS + [_CMP021_DOC]

    answer = AnswerComposer().compose(
        {
            "route": "BOTH",
            "question": question,
            "sql": {"result": {"columns": [], "rows": []}},
            "rag": {"evidence": evidence},
        }
    )

    assert "CMP-021" in answer
    for other in ("CMP-007", "CMP-012", "CMP-034"):
        assert other not in answer


@pytest.mark.unit
def test_specific_evidence_is_preferred_over_multi_campaign_report():
    selected = AnswerComposer().select_relevant_evidence(
        [_MULTI_REPORT, _CMP021_DOC],
        "What were the results of campaign CMP-021?",
    )

    assert [item["document_id"] for item in selected] == ["DOC-021"]


@pytest.mark.unit
def test_multi_campaign_report_is_labelled_general_context():
    answer = AnswerComposer().compose(
        {
            "route": "BOTH",
            "question": "What were the results of campaign CMP-021?",
            "sql": {"result": {"columns": [], "rows": []}},
            "rag": {"evidence": [_MULTI_REPORT]},
        }
    )

    assert "general context" in answer


@pytest.mark.unit
def test_no_cmp021_documents_yields_no_evidence():
    selected = AnswerComposer().select_relevant_evidence(
        _OTHER_CAMPAIGNS,
        "What were the results of campaign CMP-021?",
    )

    assert selected == []


@pytest.mark.unit
def test_policy_retrieval_without_entity_is_unchanged():
    policy = _chunk(
        "DOC-POL", "Return Policy", "return_policy.docx",
        "Customers may return products within 30 days for a refund.",
        [], 0.7,
    )
    agent = _rag_agent_returning([policy])

    result = agent.retrieve("What is the NovaMart return and refund policy?")

    assert [s["document_id"] for s in result["sources"]] == ["DOC-POL"]

# ---------------------------------------------------------------------------
# General retrieval: related chunks and document metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_composer_keeps_chunks_linked_by_entity_metadata():
    """Relevant chunks must survive even when their text omits the entity ID."""

    evidence = [
        {
            "chunk_id": "DOC-021-001",
            "document_id": "DOC-MKT-024",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Campaign facts show strong revenue and conversion performance."
            ),
            "similarity": 0.8,
        },
        {
            "chunk_id": "DOC-021-002",
            "document_id": "DOC-MKT-024",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Observed drivers are factors to investigate and include target segment alignment, "
                "campaign objective, channel selection and conversion-oriented creative."
            ),
            "similarity": 0.7,
        },
        {
            "chunk_id": "DOC-021-003",
            "document_id": "DOC-MKT-024",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
            "Future campaigns should compare conversion efficiency, "
            "customer segment quality and incremental revenue before increasing spend."
            ),
            "similarity": 0.7,
        },
    ]

    selected = AnswerComposer().select_relevant_evidence(
        evidence,
        "Campaign results, observed drivers and recommendations for CMP-021.",
    )

    combined_content = " ".join(
        item.get("_clean_content", item.get("content", ""))
        for item in selected
    ).lower()

    assert "revenue" in combined_content
    assert "observed drivers" in combined_content
    assert "conversion efficiency" in combined_content


@pytest.mark.unit
def test_composer_preserves_multiple_relevant_sections_from_one_document():
    """A multi-part question must not lose a relevant section due to a fixed cap."""

    evidence = [
        {
            "chunk_id": "DOC-100-001",
            "document_id": "DOC-100",
            "title": "Marketing Analysis",
            "filename": "marketing_analysis.docx",
            "related_entity_ids": [],
            "content": (
                "Campaign performance results include revenue, spend "
                "and conversion measurements for the reporting period."
            ),
            "similarity": 0.9,
        },
        {
            "chunk_id": "DOC-100-002",
            "document_id": "DOC-100",
            "title": "Marketing Analysis",
            "filename": "marketing_analysis.docx",
            "related_entity_ids": [],
            "content": (
                "Observed drivers include audience targeting, channel "
                "selection and the quality of campaign creative."
            ),
            "similarity": 0.8,
        },
        {
            "chunk_id": "DOC-100-003",
            "document_id": "DOC-100",
            "title": "Marketing Analysis",
            "filename": "marketing_analysis.docx",
            "related_entity_ids": [],
            "content": (
                "Recommendations include improving audience segmentation "
                "and measuring incremental revenue before scaling spend."
            ),
            "similarity": 0.7,
        },
    ]

    selected = AnswerComposer().select_relevant_evidence(
        evidence,
        "Campaign results, observed drivers and recommendations.",
    )

    combined_content = " ".join(
        item.get("_clean_content", item.get("content", ""))
        for item in selected
    ).lower()

    assert "revenue" in combined_content
    assert "observed drivers" in combined_content
    assert "recommendations" in combined_content
