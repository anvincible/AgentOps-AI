"""
Documents & Knowledge Base endpoints for AgentOps AI.

Provides:
- GET /documents (list all documents with metadata & chunk counts)
- GET /documents/{document_id} (detail view with extracted text & metadata)
- GET /documents/{document_id}/chunks (individual chunk-level inspection)
"""

from typing import Any
import logging
from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

from backend.app.database_config import load_database_config
from backend.app.safe_logging import log_sanitized_exception

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


def _get_connection():
    config = load_database_config()
    db_params = dict(config)
    if "database" in db_params:
        db_params["dbname"] = db_params.pop("database")
    return psycopg.connect(**db_params, row_factory=dict_row)


@router.get("/documents")
@router.get("/api/documents")
def list_documents() -> list[dict[str, Any]]:
    """Return catalogue of all 36 documents with metadata and chunk counts."""
    query = """
        SELECT 
            document_id,
            MIN(title) AS title,
            MIN(filename) AS filename,
            MIN(document_type) AS document_type,
            MIN(department) AS department,
            MIN(version) AS version,
            TO_CHAR(MIN(document_date), 'YYYY-MM-DD') AS document_date,
            MIN(region) AS region,
            COUNT(*) AS chunk_count
        FROM document_chunks
        GROUP BY document_id
        ORDER BY document_id;
    """
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
    except Exception as exc:
        log_sanitized_exception(logger, "Failed to list documents", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve document catalogue.") from None


@router.get("/documents/{document_id}")
@router.get("/api/documents/{document_id}")
def get_document_detail(document_id: str) -> dict[str, Any]:
    """Return document metadata, summary statistics, and reconstructed extracted text."""
    doc_id = document_id.strip()
    query = """
        SELECT 
            chunk_id,
            page_number,
            paragraph_number,
            title,
            filename,
            document_type,
            department,
            version,
            TO_CHAR(document_date, 'YYYY-MM-DD') AS document_date,
            region,
            related_entity_ids,
            content
        FROM document_chunks
        WHERE document_id = %s
        ORDER BY chunk_id, page_number, paragraph_number;
    """
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (doc_id,))
                chunks = cur.fetchall()

        if not chunks:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

        first = chunks[0]
        # Reconstruct extracted text from ordered chunks
        extracted_text = "\n\n".join(
            chunk["content"].strip() for chunk in chunks if chunk.get("content")
        )

        all_entities: list[str] = []
        for c in chunks:
            rel = c.get("related_entity_ids")
            if isinstance(rel, list):
                all_entities.extend(str(item) for item in rel if item)
            elif isinstance(rel, str) and rel.strip():
                all_entities.extend(item.strip() for item in rel.split(",") if item.strip())

        unique_entities = sorted(list(dict.fromkeys(all_entities)))

        return {
            "document_id": doc_id,
            "title": first.get("title") or doc_id,
            "filename": first.get("filename"),
            "document_type": first.get("document_type"),
            "department": first.get("department"),
            "version": first.get("version"),
            "document_date": first.get("document_date"),
            "region": first.get("region"),
            "chunk_count": len(chunks),
            "related_entities": unique_entities,
            "extracted_text": extracted_text,
            "chunks_preview": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "page_number": c.get("page_number"),
                    "paragraph_number": c.get("paragraph_number"),
                    "content_preview": (c.get("content") or "")[:200] + ("..." if len(c.get("content") or "") > 200 else ""),
                }
                for c in chunks
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to retrieve document {doc_id}", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve document details.") from None


@router.get("/documents/{document_id}/chunks")
@router.get("/api/documents/{document_id}/chunks")
def get_document_chunks(document_id: str) -> dict[str, Any]:
    """Return all chunk records and text for granular chunk-level inspection."""
    doc_id = document_id.strip()
    query = """
        SELECT 
            chunk_id,
            document_id,
            page_number,
            paragraph_number,
            title,
            filename,
            document_type,
            department,
            version,
            TO_CHAR(document_date, 'YYYY-MM-DD') AS document_date,
            region,
            related_entity_ids,
            content
        FROM document_chunks
        WHERE document_id = %s
        ORDER BY chunk_id;
    """
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (doc_id,))
                chunks = cur.fetchall()

        if not chunks:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

        return {
            "document_id": doc_id,
            "total_chunks": len(chunks),
            "chunks": chunks,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to retrieve chunks for {doc_id}", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve document chunks.") from None
