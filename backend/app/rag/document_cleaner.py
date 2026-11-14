import re


class DocumentCleaner:
    """
    Cleans extracted document text before chunking and embedding.
    """

    SYNTHETIC_NOTICE = (
        "SYNTHETIC DOCUMENT — NOVAMART"
    )

    ACADEMIC_NOTICE = (
        "Academic dataset for AgentOps AI. This document is fictional and "
        "does not represent a real company's internal document."
    )

    def clean_text(self, text: str) -> str:
        """
        Clean a single extracted text block.
        """

        if not text:
            return ""

        # Remove synthetic dataset notice
        text = text.replace(self.SYNTHETIC_NOTICE, "")
        text = text.replace(self.ACADEMIC_NOTICE, "")

        # Normalize Windows/Mac line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove trailing spaces from each line
        lines = [line.strip() for line in text.split("\n")]

        # Remove empty lines
        lines = [line for line in lines if line]

        # Rebuild text
        text = "\n".join(lines)

        # Remove excessive spaces
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    def clean_document(self, document: dict) -> dict:
        """
        Clean all extracted content blocks while preserving
        their page/paragraph metadata.
        """

        cleaned_document = document.copy()
        cleaned_content = []

        for item in document.get("content", []):
            cleaned_item = item.copy()

            if "text" in cleaned_item:
                cleaned_text = self.clean_text(cleaned_item["text"])

                if cleaned_text:
                    cleaned_item["text"] = cleaned_text
                    cleaned_content.append(cleaned_item)

        cleaned_document["content"] = cleaned_content

        return cleaned_document