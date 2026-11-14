
from typing import Any
import re


class DocumentChunker:
    """
    Splits cleaned document content into smaller chunks
    while preserving document and source metadata.

    Prefers sentence boundaries, then word boundaries, to avoid
    cutting words and sentences unnecessarily.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        document: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert a cleaned document into metadata-preserving chunks."""

        chunks: list[dict[str, Any]] = []

        for content_item in document.get("content", []):
            text = content_item.get("text", "").strip()

            if not text:
                continue

            text_chunks = self._split_text(text)

            for chunk_text in text_chunks:
                chunk = {
                    "chunk_id": (
                        f"{document['document_id']}-"
                        f"{len(chunks) + 1:03d}"
                    ),
                    "document_id": document["document_id"],
                    "filename": document["filename"],
                    "file_type": document["file_type"],
                    "title": document["title"],
                    "document_type": document["document_type"],
                    "department": document["department"],
                    "date": document["date"],
                    "version": document["version"],
                    "region": document["region"],
                    "related_entity_ids": document[
                        "related_entity_ids"
                    ],
                    "text": chunk_text,
                }

                if "page_number" in content_item:
                    chunk["page_number"] = content_item["page_number"]

                if "paragraph_number" in content_item:
                    chunk["paragraph_number"] = content_item[
                        "paragraph_number"
                    ]

                chunks.append(chunk)

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """
        Split text with configurable overlap.

        Prefer sentence boundaries near the target size, then whitespace.
        Use a hard boundary only when no suitable natural boundary exists.
        Always advance the next chunk's start to prevent infinite loops.
        """

        text = text.strip()

        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        text_length = len(text)
        start = 0

        while start < text_length:
            hard_end = min(start + self.chunk_size, text_length)

            if hard_end >= text_length:
                piece = text[start:text_length].strip()
                if piece:
                    chunks.append(piece)
                break

            # Search for a natural boundary near the end of this chunk.
            # Prefer sentence-ending punctuation followed by whitespace.
            minimum_end = start + max(1, self.chunk_size // 2)
            window = text[start:hard_end]

            sentence_matches = list(
                re.finditer(r'[.!?](?:["\')\]]*)\s+', window)
            )

            sentence_end = None

            for match in reversed(sentence_matches):
                candidate_end = start + match.end()
                if candidate_end >= minimum_end:
                    sentence_end = candidate_end
                    break

            if sentence_end is not None:
                end = sentence_end
            else:
                # If no suitable sentence boundary exists, prefer a
                # whitespace boundary near the target end.
                whitespace_end = text.rfind(
                    " ",
                    minimum_end,
                    hard_end,
                )

                if whitespace_end > start:
                    end = whitespace_end
                else:
                    # Long sentences or unbroken tokens may require a
                    # hard boundary to ensure forward progress.
                    end = hard_end

            piece = text[start:end].strip()

            if piece:
                chunks.append(piece)

            if end >= text_length:
                break

            # Preserve overlap but guarantee forward progress.
            next_start = max(start + 1, end - self.chunk_overlap)

            # Avoid starting the next chunk in the middle of a word
            # when a nearby whitespace boundary is available.
            if next_start > start:
                search_limit = min(
                    end,
                    next_start + self.chunk_overlap,
                )
                boundary = text.rfind(
                    " ",
                    next_start,
                    search_limit,
                )

                if boundary >= next_start:
                    next_start = boundary + 1

            # Defensive safeguard against an accidental non-advancing loop.
            if next_start <= start:
                next_start = end

            start = next_start

        return chunks
