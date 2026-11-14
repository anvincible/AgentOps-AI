import pytest

from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.document_cleaner import DocumentCleaner
from backend.app.rag.document_loader import DocumentLoader


@pytest.mark.unit
def test_document_cleaner_removes_notices_and_normalizes_text():
    cleaner = DocumentCleaner()
    cleaned = cleaner.clean_text(
        " SYNTHETIC DOCUMENT — NOVAMART \r\n"
        "  Return   within 30 days. \r\n\r\n"
        "Academic dataset for AgentOps AI. This document is fictional and "
        "does not represent a real company's internal document."
    )

    assert cleaned == "Return within 30 days."


@pytest.mark.unit
def test_document_cleaner_preserves_content_metadata():
    document = {
        "document_id": "DOC-1",
        "content": [
            {"page_number": 2, "text": "  Useful policy text.  "},
            {"page_number": 3, "text": "   "},
        ],
    }

    cleaned = DocumentCleaner().clean_document(document)

    assert cleaned["content"] == [
        {"page_number": 2, "text": "Useful policy text."}
    ]


@pytest.mark.unit
def test_chunker_preserves_metadata_and_overlap():
    document = {
        "document_id": "DOC-1",
        "filename": "policy.pdf",
        "file_type": "pdf",
        "title": "Return Policy",
        "document_type": "policy",
        "department": "Operations",
        "date": "2025-01-01",
        "version": "1",
        "region": "IN",
        "related_entity_ids": ["RET-1"],
        "content": [
            {
                "page_number": 1,
                "text": "First sentence has useful details. "
                "Second sentence continues the policy. "
                "Third sentence explains the exception.",
            }
        ],
    }

    chunks = DocumentChunker(chunk_size=55, chunk_overlap=12).chunk_document(
        document
    )

    assert len(chunks) > 1
    assert all(chunk["document_id"] == "DOC-1" for chunk in chunks)
    assert all(chunk["page_number"] == 1 for chunk in chunks)
    assert any(
        set(chunks[index]["text"].split())
        & set(chunks[index + 1]["text"].split())
        for index in range(len(chunks) - 1)
    )


@pytest.mark.unit
def test_document_loader_preserves_real_document_metadata():
    loader = DocumentLoader()
    document = loader.load(
        "data/novamart/documents/marketing/"
        "campaign_postmortem_CMP-021.docx"
    )

    assert document["document_id"]
    assert document["filename"] == "campaign_postmortem_CMP-021.docx"
    assert "CMP-021" in document["related_entity_ids"]
    assert all(item["paragraph_number"] for item in document["content"])
