
import re
from typing import Any

from backend.app.sql.sql_agent import SQLAgent
from backend.app.rag.rag_agent import RAGAgent
from backend.app.orchestration.answer_composer import AnswerComposer
from backend.app.orchestration.verification_agent import VerificationAgent


class Orchestrator:
    """
    Coordinates the SQL and RAG agents.

    Routing strategy:
    - CHAT -> greetings and basic assistant introductions
    - SQL  -> supported structured database questions
    - RAG  -> document and policy questions
    - BOTH -> questions requiring structured and document evidence
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "novamart",
        user: str = "postgres",
        password: str = "",
    ):
        self.sql_agent = SQLAgent(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

        self.rag_agent = RAGAgent(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

        self.answer_composer = AnswerComposer()
        self.verification_agent = VerificationAgent()

    def answer(self, question: str) -> dict[str, Any]:
        """Automatically route a question, compose an answer, and verify it."""

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        route = self._route_question(question)

        # Handle greetings without querying SQL or retrieving documents.
        if route == "CHAT":
            chat_answer = (
                "Hello! I'm AgentOps AI, your NovaMart business assistant. "
                "I can answer supported business data questions and retrieve "
                "information from company documents "
                "and policies."
            )

            verification = self.verification_agent.verify(
                answer=chat_answer,
                route="CHAT",
            )

            return {
                "question": question,
                "route": "CHAT",
                "answer": chat_answer,
                "sources": [],
                "verification": verification,
            }

        response: dict[str, Any] = {
            "question": question,
            "route": route,
        }

        # Run the SQL agent when structured data is needed.
        sql_error: str | None = None

        if route in ("SQL", "BOTH"):
            try:
                response["sql"] = self.sql_agent.answer(question)
            except ValueError as error:
                sql_error = str(error)

        if route == "SQL" and sql_error:
            unsupported_answer = (
                f"I am unable to answer this question from structured data: "
                f"{sql_error}\n\n"
                "**Supported Structured Queries:**\n"
                "- **Marketing campaigns:** Campaign performance, spend, "
                "revenue, conversions, clicks, ROI, and comparisons "
                "(e.g. *'What was the performance of campaign CMP-021?'* "
                "or *'Summarise campaign spend and revenue'*).\n"
                "- **Customer returns:** Return counts, reasons, status, "
                "resolutions, trends, and return rate "
                "(e.g. *'What are the return reasons?'* "
                "or *'What is the return rate?'*).\n"
                "- **Customers and products:** Customer counts and top "
                "products by units sold or revenue; customer segments, "
                "locations, loyalty tiers, lifetime value, product "
                "categories, brands, and inventory.\n"
                "- **Orders, sellers, support, payments, shipments, and "
                "marketing:** Totals, grouped metrics, rankings, and "
                "supported date ranges."
            )

            verification = self.verification_agent.verify(
                answer=unsupported_answer,
                route="SQL",
                sql_result=None,
            )

            return {
                "question": question,
                "route": "SQL",
                "answer": unsupported_answer,
                "sources": [],
                "verification": verification,
            }

        # Run the RAG agent when document evidence is needed.
        if route in ("RAG", "BOTH"):
            try:
                response["rag"] = self.rag_agent.retrieve(question)
            except ValueError as error:
                response["rag_error"] = str(error)

        # Compose the final answer from the agent results.
        response["answer"] = self.answer_composer.compose(response)

        # Preserve the RAG answer if the SQL part of a BOTH request fails.
        if route == "BOTH" and sql_error:
            note = (
                f"\n\n*Note on database results:* {sql_error} "
                "(Structured data queries use a defined set of NovaMart "
                "analytics templates.)"
            )
            response["answer"] += note

        # Verify the answer and the evidence used.
        response["verification"] = self.verification_agent.verify(
            answer=response["answer"],
            route=route,
            sql_result=response.get("sql"),
            rag_result=response.get("rag"),
        )

        return response

    @staticmethod
    def _contains_term(question: str, terms: set[str]) -> bool:
        """Match complete phrases or words, not accidental substrings."""

        for term in terms:
            pattern = (
                r"(?<!\w)"
                + re.escape(term)
                + r"(?!\w)"
            )
            if re.search(pattern, question):
                return True

        return False

    @staticmethod
    def _route_question(question: str) -> str:
        """Deterministically select CHAT, SQL, RAG, or BOTH."""

        text = question.lower().strip()
        text = re.sub(r"\s+", " ", text)
        normalized = text.strip(" \t\n\r!?.,;:")

        # Only treat a message as CHAT when it is just a greeting,
        # thanks, or a basic assistant-introduction question.
        chat_phrases = {
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "who are you",
            "what can you do",
            "what can you help me with",
            "how can you help me",
        }

        if normalized in chat_phrases:
            return "CHAT"

        sql_terms = {
            "how many",
            "count",
            "total",
            "average",
            "avg",
            "sum",
            "revenue",
            "sales",
            "orders",
            "customers",
            "payments",
            "shipments",
            "returns",
            "return reasons",
            "return status",
            "return rate",
            "return trends",
            "return resolutions",
            "resolution",
            "resolutions",
            "total returns",
            "leads",
            "conversion",
            "conversions",
            "campaign",
            "campaign results",
            "campaign performance",
            "campaign conversions",
            "campaign revenue",
            "campaign spend",
            "clicks",
            "roi",
            "return on investment",
            "product",
            "products",
            "top-selling",
            "top selling",
            "best-selling",
            "best selling",
            "most sold",
            "seller",
            "sellers",
            "ticket",
            "tickets",
            "inventory",
            "stock",
            "category",
            "brand",
            "segment",
            "loyalty",
            "lifetime value",
            "order value",
            "month",
        }

        rag_terms = {
            "policy",
            "policies",
            "procedure",
            "procedures",
            "guideline",
            "guidelines",
            "document",
            "documents",
            "report",
            "reports",
            "postmortem",
            "strategy",
            "strategies",
            "terms",
            "refund policy",
            "return policy",
            "shipping policy",
            "marketing report",
            "recommended",
            "recommendation",
            "recommendations",
            "lessons learned",
            "why",
            "explain",
            "explanation",
            "reason",
            "reasons",
            "improve",
            "improvement",
            "improvements",
            "actions",
            "action plan",
        }

        has_sql_signal = Orchestrator._contains_term(
            text, sql_terms
        )

        has_rag_signal = Orchestrator._contains_term(
            text, rag_terms
        )

        # A measurable campaign question is SQL.
        # A campaign question asking for both metrics and explanations
        # requires BOTH agents.
        campaign_related = (
            "campaign" in text
            or bool(re.search(r"\bCMP-\d+\b", text, re.IGNORECASE))
        )

        explanation_signal = Orchestrator._contains_term(
            text,
            {
                "why",
                "explain",
                "explanation",
                "strategy",
                "recommended",
                "recommendation",
                "recommendations",
                "lessons learned",
                "improve",
                "improvement",
                "improvements",
                "actions",
                "action plan",
            },
        )

        metric_signal = Orchestrator._contains_term(
            text,
            {
                "revenue",
                "spend",
                "conversions",
                "conversion",
                "clicks",
                "click",
                "roi",
                "return on investment",
                "performance",
                "results",
                "compare",
                "comparison",
                "highest",
                "lowest",
                "average",
                "total",
                "count",
                "how many",
            },
        )

        if campaign_related and metric_signal and explanation_signal:
            return "BOTH"

        # Strategy and lessons-learned questions about campaigns are
        # document questions unless they also ask for measurable results.
        if campaign_related and explanation_signal and not metric_signal:
            return "RAG"

                # Policy and procedure questions must use document retrieval.
        policy_question = Orchestrator._contains_term(
            text,
            {
                "policy",
                "policies",
                "procedure",
                "procedures",
                "guideline",
                "guidelines",
                "terms",
            },
        )

        if policy_question:
            return "RAG"

        if Orchestrator._contains_term(
            text,
            {"seller", "sellers", "ticket", "tickets", "payment", "payments", "shipment", "shipments", "inventory", "stock"},
        ):
            return "SQL"

        # Return metrics, reasons, statuses, and resolutions
        # are structured database questions.
        return_database_question = (
            "return" in text or "returns" in text
        )

        if return_database_question:
            return "SQL"

        if has_sql_signal and has_rag_signal:
            return "BOTH"

        if has_sql_signal:
            return "SQL"

        if has_rag_signal:
            return "RAG"

        # Keep the existing RAG default for questions not recognized
        # as greetings or supported structured-data requests.
        return "RAG"
