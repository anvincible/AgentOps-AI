import re
from typing import Any


class AnswerComposer:
    """Compose readable answers from SQL and RAG evidence."""

    MAX_DOCUMENTS = 2
    MAX_CONTENT_CHARS = 3000

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
    }

    RAG_TERM_EQUIVALENTS = {
        "timeline": {"window", "days", "within", "refund"},
        "service": {"support", "service"},
        "defective": {"damaged", "quality", "defect"},
        "returns": {"return"},
        "refunds": {"refund"},
        "disputes": {"dispute"},
        "performed": {"performance", "perform"},
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

        if not rows:
            return "I could not find any matching data."

        lines = ["Here is what I found:"]

        for row in rows:
            values = dict(zip(columns, row))

            for column, value in values.items():
                label = self._friendly_label(column)
                formatted = self._format_value(column, value)
                lines.append(f"- **{label}:** {formatted}")

        return self._with_interpretation("\n".join(lines), query_plan or {})

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

        lines = ["Based on the available documents:"]

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

        if selected:
            lines.extend(["", "**Supporting Document Evidence**"])

            for item in selected:
                title = self._display_title(item)

                content = item.get(
                    "_clean_content",
                    self._clean_content(item.get("content", "")),
                )

                if content:
                    lines.extend(["", f"**{title}**", content])

        if not lines:
            return (
                "I could not find enough relevant information "
                "to answer the question."
            )

        return self._limit_content("\n".join(lines))

    @staticmethod
    def _display_title(item: dict[str, Any]) -> str:
        title = (
            item.get("title")
            or item.get("filename")
            or "Supporting document"
        )
        if item.get("_general_context"):
            title = f"{title} (general context, covers multiple campaigns)"
        return str(title)

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
            searchable = f"{title} {filename} {content}".lower()

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

                if topic_overlap == 0:
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

        selected = candidates[:cls.MAX_DOCUMENTS]

        # Restore chunk order before merging overlapping text, but keep the
        # relevance ranking as the primary order. Sorting by score first and
        # then by document/chunk order means a focused document (e.g. the
        # CMP-021 postmortem) is not displaced by a general report (e.g. a
        # multi-campaign performance PDF) that happens to sort first by
        # document_id alone.
        selected.sort(
            key=lambda item: (
                -item["_score"],
                str(item.get("document_id", "")),
                cls._chunk_number(item.get("chunk_id", "")),
            )
        )

        merged: list[dict[str, Any]] = []

        for item in selected:
            if (
                merged
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
        key_terms = {
            word for word in words
            if len(word) >= 5
            and word not in cls.RAG_QUERY_STOP_WORDS
            and not any(word in entity.lower() for entity in entities)
        }
        for term in key_terms:
            alternatives = cls.RAG_TERM_EQUIVALENTS.get(term, {term})
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
