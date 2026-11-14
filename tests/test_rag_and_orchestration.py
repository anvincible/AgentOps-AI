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

    verified = verifier.verify(
        "Revenue was reported.",
        "SQL",
        sql_result={"result": {"rows": [["CMP-021"]]}}
    )
    unverified = verifier.verify(
        "Revenue was reported.",
        "RAG",
        rag_result={"evidence": []},
    )

    assert verified["verified"] is True
    assert unverified["verified"] is False
    assert "document evidence" in unverified["issues"][0]


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
            "document_id": "DOC-021",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Campaign facts show strong revenue and conversion "
                "performance across the reporting period."
            ),
            "similarity": 0.8,
        },
        {
            "chunk_id": "DOC-021-002",
            "document_id": "DOC-021",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Observed drivers include target segment alignment, "
                "channel selection and conversion-oriented creative."
            ),
            "similarity": 0.7,
        },
        {
            "chunk_id": "DOC-021-003",
            "document_id": "DOC-021",
            "title": "Campaign Postmortem",
            "filename": "campaign_postmortem.docx",
            "related_entity_ids": ["CMP-021"],
            "content": (
                "Future campaigns should compare conversion efficiency, "
                "customer segment quality and incremental revenue."
            ),
            "similarity": 0.7,
        },
    ]

    selected = AnswerComposer().select_relevant_evidence(
        evidence,
        "What were the results, observed drivers and recommendations "
        "for campaign CMP-021?",
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
        "Summarize campaign results, observed drivers and recommendations.",
    )

    combined_content = " ".join(
        item.get("_clean_content", item.get("content", ""))
        for item in selected
    ).lower()

    assert "revenue" in combined_content
    assert "observed drivers" in combined_content
    assert "recommendations" in combined_content
