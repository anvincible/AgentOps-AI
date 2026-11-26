import pytest
from types import SimpleNamespace

from backend.app.orchestration.answer_composer import AnswerComposer
from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.database_config import load_database_config


@pytest.mark.unit
def test_defect_a_shipping_delay_routing():
    """Verify procedural shipping questions route to RAG while metrics route to SQL."""
    procedural_q = "What should happen when a shipment is materially delayed?"
    metric_q = "What are the shipment delivery statistics?"

    assert Orchestrator._route_question(procedural_q) == "RAG"
    assert Orchestrator._route_question(metric_q) == "SQL"


@pytest.mark.unit
def test_defect_b_criteria_and_identify_aspect_coverage():
    """Verify premium customer segment criteria questions pass substantive aspect checks."""
    composer = AnswerComposer()
    question = "What criteria are used to identify premium customer segments?"

    evidence = [{
        "document_id": "DOC-MKT-030",
        "chunk_id": "DOC-MKT-030-001",
        "title": "Customer Segmentation Strategy",
        "filename": "customer_segmentation_strategy.docx",
        "department": "Marketing",
        "content": (
            "Premium and Loyal customer segments are defined based on lifetime "
            "value thresholds, retention priority, and repeat purchase patterns."
        ),
    }]

    assert composer._question_aspects_covered(question, evidence) is True
    selected = composer.select_relevant_evidence(evidence, question)
    assert len(selected) == 1
    assert selected[0]["document_id"] == "DOC-MKT-030"


@pytest.mark.unit
def test_defect_c_warranty_abstention_for_unsupported_product():
    """Ensure product-specific warranty queries without matching evidence abstain cleanly."""
    composer = AnswerComposer()
    question = "What is the warranty policy for product PROD-00001?"

    # Only general warranty guide chunk, without PROD-00001
    evidence = [{
        "document_id": "DOC-PRD-003",
        "chunk_id": "DOC-PRD-003-001",
        "title": "NovaMart Warranty Guide",
        "filename": "warranty_guide.docx",
        "department": "Product Management",
        "content": "All standard NovaMart consumer goods are covered by standard limited warranty terms.",
    }]

    # Aspects covered check should reject or select nothing because PROD-00001 entity is not covered
    selected = composer.select_relevant_evidence(evidence, question)
    assert len(selected) == 0


@pytest.mark.unit
def test_defect_d_seller_onboarding_short_procedural_steps_accepted():
    """Ensure short numbered procedural steps (5+ words) are treated as substantive."""
    composer = AnswerComposer()
    question = "What are the steps in the seller onboarding workflow?"

    evidence = [
        {
            "document_id": "DOC-OPS-001",
            "chunk_id": "DOC-OPS-001-001",
            "title": "Seller Onboarding SOP",
            "filename": "seller_onboarding_sop.docx",
            "department": "Operations",
            "content": "Step 1: Collect seller identity and business information.",
        },
        {
            "document_id": "DOC-OPS-001",
            "chunk_id": "DOC-OPS-001-002",
            "title": "Seller Onboarding SOP",
            "filename": "seller_onboarding_sop.docx",
            "department": "Operations",
            "content": "Step 2: Assign seller category, segment, and acquisition channel.",
        },
    ]

    selected = composer.select_relevant_evidence(evidence, question)
    assert len(selected) >= 1
    assert "Step 1" in selected[0]["_clean_content"]


@pytest.mark.unit
def test_defect_e_campaign_comparison_clarification_preserves_hybrid_metadata():
    """Verify clarification captures intended_route='BOTH' and resolves with recommendations."""
    orchestrator = object.__new__(Orchestrator)
    orchestrator.sql_agent = SimpleNamespace(schema={"tables": {"marketing_campaigns": {"columns": [
        {"column_name": "campaign_id"}, {"column_name": "spend"}, {"column_name": "revenue"}
    ]}}})
    orchestrator.rag_agent = SimpleNamespace(
        _explicit_document_type_filter=lambda _q: None
    )

    q1 = "Compare the campaigns and summarize their documented recommendations."
    clarify_text = orchestrator._clarification_needed(q1)
    assert clarify_text is not None

    meta = orchestrator._clarification_metadata(q1, clarify_text)
    assert meta["intended_route"] == "BOTH"
    assert meta["requires_hybrid"] is True

    resolved_q = Orchestrator._resolve_clarification("CMP-021 and CMP-022.", meta)
    assert resolved_q is not None
    assert "CMP-021" in resolved_q and "CMP-022" in resolved_q
    assert "recommendations" in resolved_q.lower()
    assert Orchestrator._route_question(resolved_q) == "BOTH"


@pytest.mark.integration
def test_live_defect_a_through_e_pipeline():
    """Live database integration test validating end-to-end fixes for Defects A through E."""
    cfg = load_database_config()
    orchestrator = Orchestrator(
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )

    # Defect A
    res_a1 = orchestrator.answer("What should happen when a shipment is materially delayed?")
    assert res_a1["route"] == "RAG"
    doc_sources_a1 = [s["document_id"] for s in res_a1["sources"] if s.get("type") == "document"]
    assert "DOC-POL-002" in doc_sources_a1

    res_a2 = orchestrator.answer("What are the shipment delivery statistics?")
    assert res_a2["route"] == "SQL"

    # Defect B
    res_b = orchestrator.answer("What criteria are used to identify premium customer segments?")
    assert res_b["route"] == "RAG"
    doc_sources_b = [s["document_id"] for s in res_b["sources"] if s.get("type") == "document"]
    assert any(doc_id in doc_sources_b for doc_id in ("DOC-MKT-030", "DOC-MKT-001"))

    # Defect C
    res_c_valid = orchestrator.answer("What is the warranty policy for product PROD-00441?")
    assert res_c_valid["route"] == "RAG"
    doc_sources_c = [s["document_id"] for s in res_c_valid["sources"] if s.get("type") == "document"]
    assert "DOC-PRD-001" in doc_sources_c

    res_c_abstain = orchestrator.answer("What is the warranty policy for product PROD-00001?")
    assert res_c_abstain["route"] == "RAG"
    doc_sources_c_abstain = [s["document_id"] for s in res_c_abstain["sources"] if s.get("type") == "document"]
    assert doc_sources_c_abstain == []
    assert "could not find" in res_c_abstain["answer"].lower()

    # Defect D
    res_d_steps = orchestrator.answer("What are the steps in the seller onboarding workflow?")
    assert res_d_steps["route"] == "RAG"
    doc_sources_d = [s["document_id"] for s in res_d_steps["sources"] if s.get("type") == "document"]
    assert "DOC-OPS-001" in doc_sources_d

    res_d_roles = orchestrator.answer("What are the key responsibilities in the seller onboarding process?")
    assert res_d_roles["route"] == "RAG"
    doc_sources_d_roles = [s["document_id"] for s in res_d_roles["sources"] if s.get("type") == "document"]
    assert doc_sources_d_roles == []
    assert "could not find" in res_d_roles["answer"].lower()

    # Defect E
    turn1 = orchestrator.answer("Compare the campaigns and summarize their documented recommendations.")
    assert turn1["route"] == "CLARIFY"
    ctx = turn1.get("clarification_context") or turn1.get("clarification")
    assert ctx["intended_route"] == "BOTH"

    turn2 = orchestrator.answer("CMP-021 and CMP-022.", clarification_context=ctx)
    assert turn2["route"] == "BOTH"
    source_types = [s.get("type") for s in turn2["sources"]]
    assert "sql" in source_types
    assert "document" in source_types
    assert any(s.get("document_id") == "DOC-MKT-024" for s in turn2["sources"])
