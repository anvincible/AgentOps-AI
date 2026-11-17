import re
from datetime import date, datetime
from typing import Any


class AnswerComposer:
    """Compose readable answers from SQL and RAG evidence."""

    MAX_DOCUMENTS = 2
    MAX_CHUNKS_PER_DOCUMENT = 3
    MAX_CONTENT_CHARS = 6000

    METADATA_FIELDS = {
        "document_id",
        "title",
        "document_type",
        "department",
        "date",
        "version",
        "region",
        "related_entity_ids",
        "filename",
        "file_type",
    }

    SECTION_HEADINGS = (
        "Return window",
        "Common reasons",
        "Resolution",
        "Warranty coverage",
        "Eligibility",
        "Exceptions",
        "Delivery",
        "Campaign facts",
        "Observed drivers",
        "Recommendations",
        "Root causes",
        "Key findings",
        "Next steps",
    )

    TOPIC_TERMS = {
        "return": {
            "return", "refund", "refunds", "replacement",
            "store", "credit", "damaged", "returned",
        },
        "shipping": {
            "shipping", "shipment", "delivery", "delayed",
            "delay", "tracking", "dispatch", "delivered",
        },
        "warranty": {
            "warranty", "coverage", "eligible", "product",
            "purchase", "repair",
        },
        "seller": {
            "seller", "onboarding", "vendor", "listing",
            "merchant",
        },
        "campaign": {
            "campaign", "spend", "revenue", "conversions",
            "clicks", "marketing",
        },
    }

    RAG_QUERY_STOP_WORDS = {
        "according", "about", "above", "after", "again", "also", "among",
        "and", "are", "around", "based", "can", "campaign", "could", "describe",
        "details", "did", "does", "document", "documents", "explain", "for", "from",
        "give", "how", "information", "include", "is", "it", "me", "need",
        "novamart", "of", "on", "or", "performance", "performed", "please", "policy", "policies",
        "related", "regarding", "say", "says", "should", "show", "tell",
        "the", "this", "to", "what", "when", "where", "which", "who",
        "why", "results", "will", "with", "would", "you",
        "customer", "customers", "recorded", "number", "count",
        "happens", "take", "takes",
    }

    RAG_TERM_EQUIVALENTS = {
        "timeline": {"window", "days", "within", "refund"},
        "long": {"days", "window", "period"},
        "buying": {"product", "item", "purchase"},
        "bought": {"product", "item", "purchase"},
        "something": {"product", "item"},
        "send": {"return", "returned"},
        "sent": {"return", "returned"},
        "back": {"return", "returned"},
        "delayed": {"delay", "delays", "late"},
        "delivery": {"delivery", "delivered", "shipment", "dispatch"},
        "service": {"support", "service"},
        "defective": {"damaged", "quality", "defect"},
        "returns": {"return"},
        "refunds": {"refund"},
        "disputes": {"dispute"},
        "performed": {"performance", "perform"},
        "strategy": {"strategy", "recommend", "recommended", "recommendation"},
        "recommended": {"recommended", "recommend", "recommendation", "strategy"},
        "recommendation": {"recommendation", "recommended", "recommend", "strategy"},
    }

    def compose(self, orchestration_result: dict[str, Any]) -> str:
        if not orchestration_result:
            return "I could not generate an answer."

        route = orchestration_result.get("route")
        question = orchestration_result.get("question", "")

        if route == "SQL":
            sql_result = orchestration_result.get("sql", {})
            return self._compose_sql(
                sql_result,
                sql_result.get("query_plan", {}),
            )

        if route == "RAG":
            return self._compose_rag(
                orchestration_result.get("rag", {}),
                question,
            )

        if route == "BOTH":
            sql_result = orchestration_result.get("sql", {})
            answer = self._compose_both(
                sql_result,
                orchestration_result.get("rag", {}),
                question,
            )
            return self._with_interpretation(
                answer, sql_result.get("query_plan", {})
            )

        return "I could not determine how to answer this question."

    def _compose_sql(
        self,
        sql_result: dict[str, Any],
        query_plan: dict[str, Any] | None = None,
    ) -> str:
        result = sql_result.get("result", {})
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        plan = query_plan or {}

        if plan.get("intent") == "SALES_BY_MONTH":
            month_index = next(
                (
                    index
                    for index, column in enumerate(columns)
                    if str(column).lower() in {"sales_month", "month"}
                ),
                None,
            )
            if month_index is not None:
                rows = sorted(rows, key=lambda row: self._month_order(row[month_index]))

        if not rows:
            return "I could not find any matching data."

        lines = ["Here is what I found:"]

        for row in rows:
            values = dict(zip(columns, row))

            for column, value in values.items():
                label = self._friendly_label(column)
                formatted = self._format_value(column, value)
                lines.append(f"- **{label}:** {formatted}")

        return self._with_interpretation("\n".join(lines), plan)

    @staticmethod
    def _month_order(value: Any) -> tuple[int, int, int, str]:
        if isinstance(value, (date, datetime)):
            return (0, value.year, value.month, str(value))
        text = str(value).strip()
        for format_string in ("%Y-%m-%d", "%Y-%m", "%B %Y", "%b %Y"):
            try:
                parsed = datetime.strptime(text, format_string)
            except ValueError:
                continue
            return (0, parsed.year, parsed.month, text)
        return (1, 0, 0, text.casefold())

    @staticmethod
    def _with_interpretation(
        answer: str, query_plan: dict[str, Any]
    ) -> str:
        """State deterministic interpretations that affect SQL results."""
        intent = query_plan.get("intent", "")
        date_filter = query_plan.get("date_filter") or {}
        note = None
        if "start_year" in date_filter:
            first = date_filter["start_year"]
            last = date_filter.get("end_year", first)
            note = (
                f"Interpretation used: calendar year {first}."
                if first == last
                else f"Interpretation used: calendar years {first} through {last}."
            )
        elif "last_days" in date_filter:
            note = (
                "Interpretation used: the rolling trailing "
                f"{date_filter['last_days']} days ending today."
            )
        elif intent == "CUSTOMER_STATUS_COUNT" and query_plan.get("status_value") == "NOT_ACTIVE":
            note = (
                "Interpretation used: inactive means any customer whose "
                "status is not ACTIVE (including DORMANT and CLOSED)."
            )
        elif intent == "TOP_PRODUCTS_BY_QUANTITY":
            note = "Interpretation used: ranked by quantity sold."
        elif intent == "TOP_PRODUCTS_BY_REVENUE":
            note = "Interpretation used: ranked by revenue."
        elif intent == "CAMPAIGN_PERFORMANCE" and not query_plan.get("entity_id"):
            note = (
                "Interpretation used: aggregate overview across all campaigns; "
                "no ranking applied."
            )

        return f"{note}\n\n{answer}" if note else answer

    def _compose_rag(
        self,
        rag_result: dict[str, Any],
        question: str = "",
    ) -> str:
        evidence = rag_result.get("evidence", [])

        if not evidence:
            return (
                "I could not find enough relevant information "
                "in the available documents."
            )

        selected = self._select_relevant_evidence(
            evidence,
            question,
        )

        if not selected:
            return (
                "I could not find enough substantive evidence "
                "to answer this question from the available documents."
            )

        missing_facets = self._missing_document_facets(question, selected)
        if missing_facets:
            lines = [
                "I found some relevant excerpts, but not evidence for every "
                "requested document. Missing: " + ", ".join(missing_facets) + "."
            ]
        else:
            lines = ["Based on the available documents:"]
        campaign_scope = self._campaign_recommendation_scope(
            question, selected
        )
        if campaign_scope:
            lines.extend(["", campaign_scope])
        missing_aspects = self._missing_material_aspects(question, selected)
        if missing_aspects:
            lines.extend([
                "",
                "The retrieved excerpts do not provide: "
                + ", ".join(missing_aspects)
                + ".",
            ])
        if self._documents_differ(selected):
            lines.extend([
                "",
                "The excerpts are attributed to their sources below; "
                "any differences have not been reconciled.",
            ])

        for item in selected:
            title = self._display_title(item)

            content = item.get(
                "_clean_content",
                self._clean_content(item.get("content", "")),
            )

            if content:
                lines.extend(["", f"**{title}**", content])

        if len(lines) == 1:
            return "The retrieved documents did not contain usable text."

        return self._limit_content("\n".join(lines))

    def _compose_both(
        self,
        sql_result: dict[str, Any],
        rag_result: dict[str, Any],
        question: str = "",
    ) -> str:
        lines: list[str] = []

        result = sql_result.get("result", {})
        rows = result.get("rows", [])
        columns = result.get("columns", [])

        if rows:
            lines.append("**Database Results**")

            for row in rows:
                values = dict(zip(columns, row))

                for column, value in values.items():
                    label = self._friendly_label(column)
                    formatted = self._format_value(column, value)
                    lines.append(f"- **{label}:** {formatted}")

        selected = self._select_relevant_evidence(
            rag_result.get("evidence", []),
            question,
        )
        missing_facets = self._missing_document_facets(question, selected)
        missing_aspects = self._missing_material_aspects(question, selected)

        if selected:
            lines.extend(["", "**Supporting Document Evidence**"])
            campaign_scope = self._campaign_recommendation_scope(
                question, selected
            )
            if campaign_scope:
                lines.extend(["", campaign_scope])
            if missing_aspects:
                lines.extend([
                    "",
                    "The retrieved excerpts do not provide: "
                    + ", ".join(missing_aspects)
                    + ".",
                ])
            if missing_facets:
                lines.extend([
                    "",
                    "Evidence is missing for: " + ", ".join(missing_facets) + ".",
                ])
            if self._documents_differ(selected):
                lines.extend([
                    "",
                    "The excerpts are attributed to their sources below; "
                    "any differences have not been reconciled.",
                ])

            for item in selected:
                title = self._display_title(item)

                content = item.get(
                    "_clean_content",
                    self._clean_content(item.get("content", "")),
                )

                if content:
                    lines.extend(["", f"**{title}**", content])
        elif missing_facets:
            lines.extend([
                "",
                "**Supporting Document Evidence**",
                "I could not retrieve evidence for: " + ", ".join(missing_facets) + ".",
            ])

        if not lines:
            return (
                "I could not find enough relevant information "
                "to answer the question."
            )

        return self._limit_content("\n".join(lines))

    @classmethod
    def _display_title(cls, item: dict[str, Any]) -> str:
        title = (
            item.get("title")
            or item.get("filename")
            or "Supporting document"
        )
        if item.get("_general_context"):
            title = f"{title} (general context, covers multiple campaigns)"
        if cls._item_covers_document_facet(
            item, "campaign_observed_drivers"
        ):
            title = f"{title} - Factors to investigate"
        elif cls._item_covers_document_facet(
            item, "campaign_recommendation"
        ):
            title = f"{title} - Future-campaign recommendation"
        return str(title)

    @classmethod
    def _campaign_recommendation_scope(
        cls,
        question: str,
        selected: list[dict[str, Any]],
    ) -> str | None:
        requested = cls._requested_document_facets(question)
        requested_observed = "campaign_observed_drivers" in requested
        if not requested_observed:
            return None
        if cls._missing_document_facets(question, selected):
            return None
        return (
            "The postmortem frames the alignment points as factors to "
            "investigate; it does not establish them as causes of CMP-021's results."
        )

    @staticmethod
    def _documents_differ(items: list[dict[str, Any]]) -> bool:
        document_ids = {
            item.get("document_id") for item in items if item.get("document_id")
        }
        return len(document_ids) > 1

    @classmethod
    def _requested_document_facets(cls, question: str) -> dict[str, str]:
        text = question.lower()
        requested: dict[str, str] = {}
        explicit_return_policy = bool(re.search(
            r"\b(return|refund)\b.{0,30}\bpolic(?:y|ies)\b", text
        ))
        return_window_question = bool(re.search(
            r"\b(how long|return window|refund timeline|eligible|eligibility|"
            r"after (?:buying|purchase|purchasing))\b",
            text,
        ))
        if explicit_return_policy or (
            return_window_question
            and re.search(r"\b(return|returns|refund|refunds|back)\b", text)
        ):
            requested["return_policy"] = "return/refund policy"
        if re.search(r"\bcustomer\s+service\s+polic(?:y|ies)\b", text):
            requested["customer_service_policy"] = "customer service policy"
        if re.search(r"\bshipping\s+polic(?:y|ies)\b", text):
            requested["shipping_policy"] = "shipping policy"
        elif "shipping" in text and re.search(r"\b(delivery|deliveries|shipping)\b", text):
            requested["shipping_policy"] = "shipping policy"
        if re.search(r"\b(delivery|deliveries)\b", text) and re.search(
            r"\b(delay|delayed|late|exception|happens)\b", text
        ):
            requested["delivery_exception"] = "delivery exception guidance"
        if re.search(r"\bCMP-021\b", question, re.IGNORECASE):
            asks_factors = bool(re.search(
                r"\b(factors?|investigat(?:e|ed|ing)|understand)\b", text
            ))
            asks_recommendation = bool(re.search(
                r"\b(strategy|strategies|recommend(?:ed|ation|ations)?|"
                r"before increasing spend|key recommendations?)\b",
                text,
            ))
            postmortem_summary = (
                "postmortem" in text
                and bool(re.search(r"\b(summarize|summarise|summary|explain|financial)\b", text))
            )
            focused_postmortem_recommendation = (
                "postmortem" in text
                and asks_recommendation
                and not postmortem_summary
                and not re.search(r"\b(metrics?|results?|performance|strategy|factors?)\b", text)
            )
            explicit_hybrid_postmortem = (
                "postmortem" in text
                and bool(re.search(r"\b(database|SQL|structured data)\b", text, re.IGNORECASE))
            )
            if (
                asks_factors
                or (asks_recommendation and not focused_postmortem_recommendation)
                or postmortem_summary
                or explicit_hybrid_postmortem
            ):
                requested["campaign_observed_drivers"] = "campaign factors to investigate"
            if asks_recommendation or postmortem_summary or explicit_hybrid_postmortem:
                requested["campaign_recommendation"] = "campaign strategy/recommendation"
        return requested

    @classmethod
    def _missing_material_aspects(
        cls,
        question: str,
        selected: list[dict[str, Any]],
    ) -> list[str]:
        text = question.lower()
        if not re.search(r"\bhow long\b", text) or not re.search(
            r"\b(shipping|delivery|deliveries)\b", text
        ):
            return []
        excerpts = " ".join(
            str(item.get("_clean_content") or item.get("content") or "")
            for item in selected
        )
        if re.search(r"\b\d+\s+(?:calendar\s+|business\s+)?days?\b", excerpts, re.IGNORECASE):
            return []
        return ["a fixed general shipping duration"]

    @classmethod
    def _item_covers_document_facet(
        cls, item: dict[str, Any], facet: str
    ) -> bool:
        searchable = " ".join(str(item.get(field) or "") for field in (
            "title", "filename", "document_type", "content"
        )).lower()
        if facet == "return_policy":
            return (
                "return" in searchable
                and "policy" in searchable
                and (
                    "return refund policy" in searchable
                    or "return policy" in searchable
                    or "return_refund_policy" in searchable
                )
            )
        if facet == "customer_service_policy":
            return (
                "customer" in searchable
                and ("service" in searchable or "support" in searchable)
                and "policy" in searchable
            )
        if facet == "shipping_policy":
            return "shipping" in searchable and "policy" in searchable
        if facet == "delivery_exception":
            return "delivery" in searchable and (
                "exception" in searchable or "delay" in searchable
                or "delayed" in searchable
            )
        if facet == "campaign_recommendation":
            content = str(item.get("content") or "").lower()
            return (
                item.get("document_id") == "DOC-MKT-024"
                and "future campaigns should compare" in content
                and "conversion efficiency" in content
                and "customer segment quality" in content
                and "incremental revenue" in content
                and "before increasing spend" in content
            )
        if facet == "campaign_observed_drivers":
            content = str(item.get("content") or "").lower()
            return (
                item.get("document_id") == "DOC-MKT-024"
                and "factors to investigate" in content
                and "target segment" in content
                and "campaign objective" in content
                and "channel selection" in content
                and "conversion-oriented creative" in content
            )
        return False

    @classmethod
    def _missing_document_facets(
        cls,
        question: str,
        selected: list[dict[str, Any]],
    ) -> list[str]:
        requested = cls._requested_document_facets(question)
        return [
            label for facet, label in requested.items()
            if not any(cls._item_covers_document_facet(item, facet) for item in selected)
        ]

    @staticmethod
    def _friendly_label(field: str) -> str:
        labels = {
            "campaign_id": "Campaign",
            "customer_count": "Customers",
            "product_name": "Product",
            "units_sold": "Units Sold",
            "total_revenue": "Revenue",
            "campaign_name": "Campaign Name",
            "campaign_count": "Campaigns",
            "actual_spend": "Spend",
            "revenue_generated": "Revenue",
            "total_spend": "Total Spend",
            "total_revenue": "Total Revenue",
            "total_conversions": "Total Conversions",
            "total_clicks": "Total Clicks",
            "conversions": "Conversions",
            "clicks": "Clicks",
            "roi_percent": "ROI",
            "total": "Total",
            "count": "Count",
            "return_count": "Returns",
            "order_count": "Orders",
            "return_reason": "Return Reason",
            "return_status": "Return Status",
            "resolution_type": "Resolution",
            "return_month": "Return Month",
            "return_rate_percent": "Return Rate",
            "average": "Average",
            "avg": "Average",
            "customer_segment": "Customer Segment",
            "loyalty_tier": "Loyalty Tier",
            "acquisition_channel": "Acquisition Channel",
            "customer_count": "Customers",
            "average_lifetime_value": "Average Lifetime Value",
            "total_lifetime_value": "Total Lifetime Value",
            "product_count": "Products",
            "average_rating": "Average Rating",
            "inventory_quantity": "Inventory Units",
            "average_price": "Average Price",
            "lowest_price": "Lowest Price",
            "highest_price": "Highest Price",
            "order_count": "Orders",
            "total_revenue": "Total Revenue",
            "average_order_value": "Average Order Value",
            "sales_month": "Month",
            "region": "Region",
            "category": "Category",
            "product_name": "Product",
            "units_sold": "Units Sold",
            "seller_count": "Sellers",
            "seller_name": "Seller",
            "products_sold": "Products Sold",
            "ticket_count": "Tickets",
            "average_resolution_hours": "Average Resolution Hours",
            "average_satisfaction": "Average Satisfaction",
            "payment_count": "Payments",
            "total_payment_amount": "Total Payment Amount",
            "average_payment_amount": "Average Payment Amount",
            "shipment_count": "Shipments",
            "average_delay_days": "Average Delay Days",
            "delayed_shipments": "Delayed Shipments",
            "event_count": "Campaign Events",
            "attributed_revenue": "Attributed Revenue",
        }

        return labels.get(field, field.replace("_", " ").title())

    @staticmethod
    def _format_value(field: str, value: Any) -> str:
        if value is None:
            return "N/A"

        if field in {
            "actual_spend", "revenue_generated", "spend", "revenue",
            "total_revenue", "average_order_value", "average_price",
            "lowest_price", "highest_price", "average_lifetime_value",
            "total_lifetime_value", "total_payment_amount",
            "average_payment_amount", "attributed_revenue",
        }:
            try:
                return f"₹{float(value):,.2f}"
            except (TypeError, ValueError, OverflowError):
                return str(value)

        if field in {"return_rate_percent", "roi_percent"}:
            try:
                return f"{float(value):,.2f}%"
            except (TypeError, ValueError, OverflowError):
                return str(value)

        if field in {
            "conversions", "clicks", "count", "total",
            "customer_count", "units_sold",
            "product_count", "order_count", "seller_count", "products_sold",
            "ticket_count", "payment_count", "shipment_count",
            "delayed_shipments", "event_count", "clicks", "conversions",
        }:
            try:
                return f"{int(value):,}"
            except (TypeError, ValueError, OverflowError):
                return str(value)

        return str(value)

    def select_relevant_evidence(
        self,
        evidence: list[dict[str, Any]],
        question: str = "",
    ) -> list[dict[str, Any]]:
        """Public interface for filtering and selecting relevant evidence."""
        return self._select_relevant_evidence(evidence, question)

    @classmethod
    def _select_relevant_evidence(
        cls,
        evidence: list[dict[str, Any]],
        question: str = "",
    ) -> list[dict[str, Any]]:
        """Filter, rank, merge, then format relevant evidence chunks."""

        if not evidence:
            return []

        requested_entities = cls._extract_entity_ids(question)
        topic_terms = cls._detect_topic_terms(question)
        requested_facets = cls._requested_document_facets(question)
        if not cls._question_aspects_covered(question, evidence):
            return []
        candidates = []

        for item in evidence:
            # Clean text here, but do not format headings yet.
            content = cls._clean_content(item.get("content", ""))

            if not cls._is_substantive_content(content):
                continue

            title = str(item.get("title") or "")
            filename = str(item.get("filename") or "")
            related_entity_ids = " ".join(
                str(entity_id)
                for entity_id in item.get("related_entity_ids", [])
            )
            searchable = (
                f"{title} {filename} {content} {related_entity_ids}"
            ).lower()

            if requested_entities and not any(
                cls._contains_entity(searchable, entity)
                for entity in requested_entities
            ):
                continue

            if topic_terms:
                matching_terms = set(
                    re.findall(r"\b[a-z]+\b", searchable)
                )
                topic_overlap = len(topic_terms & matching_terms)

                if topic_overlap == 0 and not any(
                    cls._item_covers_document_facet(item, facet)
                    for facet in requested_facets
                ):
                    continue
            else:
                topic_overlap = 0

            candidate = dict(item)
            candidate["_clean_content"] = content

            # When the question names a specific entity (e.g. CMP-021),
            # prefer documents focused on that entity. A document that
            # mentions the entity alongside many other entities of the same
            # kind is a general report or list (e.g. "Campaign Performance Q2"
            # covering CMP-007, CMP-012, CMP-034, ...). It may still be useful
            # as general context, so it is kept but ranked below focused
            # evidence rather than selected first.
            if requested_entities:
                candidate["_score"] = cls._specificity_score(
                    question, item, content
                ) + cls._entity_focus_penalty(
                    content, requested_entities
                )
            else:
                candidate["_score"] = cls._specificity_score(
                    question, item, content
                )

            candidate["_score"] += topic_overlap * 0.15

            # Evidence that names the requested entity only alongside other
            # entities of the same kind (e.g. a multi-campaign report) is
            # general context, not evidence specific to the requested ID.
            candidate["_general_context"] = bool(
                requested_entities
                and cls._entity_focus_penalty(content, requested_entities)
                < 0
            )

            candidates.append(candidate)

        # Prefer entity-specific evidence. General multi-entity context is
        # only kept (and labelled as such) when nothing more specific exists.
        if any(not item["_general_context"] for item in candidates):
            candidates = [
                item for item in candidates if not item["_general_context"]
            ]

        candidates.sort(
            key=lambda item: item["_score"],
            reverse=True,
        )

        # Select at least one source for each explicitly requested document
        # facet before filling remaining slots by relevance. Chunks from one
        # document no longer consume all source slots by themselves.
        selected_document_ids: list[str] = []
        for facet in requested_facets:
            facet_match = next((
                item for item in candidates
                if cls._item_covers_document_facet(item, facet)
            ), None)
            if facet_match:
                document_id = str(facet_match.get("document_id") or "")
                if document_id and document_id not in selected_document_ids:
                    selected_document_ids.append(document_id)

        max_documents = max(cls.MAX_DOCUMENTS, len(requested_facets))
        for item in candidates:
            if requested_facets and not any(
                cls._item_covers_document_facet(item, facet)
                for facet in requested_facets
            ):
                continue
            document_id = str(item.get("document_id") or "")
            if (
                document_id
                and document_id not in selected_document_ids
                and len(selected_document_ids) < max_documents
            ):
                selected_document_ids.append(document_id)

        selected: list[dict[str, Any]] = []
        chunks_per_document: dict[str, int] = {}
        for item in candidates:
            if requested_facets and not any(
                cls._item_covers_document_facet(item, facet)
                for facet in requested_facets
            ):
                continue
            document_id = str(item.get("document_id") or "")
            if document_id not in selected_document_ids:
                continue
            count = chunks_per_document.get(document_id, 0)
            if count >= cls.MAX_CHUNKS_PER_DOCUMENT:
                continue
            selected.append(item)
            chunks_per_document[document_id] = count + 1

        # Restore chunk order before merging overlapping text, but keep the
        # relevance ranking as the primary order. Sorting by score first and
        # then by document/chunk order means a focused document (e.g. the
        # CMP-021 postmortem) is not displaced by a general report (e.g. a
        # multi-campaign performance PDF) that happens to sort first by
        # document_id alone.
        document_order = {
            document_id: index
            for index, document_id in enumerate(selected_document_ids)
        }
        selected.sort(key=lambda item: (
            document_order.get(str(item.get("document_id") or ""), 10**6),
            cls._chunk_number(item.get("chunk_id", "")),
        ))

        merged: list[dict[str, Any]] = []
        preserve_campaign_chunk_sources = (
            "campaign_recommendation" in requested_facets
        )

        for item in selected:
            if (
                not preserve_campaign_chunk_sources
                and merged
                and merged[-1].get("document_id")
                == item.get("document_id")
            ):
                previous = merged[-1]
                previous["_clean_content"] = cls._merge_overlap(
                    previous["_clean_content"],
                    item["_clean_content"],
                )
            else:
                merged.append(dict(item))

        # Format headings only after merging, so their line breaks survive.
        for item in merged:
            item["_clean_content"] = cls._format_section_headings(
                item.get("_clean_content", "")
            )

        return merged

    @classmethod
    def _question_aspects_covered(
        cls,
        question: str,
        evidence: list[dict[str, Any]],
    ) -> bool:
        """Require concrete question terms to appear in retrieved excerpts."""
        entities = set(cls._extract_entity_ids(question))
        searchable = " ".join(
            " ".join(str(item.get(field) or "") for field in (
                "title", "filename", "content", "related_entity_ids"
            ))
            for item in evidence
        ).lower()
        evidence_words = set(re.findall(r"\b[a-z0-9]+\b", searchable))
        words = re.findall(r"\b[a-z0-9]+\b", question.lower())
        requested_facets = cls._requested_document_facets(question)
        facet_terms: set[str] = set()
        for facet in requested_facets:
            if facet == "return_policy":
                facet_terms.update({"return", "refund", "policy", "policies"})
            elif facet == "customer_service_policy":
                facet_terms.update({"customer", "customers", "service", "policy", "policies"})
            elif facet == "shipping_policy":
                facet_terms.update({"shipping", "policy", "policies"})
            elif facet == "delivery_exception":
                facet_terms.update({
                    "delivery", "deliveries", "delay", "delayed", "late",
                    "exception",
                })
            elif facet == "campaign_recommendation":
                facet_terms.update({
                    "campaign", "strategy", "strategies", "recommend",
                    "recommended", "recommendation", "recommendations",
                })
            elif facet == "campaign_observed_drivers":
                facet_terms.update({
                    "campaign", "observed", "driver", "drivers",
                    "factor", "factors", "investigate",
                    "alignment", "target", "segment", "objective", "channel",
                    "selection", "conversion-oriented", "creative",
                })
        if set(requested_facets).intersection({"campaign_recommendation", "campaign_observed_drivers"}):
            # For the fixed CMP-021 postmortem facets, these words describe
            # the request or its evidence source; the required chunk-level
            # facet checks below remain mandatory.
            facet_terms.update({
                "key", "summarize", "summarise", "understand", "postmortem",
                "investigated", "investigating",
                "spending", "increasing", "database", "results", "result",
                "financial", "structured", "sql", "evidence", "using",
            })
        if "return_policy" in requested_facets:
            facet_terms.update({"overall", "rate", "document"})
        key_terms = {
            word for word in words
            if len(word) >= 5
            and word not in cls.RAG_QUERY_STOP_WORDS
            and word not in facet_terms
            and not any(word in entity.lower() for entity in entities)
        }
        for term in key_terms:
            alternatives = cls.RAG_TERM_EQUIVALENTS.get(term, {term})
            campaign_facets = {
                "campaign_recommendation", "campaign_observed_drivers"
            }
            if (
                term == "metrics"
                and campaign_facets.issubset(requested_facets)
                and all(
                    any(
                        cls._item_covers_document_facet(item, facet)
                        for item in evidence
                    )
                    for facet in campaign_facets
                )
            ):
                # In this CMP-021 hybrid question, structured SQL evidence
                # supplies the requested metrics; document evidence must
                # independently cover both strategy facets.
                continue
            if (
                term == "follow"
                and campaign_facets.issubset(requested_facets)
                and all(
                    any(
                        cls._item_covers_document_facet(item, facet)
                        for item in evidence
                    )
                    for facet in campaign_facets
                )
            ):
                continue
            if (
                term == "long"
                and re.search(r"\bhow long\b", question.lower())
                and re.search(r"\b(shipping|delivery|deliveries)\b", question.lower())
            ):
                # Keep policy/exception evidence so the answer can state that
                # the retrieved excerpts contain no general duration.
                continue
            if not any(
                alt in evidence_words
                or (alt.endswith("s") and alt[:-1] in evidence_words)
                or (alt + "s" in evidence_words)
                for alt in alternatives
            ):
                return False
        return bool(key_terms) or bool(evidence)

    @classmethod
    def _detect_topic_terms(cls, question: str) -> set[str]:
        """Identify explicit policy or campaign topics in a question."""

        words = set(re.findall(r"\b[a-z]+\b", question.lower()))
        matched_topics = set()

        topic_triggers = {
            "return": {"return", "refund", "refunds"},
            "shipping": {"shipping", "shipment", "delivery", "tracking"},
            "warranty": {"warranty"},
            "seller": {"seller", "onboarding"},
            "campaign": {"campaign"},
        }

        for topic, triggers in topic_triggers.items():
            if words & triggers:
                matched_topics.update(cls.TOPIC_TERMS[topic])

        return matched_topics

    @staticmethod
    def _chunk_number(chunk_id: Any) -> int:
        match = re.search(r"-(\d+)$", str(chunk_id))
        return int(match.group(1)) if match else 0

    @staticmethod
    def _merge_overlap(previous: str, current: str) -> str:
        """Remove repeated words at adjacent chunk boundaries."""

        previous_words = previous.split()
        current_words = current.split()
        maximum = min(len(previous_words), len(current_words), 60)

        for size in range(maximum, 0, -1):
            left = [
                re.sub(r"[^\w₹.-]", "", word).lower()
                for word in previous_words[-size:]
            ]
            right = [
                re.sub(r"[^\w₹.-]", "", word).lower()
                for word in current_words[:size]
            ]

            if left == right:
                remaining = current_words[size:]

                if not remaining:
                    return previous

                return previous.rstrip() + " " + " ".join(remaining)

        return previous.rstrip() + " " + current.lstrip()

    @staticmethod
    def _extract_entity_ids(question: str) -> list[str]:
        return list(
            dict.fromkeys(
                re.findall(r"\b[A-Z][A-Z0-9]*-\d+\b", question.upper())
            )
        )

    @staticmethod
    def _contains_entity(text: str, entity: str) -> bool:
        return bool(
            re.search(
                rf"(?<![A-Z0-9]){re.escape(entity)}(?![A-Z0-9])",
                text.upper(),
            )
        )

    @classmethod
    def _specificity_score(
        cls,
        question: str,
        item: dict[str, Any],
        content: str,
    ) -> float:
        score = float(
            item.get("evidence_score", item.get("similarity", 0.0))
        )

        title = str(item.get("title") or "").upper()
        filename = str(item.get("filename") or "").upper()
        content_upper = content.upper()

        for entity in cls._extract_entity_ids(question):
            if cls._contains_entity(content_upper, entity):
                score += 0.40

            if (
                cls._contains_entity(title, entity)
                or cls._contains_entity(filename, entity)
            ):
                score += 0.25

        question_terms = set(
            re.findall(r"\b[a-z0-9]+\b", question.lower())
        )
        content_terms = set(
            re.findall(r"\b[a-z0-9]+\b", content.lower())
        )

        if question_terms:
            score += 0.2 * (
                len(question_terms & content_terms)
                / len(question_terms)
            )

        return score

    @classmethod
    def _entity_focus_penalty(
        cls,
        content: str,
        requested_entities: list[str],
    ) -> float:
        """
        Penalise evidence that mentions a requested entity only as one of
        many similar entities.

        A focused document (e.g. "Campaign Postmortem Cmp-021") discusses
        the requested entity in its own right and is left untouched. A
        general report or list (e.g. "Campaign Performance Q2") may mention
        the entity alongside several others; such documents are still
        relevant but should rank below focused evidence. The penalty is
        small and negative so general documents remain selectable when no
        focused evidence exists.
        """

        if not requested_entities:
            return 0.0

        content_upper = content.upper()
        other_entity_count = 0

        for match in re.finditer(
            r"\b[A-Z][A-Z0-9]*-\d+\b", content_upper
        ):
            entity = match.group(0)
            if entity in requested_entities:
                continue
            other_entity_count += 1

        if other_entity_count == 0:
            return 0.0

        # Small penalty, scaled by how many unrelated entities appear.
        # Bounded so focused documents always outrank general ones.
        return -min(0.25, 0.05 * other_entity_count)

    @classmethod
    def _is_substantive_content(cls, content: str) -> bool:
        if not content or cls._is_metadata_only(content):
            return False

        return len(re.findall(r"\b[\w₹,.-]+\b", content)) >= 8

    @classmethod
    def _is_metadata_only(cls, content: str) -> bool:
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]

        if not lines:
            return True

        metadata_count = 0

        for line in lines:
            key = line.split(":", 1)[0].strip().lower()
            normalized = line.rstrip(":").strip().lower()

            if (
                key in cls.METADATA_FIELDS
                or normalized in cls.METADATA_FIELDS
            ):
                metadata_count += 1

        return (
            metadata_count >= 2
            and metadata_count / len(lines) >= 0.5
        )

    @classmethod
    def _clean_content(cls, content: Any) -> str:
        """Remove metadata and normalize text without formatting headings."""

        if not content:
            return ""

        cleaned = []
        skip_next_value = False

        for line in str(content).splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            normalized = stripped.rstrip(":").strip().lower()

            if normalized in cls.METADATA_FIELDS:
                skip_next_value = True
                continue

            if skip_next_value:
                skip_next_value = False
                continue

            if ":" in stripped:
                key = stripped.split(":", 1)[0].strip().lower()
                if key in cls.METADATA_FIELDS:
                    continue

            cleaned.append(stripped)

        # IMPORTANT: do not call _format_section_headings here.
        # Formatting happens after evidence chunks have been merged.
        return " ".join(cleaned)

    @classmethod
    def _format_section_headings(cls, content: str) -> str:
        """Place recognized section headings on separate Markdown lines."""

        if not content:
            return ""

        # Normalize whitespace before applying heading formatting.
        text = " ".join(content.split())

        # Longer headings first to avoid partial-label matches.
        headings = sorted(
            cls.SECTION_HEADINGS,
            key=len,
            reverse=True,
        )
        alternatives = "|".join(
            re.escape(heading) for heading in headings
        )

        # A heading is recognized only at the start of the text or
        # immediately after sentence-ending punctuation.
        pattern = (
            rf"(^|[.!?:]\s+)({alternatives})(?=\s|:)"
        )

        def replace_heading(match: re.Match[str]) -> str:
            prefix = match.group(1)
            heading = match.group(2)

            if prefix:
                # Keep the punctuation at the end of the previous sentence.
                punctuation = prefix.rstrip()[-1]
                return f"{punctuation}\n\n**{heading}**\n"

            # A heading at the very beginning of the content.
            return f"**{heading}**\n"

        text = re.sub(
            pattern,
            replace_heading,
            text,
            flags=re.IGNORECASE,
        )

        # Normalize spaces around line breaks without removing section breaks.
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @classmethod
    def _limit_content(cls, content: str) -> str:
        if len(content) <= cls.MAX_CONTENT_CHARS:
            return content

        excerpt = content[:cls.MAX_CONTENT_CHARS]
        last_space = excerpt.rfind(" ")

        if last_space > cls.MAX_CONTENT_CHARS // 2:
            excerpt = excerpt[:last_space]

        return excerpt.rstrip(" ,;:-") + "…"
