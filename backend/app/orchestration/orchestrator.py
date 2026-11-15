
import re
import logging
from typing import Any

from backend.app.sql.sql_agent import SQLAgent
from backend.app.rag.rag_agent import RAGAgent
from backend.app.orchestration.answer_composer import AnswerComposer
from backend.app.orchestration.verification_agent import VerificationAgent
from backend.app.orchestration.analysis_agent import AnalysisAgent

logger = logging.getLogger(__name__)


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
        self.analysis_agent = AnalysisAgent()

    def answer(
        self,
        question: str,
        clarification_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Automatically route a question, compose an answer, and verify it."""

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        resolved_question = self._resolve_clarification(question, clarification_context)
        if resolved_question:
            question = resolved_question

        clarification = self._clarification_needed(question)
        if clarification:
            answer = clarification
            verification = self.verification_agent.verify(
                answer=answer,
                route="CLARIFY",
                question=question,
            )
            return {
                "question": question,
                "route": "CLARIFY",
                "answer": answer,
                "sources": [],
                "verification": verification,
                "clarification": self._clarification_metadata(question, clarification),
            }

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
                question=question,
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
        business_summary = self._is_business_summary_question(question)

        if route in ("SQL", "BOTH"):
            if business_summary:
                summary_queries = (
                    ("Sales", "What is total sales revenue and average order value?"),
                    ("Customers", "How many customers are there?"),
                    ("Returns", "What is the return rate?"),
                    ("Campaigns", "Show campaign performance."),
                )
                validated_results: list[dict[str, Any]] = []
                unavailable_areas: list[str] = []
                component_queries: list[dict[str, Any]] = []
                for area, summary_query in summary_queries:
                    try:
                        result = self.sql_agent.answer(summary_query)
                    except Exception as error:
                        logger.warning("Business summary query failed for %s (%s)", area, type(error).__name__)
                        unavailable_areas.append(area)
                        component_queries.append({
                            "area": area,
                            "query_intent": None,
                            "status": "query_failed",
                            "sql_validated": False,
                            "result_nonempty": False,
                        })
                        continue
                    validation = result.get("validation") if isinstance(result, dict) else None
                    sql_data = result.get("result") if isinstance(result, dict) else None
                    sql_validated = isinstance(validation, dict) and validation.get("valid") is True
                    result_nonempty = (
                        isinstance(sql_data, dict)
                        and bool(sql_data.get("columns"))
                        and bool(sql_data.get("rows"))
                    )
                    component_status = (
                        "validated" if sql_validated and result_nonempty
                        else "validation_failed" if not sql_validated
                        else "empty_result"
                    )
                    component_queries.append({
                        "area": area,
                        "query_intent": (result.get("query_plan") or {}).get("intent")
                        if isinstance(result, dict) else None,
                        "status": component_status,
                        "sql_validated": sql_validated,
                        "result_nonempty": result_nonempty,
                    })
                    if sql_validated and result_nonempty:
                        validated_results.append(result)
                        response.setdefault("sql", result)
                    else:
                        unavailable_areas.append(area)
                response["analysis"] = self.analysis_agent.analyze_business_summary(
                    validated_results, unavailable_areas
                )
                response["analysis"]["evidence"]["components"] = component_queries
                if not validated_results:
                    sql_error = "No business-summary query returned validated structured results."
            else:
                try:
                    response["sql"] = self.sql_agent.answer(question)
                except Exception as error:
                    if isinstance(error, ValueError):
                        logger.warning("SQL agent rejected a query: %s", error)
                        sql_error = "The requested structured-data query is not supported."
                    else:
                        logger.exception("SQL agent failed while processing a question")
                        sql_error = "The database query could not be completed."

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
                question=question,
            )
            if business_summary:
                self._attach_business_summary_verification(response, verification)

            return {
                "question": question,
                "route": "SQL",
                "answer": unsupported_answer,
                "sources": [],
                "verification": verification,
                "analysis": response.get("analysis"),
            }

        # Run the RAG agent when document evidence is needed.
        if route in ("RAG", "BOTH"):
            try:
                response["rag"] = self.rag_agent.retrieve(question)
            except Exception as error:
                if isinstance(error, ValueError):
                    logger.warning("RAG agent could not retrieve evidence: %s", error)
                    response["rag_error"] = "The requested document evidence is unavailable."
                else:
                    logger.exception("RAG agent failed while processing a question")
                    response["rag_error"] = "Document retrieval could not be completed."

        # Analysis consumes existing validated SQL rows; it never issues queries.
        if route in ("SQL", "BOTH") and not business_summary:
            response["analysis"] = self.analysis_agent.analyze(
                response.get("sql"), question, response.get("rag")
            )

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

        if route == "BOTH" and response.get("rag_error"):
            response["answer"] += (
                "\n\n*Note on document evidence:* "
                "Document retrieval could not be completed."
            )

        # Verify the answer and the evidence used.
        response["verification"] = self.verification_agent.verify(
            answer=response["answer"],
            route=route,
            sql_result=response.get("sql"),
            rag_result=response.get("rag"),
            question=question,
        )
        if business_summary:
            self._attach_business_summary_verification(response, response["verification"])

        return response

    def _attach_business_summary_verification(
        self,
        response: dict[str, Any],
        verification: dict[str, Any],
    ) -> None:
        analysis_verification = self.verification_agent.verify_business_summary(
            response.get("analysis") or {}
        )
        response["analysis"]["verification"] = analysis_verification
        verification["business_summary"] = analysis_verification
        verification["verified"] = bool(verification.get("verified")) and analysis_verification["verified"]
        if not analysis_verification["verified"]:
            verification.setdefault("issues", []).extend(analysis_verification["issues"])
        verification.setdefault("checks", []).append(
            "Business-summary component validation, KPI coverage, and consistency scope were checked."
        )

    @staticmethod
    def _clarification_metadata(question: str, prompt: str) -> dict[str, Any]:
        text = question.lower()
        if (
            Orchestrator._is_business_summary_question(question)
            and Orchestrator._has_business_summary_period(text)
        ):
            return {
                "original_question": question,
                "kind": "business_summary_period",
                "options": ["all-time summary"],
                "prompt": prompt,
            }
        if "campaign" in text and re.search(r"\b(compare|comparison|difference|differences|contrast)\b", text):
            return {
                "original_question": question,
                "kind": "campaign_comparison_targets",
                "options": [],
                "prompt": prompt,
            }
        if "product" in text and re.search(r"\b(best|top|highest|rank|ranking)\b", text):
            return {
                "original_question": question,
                "kind": "product_ranking_metric",
                "options": ["revenue", "quantity"],
                "prompt": prompt,
            }
        if "customer" in text and re.search(r"\b(distribution|breakdown)\b", text):
            return {
                "original_question": question,
                "kind": "customer_distribution_dimension",
                "options": ["segment", "location", "city", "state", "country", "loyalty tier", "acquisition channel"],
                "prompt": prompt,
            }
        if re.search(r"\b(last|previous) year\b", text):
            return {
                "original_question": question,
                "kind": "date_range",
                "options": ["previous calendar year", "rolling 12 months"],
                "prompt": prompt,
            }
        return {"original_question": question, "kind": "other", "options": [], "prompt": prompt}

    @staticmethod
    def _resolve_clarification(
        reply: str, context: dict[str, Any] | None
    ) -> str | None:
        if not isinstance(context, dict):
            return None
        original = context.get("original_question")
        kind = context.get("kind")
        options = context.get("options")
        if not isinstance(original, str) or not original.strip() or not isinstance(options, list):
            return None
        if kind == "campaign_comparison_targets":
            match = re.fullmatch(
                r"\s*(?:compare\s+)?(?:campaign\s+)?(CMP-\d+)\s*(?:,|and|&)\s*"
                r"(?:campaign\s+)?(CMP-\d+)\s*[.!]?\s*",
                reply,
                re.IGNORECASE,
            )
            if not match or match.group(1).upper() == match.group(2).upper():
                return None
            return f"Compare campaigns {match.group(1).upper()} and {match.group(2).upper()}."
        normalized = re.sub(r"[^a-z0-9 ]", " ", reply.lower()).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if len(normalized.split()) > 6:
            return None

        if kind == "business_summary_period":
            context_options = {
                re.sub(r"[^a-z0-9 ]", " ", option.lower()).strip()
                for option in options
                if isinstance(option, str)
            }
            valid_context = (
                Orchestrator._is_business_summary_question(original)
                and Orchestrator._has_business_summary_period(original)
                and "all time summary" in context_options
            )
            scope_is_all_time = bool(re.search(r"\b(all time|unfiltered)\b", normalized))
            affirmative = bool(re.search(
                r"\b(yes|yeah|sure|fine|acceptable|okay|ok|use|accept|works|good)\b",
                normalized,
            ))
            negative = bool(re.search(r"\b(no|not|never|dont|don t|without)\b", normalized))
            is_offered_option = normalized in context_options
            if valid_context and scope_is_all_time and (is_offered_option or (affirmative and not negative)):
                return "Summarize NovaMart's business performance."
            return None

        aliases = {
            "product_ranking_metric": {
                "revenue": ("revenue", "sales"),
                "quantity": ("quantity", "units", "quantity sold", "units sold"),
            },
            "customer_distribution_dimension": {
                "segment": ("segment", "customer segment"),
                "location": ("location", "locations"),
                "city": ("city",), "state": ("state",), "country": ("country",),
                "loyalty tier": ("loyalty", "loyalty tier"),
                "acquisition channel": ("acquisition channel", "channel"),
            },
            "date_range": {
                "previous calendar year": ("calendar year", "previous calendar year", "last calendar year"),
                "rolling 12 months": ("rolling 12 months", "rolling year", "12 months"),
            },
        }
        allowed = aliases.get(kind, {})
        selected = next((option for option, phrases in allowed.items()
                         if option in options and any(phrase in normalized for phrase in phrases)), None)
        if not selected:
            return None
        if kind == "date_range":
            question = re.sub(
                r"\b(?:last|previous) year\b", selected, original,
                count=1, flags=re.IGNORECASE,
            )
            return question if question != original else f"{original.strip()} {selected}"
        return f"{original.strip()} by {selected}"

    def _clarification_needed(self, question: str) -> str | None:
        text = re.sub(r"\s+", " ", question.lower()).strip()
        if (
            Orchestrator._is_business_summary_question(question)
            and Orchestrator._has_business_summary_period(text)
        ):
            return (
                "I can’t apply that time period consistently across sales, customer, returns, and campaign KPIs "
                "with the current query templates. Would you like the all-time business summary instead?"
            )
        if "campaign" in text and re.search(
            r"\b(compare|comparison|difference|differences|contrast)\b", text
        ):
            campaign_ids = {
                campaign_id.upper()
                for campaign_id in re.findall(r"\bCMP-\d+\b", question, re.IGNORECASE)
            }
            if len(campaign_ids) != 2:
                return "Which two campaigns should I compare? Please provide two campaign IDs, such as CMP-021 and CMP-022."
        if re.search(r"\b(age|gender|income)\b", text):
            requested = re.search(r"\b(age|gender|income)\b", text).group(1)
            customer_columns = {
                column.get("column_name")
                for column in self.sql_agent.schema.get("tables", {})
                .get("customers", {})
                .get("columns", [])
            }
            supported_customer_groupings = {
                "customer_segment", "city", "state", "country",
                "loyalty_tier", "acquisition_channel", "status",
            }
            if requested not in customer_columns or requested not in supported_customer_groupings:
                reason = (
                    "is present in the database, but isn't supported by the "
                    "current analytics templates"
                    if requested in customer_columns
                    else "is not present in the live customers table"
                )
                return (
                    f"The {requested} field {reason}. "
                    "Would you like a supported grouping such as "
                    "segment, city, state, country, or loyalty tier?"
                )
        if re.search(r"\b(last|previous) year\b", text):
            return (
                "Do you mean the previous calendar year or the rolling "
                "12 months?"
            )
        if (
            re.search(r"\b(customer|customers)\b.*\b(location|locations)\b", text)
            and not re.search(r"\b(city|state|country)\b", text)
        ):
            return "Which location grouping should I use: city, state, or country?"
        if (
            re.search(r"\b(inventory|stock)\b", text)
            and re.search(r"\bby\s+(category|brand)\b", text)
        ):
            return (
                "Do you want product-level inventory listed under each "
                "category/brand, or total stock grouped by that dimension?"
            )
        if (
            re.search(r"\bproducts?\b", text)
            and re.search(r"\b(top|best|highest|rank|ranking|popular|performed best)\b", text)
            and not re.search(
                r"\b(revenue|sales|quantity|units|sold|price)\b", text
            )
        ):
            return "Should I rank products by quantity sold or by revenue?"
        if (
            re.search(r"\bcustomer\b", text)
            and re.search(r"\b(distribution|breakdown)\b", text)
            and not re.search(r"\b(segment|city|state|country|loyalty|channel)\b", text)
        ):
            return "Which supported dimension should I use: segment, location, loyalty tier, or acquisition channel?"
        if (
            re.search(r"\b(top|best|highest|rank|ranking)\b.*\bcampaigns?\b", text)
            and not re.search(r"\b(roi|revenue|spend|conversions?|clicks?)\b", text)
        ):
            return "Should I rank campaigns by ROI, revenue, spend, or conversions?"
        if (
            re.search(r"\b(top|best|highest|rank|ranking)\b.*\bsellers?\b", text)
            and not re.search(r"\b(revenue|sales|orders|quantity|units)\b", text)
        ):
            return "Should I rank sellers by revenue, order count, or units sold?"
        unsupported_filter = (
            re.search(r"\b(where|whose|only)\b", text)
            or re.search(r"\b(above|below|greater than|less than|over|under)\b", text)
        )
        supported_filter = (
            "low stock" in text
            or "out of stock" in text
            or re.search(r"\b(last|past)\s+\d+\s+days?\b", text)
            or re.search(r"\b20\d{2}\b", text)
            or bool(self.rag_agent._explicit_document_type_filter(question))
        )
        if unsupported_filter and not supported_filter:
            return (
                "That specific filter is not supported by the current SQL "
                "templates. Would you like an unfiltered summary instead?"
            )
        return None

    @staticmethod
    def _is_business_summary_question(question: str) -> bool:
        text = re.sub(r"\s+", " ", question.casefold()).strip()
        summary_requested = bool(re.search(
            r"\b(summarize|summarise|summary|overview|snapshot)\b", text
        )) or "business performance" in text
        business_scope = bool(re.search(r"\b(novamart|business|overall)\b", text))
        specific_entity = bool(re.search(
            r"\b(campaign|product|customer|return|seller|shipment|payment|ticket)\b", text
        ))
        return summary_requested and business_scope and not specific_entity

    @staticmethod
    def _has_business_summary_period(question: str) -> bool:
        text = question.casefold()
        if re.search(r"\b20\d{2}\b", text):
            return True
        if re.search(
            r"\b(?:last|past|previous|rolling)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+"
            r"(?:days?|weeks?|months?|quarters?|years?)\b",
            text,
        ):
            return True
        if re.search(r"\b(?:last|previous)\s+year\b", text):
            return True
        if re.search(
            r"\b(?:monthly|weekly|quarterly|yearly|annually|by month|by quarter|over time)\b",
            text,
        ):
            return True
        return bool(re.search(r"\b(?:between|from)\s+\w+\s+(?:and|to|through)\s+\w+\b", text))

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

        if Orchestrator._is_business_summary_question(question):
            return "SQL"

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
        campaign_comparison = (
            campaign_related
            and bool(re.search(r"\b(compare|comparison|difference|differences|contrast)\b", text))
        )
        comparison_ids = {
            campaign_id.upper()
            for campaign_id in re.findall(r"\bCMP-\d+\b", text, re.IGNORECASE)
        }
        if campaign_comparison and len(comparison_ids) >= 2:
            return "SQL"

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
                "metrics",
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

        return_policy_hybrid = (
            policy_question
            and has_sql_signal
            and bool(re.search(r"\b(return|returns|refund|refunds)\b", text))
            and metric_signal
        )
        if return_policy_hybrid:
            return "BOTH"

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

        return_policy_detail = bool(re.search(
            r"\b(return|refund)\s+(window|timeline|timeframe|eligibility|eligible)\b",
            text,
        ))

        if return_policy_detail and not Orchestrator._contains_term(
            text, {"count", "rate", "reasons", "status", "resolution", "trends"}
        ):
            return "RAG"

        return_eligibility_question = bool(re.search(
            r"\b(can|may|eligible|allowed)\b.{0,80}\b(return|returns|refund|refunds)\b",
            text,
        ))
        if return_eligibility_question and not metric_signal:
            return "RAG"

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
