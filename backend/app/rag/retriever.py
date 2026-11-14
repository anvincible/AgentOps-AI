
from typing import Any
import os
import re

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from dotenv import load_dotenv
from backend.app.rag.embedder import DocumentEmbedder


# Load values from the project's .env file.
# The project root is four parent levels above this file.
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


class Retriever:
    """
    Retrieves document chunks using pgvector semantic similarity
    and reranks results using exact entity and keyword matches.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        host = host or os.getenv("DB_HOST", "localhost")
        port = port or int(os.getenv("DB_PORT", "5432"))
        database = database or os.getenv("DB_NAME", "novamart")
        user = user or os.getenv("DB_USER", "postgres")
        password = (
            password
            if password is not None
            else os.getenv("DB_PASSWORD", "")
        )

        self.connection_string = (
            f"host={host} "
            f"port={port} "
            f"dbname={database} "
            f"user={user} "
            f"password={password}"
        )

        self.embedder = DocumentEmbedder()

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search document chunks semantically, then rerank them."""

        if not query or not query.strip() or top_k <= 0:
            return []

        query_embedding = self.embedder.embed_text(query)
        query_vector = Vector(query_embedding)
        candidate_limit = max(top_k * 5, 25)

        allowed_document_types = {
            "MARKETING", "OPERATIONS", "POLICIES", "PRODUCTS", "REPORTS",
        }
        requested_types = [
            value.strip().upper()
            for value in (document_types or [])
        ]
        if not set(requested_types).issubset(allowed_document_types):
            raise ValueError("Unsupported document type metadata filter.")

        type_filter = ""
        params: tuple[Any, ...]
        if requested_types:
            type_filter = " AND document_type = ANY(%s)"
            params = (
                query_vector,
                requested_types,
                query_vector,
                candidate_limit,
            )
        else:
            params = (query_vector, query_vector, candidate_limit)

        search_query = """
            SELECT
                chunk_id,
                document_id,
                filename,
                file_type,
                title,
                document_type,
                department,
                document_date,
                version,
                region,
                related_entity_ids,
                page_number,
                paragraph_number,
                content,
                1 - (embedding <=> %s) AS similarity
            FROM document_chunks
            WHERE embedding IS NOT NULL
        """ + type_filter + """
            ORDER BY embedding <=> %s
            LIMIT %s;
        """

        with psycopg.connect(self.connection_string) as connection:
            register_vector(connection)

            with connection.cursor() as cursor:
                cursor.execute(
                    search_query,
                    params,
                )
                rows = cursor.fetchall()

        results: list[dict[str, Any]] = []

        for row in rows:
            item = {
                "chunk_id": row[0],
                "document_id": row[1],
                "filename": row[2],
                "file_type": row[3],
                "title": row[4],
                "document_type": row[5],
                "department": row[6],
                "document_date": row[7],
                "version": row[8],
                "region": row[9],
                "related_entity_ids": row[10],
                "page_number": row[11],
                "paragraph_number": row[12],
                "content": row[13] or "",
                "similarity": float(row[14]),
            }

            item["entity_match"] = self._has_entity_match(query, item)
            item["relevance_score"] = self._calculate_relevance(query, item)
            results.append(item)

        results.sort(
            key=lambda item: item["relevance_score"],
            reverse=True,
        )

        return results[:top_k]

    @staticmethod
    def _extract_entity_ids(text: str) -> set[str]:
        return {
            match.upper()
            for match in re.findall(
                r"\b[A-Z][A-Z0-9]*-\d+\b",
                text.upper(),
            )
        }

    @classmethod
    def _has_entity_match(
        cls,
        query: str,
        item: dict[str, Any],
    ) -> bool:
        query_entities = cls._extract_entity_ids(query)

        if not query_entities:
            return False

        related = item.get("related_entity_ids") or []

        if isinstance(related, str):
            document_entities = cls._extract_entity_ids(related)
        else:
            document_entities = set()
            for entity in related:
                document_entities.update(
                    cls._extract_entity_ids(str(entity))
                )

        document_entities.update(
            cls._extract_entity_ids(
                " ".join(
                    str(item.get(field) or "")
                    for field in ("title", "filename", "content")
                )
            )
        )

        return bool(query_entities & document_entities)

    @classmethod
    def _calculate_relevance(
        cls,
        query: str,
        item: dict[str, Any],
    ) -> float:
        """Combine semantic similarity with entity and keyword matches."""

        score = item.get("similarity", 0.0)

        if item.get("entity_match"):
            score += 0.25

        query_entities = cls._extract_entity_ids(query)
        title = str(item.get("title") or "").lower()
        filename = str(item.get("filename") or "").lower()
        content = str(item.get("content") or "").lower()

        for entity in query_entities:
            entity_lower = entity.lower()
            if entity_lower in title or entity_lower in filename:
                score += 0.15
                break

        stop_words = {
            "what", "were", "was", "the", "a", "an", "is", "are",
            "of", "for", "to", "in", "on", "and", "or", "by",
            "with", "how", "tell", "me", "about", "please",
        }

        terms = {
            term.lower()
            for term in re.findall(r"\b[a-zA-Z0-9]+\b", query)
            if len(term) > 2 and term.lower() not in stop_words
        }

        if terms:
            title_terms = set(re.findall(r"\b[a-zA-Z0-9]+\b", title))
            content_terms = set(re.findall(r"\b[a-zA-Z0-9]+\b", content))

            score += 0.10 * (
                len(terms & title_terms) / len(terms)
            )
            score += 0.05 * (
                len(terms & content_terms) / len(terms)
            )

        return score
