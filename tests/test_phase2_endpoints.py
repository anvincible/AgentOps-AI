"""
Unit and integration tests for Phase 2 API endpoints:
- Phase 2A: Documents & Knowledge Base (/api/documents)
- Phase 2B: Data Explorer (/api/data)
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.api.main import app

client = TestClient(app)


@pytest.mark.unit
def test_list_documents_endpoint():
    response = client.get("/api/documents")
    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) == 36
    first = docs[0]
    for key in ("document_id", "title", "filename", "document_type", "department", "chunk_count"):
        assert key in first


@pytest.mark.unit
def test_document_detail_endpoint():
    response = client.get("/api/documents/DOC-POL-001")
    assert response.status_code == 200
    detail = response.json()
    assert detail["document_id"] == "DOC-POL-001"
    assert detail["chunk_count"] == 2
    assert "Return" in detail["title"] or "return" in detail["title"].lower()
    assert len(detail["extracted_text"]) > 0
    assert "chunks_preview" in detail


@pytest.mark.unit
def test_document_detail_not_found():
    response = client.get("/api/documents/DOC-NON-EXISTENT")
    assert response.status_code == 404


@pytest.mark.unit
def test_document_chunks_endpoint():
    response = client.get("/api/documents/DOC-POL-001/chunks")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == "DOC-POL-001"
    assert data["total_chunks"] == 2
    assert len(data["chunks"]) == 2
    first_chunk = data["chunks"][0]
    assert "chunk_id" in first_chunk
    assert "content" in first_chunk


@pytest.mark.unit
def test_data_schema_endpoint():
    response = client.get("/api/data/schema")
    assert response.status_code == 200
    schema = response.json()
    assert "tables" in schema
    table_names = {t["table_name"] for t in schema["tables"]}
    assert "customers" in table_names
    assert "orders" in table_names
    assert "products" in table_names
    assert len(table_names) == 12


@pytest.mark.unit
def test_data_table_records_pagination_and_sorting():
    response = client.get("/api/data/tables/customers?page=1&page_size=5&sort_by=customer_id&sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "customers"
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["rows"]) == 5
    assert data["total_rows"] == 10000


@pytest.mark.unit
def test_data_table_records_search():
    response = client.get("/api/data/tables/customers?search=Active&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "customers"
    assert data["total_rows"] > 0
    assert len(data["rows"]) <= 10


@pytest.mark.unit
def test_data_table_stats_endpoint():
    response = client.get("/api/data/tables/customers/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["table_name"] == "customers"
    assert stats["total_rows"] == 10000
    assert "numeric_metrics" in stats
    assert "categorical_breakdowns" in stats


@pytest.mark.unit
def test_data_table_security_rejects_disallowed_tables():
    # Attempt to query arbitrary or system tables
    response = client.get("/api/data/tables/pg_shadow")
    assert response.status_code == 404

    response = client.get("/api/data/tables/unknown_table_xyz")
    assert response.status_code == 404

    response = client.get("/api/data/tables/pg_shadow/stats")
    assert response.status_code == 404
