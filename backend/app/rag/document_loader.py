from pathlib import Path
from typing import Any
import csv
import json

import pymupdf
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class DocumentLoader:
    """
    Loads NovaMart PDF and DOCX files and converts them
    into a common document representation.
    """

    def __init__(
        self,
        metadata_path: str = "data/novamart/metadata/document_metadata.csv",
        entity_links_path: str = "data/novamart/metadata/document_entity_links.csv",
    ):
        self.metadata_path = Path(metadata_path)
        self.entity_links_path = Path(entity_links_path)

        self.metadata = self._load_metadata()
        self.entity_links = self._load_entity_links()

    # ---------------------------------------------------------
    # Public method
    # ---------------------------------------------------------

    def load(self, file_path: str | Path) -> dict[str, Any]:
        """
        Load a PDF or DOCX and return a standardized document object.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported types: {SUPPORTED_EXTENSIONS}"
            )

        if path.suffix.lower() == ".pdf":
            content = self._load_pdf(path)
        else:
            content = self._load_docx(path)

        metadata = self._get_metadata(path)

        document_id = metadata.get("document_id")

        related_entity_ids = self._get_related_entities(
            document_id=document_id,
            metadata=metadata,
        )

        return {
            "document_id": document_id,
            "source": str(path).replace("\\", "/"),
            "filename": path.name,
            "file_type": path.suffix.lower().replace(".", ""),
            "title": metadata.get("title", path.stem),
            "document_type": metadata.get("document_type"),
            "department": metadata.get("department"),
            "date": metadata.get("date"),
            "version": metadata.get("version"),
            "region": metadata.get("region"),
            "related_entity_ids": related_entity_ids,
            "content": content,
        }

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    def _load_pdf(self, path: Path) -> list[dict[str, Any]]:
        """
        Extract text page-by-page from a PDF.
        """

        document = pymupdf.open(path)

        pages = []

        try:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()

                if text:
                    pages.append(
                        {
                            "page_number": page_number,
                            "text": text,
                        }
                    )
        finally:
            document.close()

        return pages

    # ---------------------------------------------------------
    # DOCX
    # ---------------------------------------------------------

    def _load_docx(self, path: Path) -> list[dict[str, Any]]:
        """
        Extract non-empty paragraphs from a DOCX.
        """

        document = Document(path)

        paragraphs = []

        for paragraph_number, paragraph in enumerate(
            document.paragraphs,
            start=1,
        ):
            text = paragraph.text.strip()

            if text:
                paragraphs.append(
                    {
                        "paragraph_number": paragraph_number,
                        "text": text,
                    }
                )

        return paragraphs

    # ---------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------

    def _load_metadata(self) -> dict[str, dict[str, Any]]:
        """
        Load document_metadata.csv and index it by filename.
        """

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {self.metadata_path}"
            )

        metadata = {}

        with self.metadata_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                filename = row.get("source_filename") or row.get("filename")

                if filename:
                    metadata[Path(filename).name] = row

        return metadata

    # ---------------------------------------------------------
    # Entity Links
    # ---------------------------------------------------------

    def _load_entity_links(self) -> dict[str, list[str]]:
        """
        Load document_entity_links.csv and create:

        document_id -> [entity_id, entity_id, ...]
        """

        if not self.entity_links_path.exists():
            raise FileNotFoundError(
                f"Entity links file not found: {self.entity_links_path}"
            )

        entity_links: dict[str, list[str]] = {}

        with self.entity_links_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                document_id = row.get("document_id")
                entity_id = row.get("entity_id")

                if not document_id or not entity_id:
                    continue

                entity_links.setdefault(document_id, [])

                if entity_id not in entity_links[document_id]:
                    entity_links[document_id].append(entity_id)

        return entity_links

    # ---------------------------------------------------------
    # Metadata lookup
    # ---------------------------------------------------------

    def _get_metadata(self, path: Path) -> dict[str, Any]:
        """
        Find metadata for a document using its filename.
        """

        metadata = self.metadata.get(path.name)

        if metadata is None:
            raise ValueError(
                f"No metadata found for document: {path.name}"
            )

        return metadata

    # ---------------------------------------------------------
    # Entity lookup
    # ---------------------------------------------------------

    def _get_related_entities(
        self,
        document_id: str | None,
        metadata: dict[str, Any],
    ) -> list[str]:

        entities = []

        if document_id:
            entities.extend(
                self.entity_links.get(document_id, [])
            )

        # Also support a populated related_entity_ids field
        # directly inside document_metadata.csv.
        metadata_entities = metadata.get("related_entity_ids", "")

        if metadata_entities:
            try:
                parsed = json.loads(metadata_entities)

                if isinstance(parsed, list):
                    entities.extend(str(item) for item in parsed)

            except (json.JSONDecodeError, TypeError):
                # Handle simple comma-separated values.
                for item in metadata_entities.split(","):
                    item = item.strip()

                    if item:
                        entities.append(item)

        # Remove duplicates while preserving order.
        return list(dict.fromkeys(entities))