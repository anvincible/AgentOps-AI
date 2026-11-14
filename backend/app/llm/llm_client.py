import os

from dotenv import load_dotenv
from openai import OpenAI


class LLMClient:
    """
    Client for generating grounded answers using an OpenAI LLM.

    Phase 4.4:
    - Receives a user question
    - Receives retrieved RAG evidence
    - Sends only the provided evidence to the LLM
    - Generates a grounded natural-language answer

    The LLM does not perform document retrieval.
    Retrieval is handled separately by the RAG Agent.
    """

    def __init__(
        self,
        model: str = "gpt-5.6-luna",
    ):
        # Load variables from .env
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY was not found. "
                "Please add it to the .env file."
            )

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = model

    def generate_answer(
        self,
        question: str,
        evidence: list[dict],
    ) -> str:
        """
        Generate an answer using only the retrieved evidence.
        """

        if not question or not question.strip():
            raise ValueError(
                "Question cannot be empty."
            )

        if not evidence:
            return (
                "I could not find enough relevant "
                "information in the available documents "
                "to answer this question."
            )

        evidence_text = self._format_evidence(
            evidence
        )

        instructions = """
You are the answer-generation component of an
enterprise RAG system.

Answer the user's question using ONLY the evidence
provided below.

Rules:
1. Do not invent facts.
2. Do not use outside knowledge.
3. If the evidence does not contain enough information,
   clearly say that the available evidence is insufficient.
4. Keep the answer concise and factual.
5. Preserve important numbers exactly as provided.
6. When multiple pieces of evidence are relevant,
   combine them carefully.
7. Do not mention internal implementation details,
   embeddings, vector databases, or retrieval scores.
"""

        user_input = f"""
Question:
{question}

Retrieved Evidence:
{evidence_text}

Based only on the retrieved evidence, answer the question.
"""

        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=user_input,
        )

        return response.output_text.strip()

    @staticmethod
    def _format_evidence(
        evidence: list[dict],
    ) -> str:
        """
        Convert retrieved evidence into a structured
        text block for the LLM.
        """

        formatted_chunks = []

        for index, item in enumerate(
            evidence,
            start=1,
        ):
            chunk = f"""
Evidence {index}

Document ID:
{item.get("document_id")}

Filename:
{item.get("filename")}

Title:
{item.get("title")}

Document Type:
{item.get("document_type")}

Page:
{item.get("page_number")}

Paragraph:
{item.get("paragraph_number")}

Content:
{item.get("content")}
"""

            formatted_chunks.append(
                chunk.strip()
            )

        return "\n\n".join(
            formatted_chunks
        )