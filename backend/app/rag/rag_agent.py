
from typing import Any
import re

from backend.app.rag.retriever import Retriever


class RAGAgent:
    """
    RAG Agent for document-based questions.

    Retrieves document chunks and ranks them using semantic similarity,
    exact entity matches, content quality, and query-term relevance.

    This version does not use an LLM.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        top_k: int = 5,
    ):
        # None lets Retriever load the corresponding value from .env.
        self.retriever = Retriever(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        self.top_k = top_k

    def retrieve(self, question: str) -> dict[str, Any]:
        """Retrieve and rank evidence for a question."""

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        results = self.retriever.search(
            query=question,
            top_k=max(self.top_k * 5, 25),
        )

        ranked = self._rank_evidence(question, results)
        ranked = self._drop_other_entity_documents(question, ranked)

        return {
            "question": question,
            "evidence": ranked[:self.top_k],
            "sources": [
                {
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename"),
                    "title": item.get("title"),
                    "document_type": item.get("document_type"),
                    "page_number": item.get("page_number"),
                    "paragraph_number": item.get("paragraph_number"),
                    "chunk_id": item.get("chunk_id"),
                }
                for item in ranked[:self.top_k]
            ],
        }

    @classmethod
    def _rank_evidence(
        cls,
        question: str,
        evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank retrieved chunks using relevance and content quality."""

        query_entities = cls._extract_entity_ids(question)
        question_terms = {
            term.lower()
            for term in re.findall(r"\b[a-zA-Z0-9]+\b", question)
            if len(term) > 2
        }

        ranked = []

        for item in evidence:
            content = str(item.get("content") or "")
            title = str(item.get("title") or "")
            filename = str(item.get("filename") or "")
            related = item.get("related_entity_ids") or []

            text = f"{title} {filename} {content}".upper()

            if isinstance(related, str):
                related_text = related.upper()
            else:
                related_text = " ".join(str(value) for value in related).upper()

            entity_in_content = any(
                cls._contains_entity(content, entity)
                for entity in query_entities
            )
            entity_in_title = any(
                cls._contains_entity(title + " " + filename, entity)
                for entity in query_entities
            )
            entity_in_metadata = any(
                cls._contains_entity(related_text, entity)
                for entity in query_entities
            )

            score = float(
                item.get("relevance_score", item.get("similarity", 0.0))
            )

            if entity_in_content:
                score += 0.40
            elif entity_in_title:
                score += 0.25
            elif entity_in_metadata:
                score += 0.03

            if len(content.strip()) < 80:
                score -= 0.15
            elif len(content.strip()) >= 150:
                score += 0.05

            content_terms = {
                term.lower()
                for term in re.findall(r"\b[a-zA-Z0-9]+\b", content)
            }
            title_terms = {
                term.lower()
                for term in re.findall(r"\b[a-zA-Z0-9]+\b", title)
            }

            if question_terms:
                score += 0.10 * (
                    len(question_terms & title_terms) / len(question_terms)
                )
                score += 0.05 * (
                    len(question_terms & content_terms) / len(question_terms)
                )

            candidate = dict(item)
            candidate["evidence_score"] = score
            candidate["entity_match"] = (
                entity_in_content or entity_in_title or entity_in_metadata
            )
            candidate["entity_in_content"] = entity_in_content
            candidate["entity_in_title"] = entity_in_title
            candidate["entity_in_metadata"] = entity_in_metadata
            ranked.append(candidate)

        ranked.sort(
            key=lambda item: item["evidence_score"],
            reverse=True,
        )
        return ranked

    @classmethod
    def _drop_other_entity_documents(
        cls,
        question: str,
        ranked: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        When the question names an entity (e.g. CMP-021), remove chunks that
        are about other entities of the same kind (e.g. a CMP-007 postmortem)
        and never mention the requested one. Chunks with no entity IDs
        (general policies and strategy documents) are kept.
        """

        requested = cls._extract_entity_ids(question)
        if not requested:
            return ranked

        kept = []
        for item in ranked:
            if item.get("entity_match"):
                kept.append(item)
                continue

            title = str(item.get("title") or "")
            filename = str(item.get("filename") or "")
            content = str(item.get("content") or "")
            related = item.get("related_entity_ids") or []
            if not isinstance(related, str):
                related = " ".join(str(value) for value in related)

            mentioned = cls._extract_entity_ids(
                f"{title} {filename} {content} {related}"
            )
            if not mentioned:
                kept.append(item)

        return kept

    @staticmethod
    def _extract_entity_ids(text: str) -> list[str]:
        return list(dict.fromkeys(
            re.findall(r"\b[A-Z][A-Z0-9]*-\d+\b", text.upper())
        ))

    @staticmethod
    def _contains_entity(text: str, entity: str) -> bool:
        return bool(
            re.search(
                rf"(?<![A-Z0-9]){re.escape(entity)}(?![A-Z0-9])",
                text.upper(),
            )
        )
