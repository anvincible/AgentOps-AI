import re
from typing import Any

from backend.app.sql.schema_inspector import DatabaseSchemaLoader


class SQLReasoner:
    """
    Performs structured reasoning over a natural-language question
    before SQL generation.

    Phase 3.7 responsibilities:
    - Understand the user's question
    - Identify the intent
    - Identify the entity
    - Identify the relevant table
    - Identify the required columns
    - Identify filters
    - Validate that the selected table and columns exist
      in the actual NovaMart database schema

    This is a deterministic reasoning layer and does not use
    an LLM yet.
    """

    def __init__(self, schema_loader: DatabaseSchemaLoader):
        self.schema_loader = schema_loader
        self.schema = schema_loader.load_schema()

    def reason(self, question: str) -> dict[str, Any]:
        """
        Convert a natural-language question into a structured
        SQL query plan.
        """

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        question_lower = question.lower().strip()

        campaign_ids = self._extract_campaign_ids(question)

        if "campaign" in question_lower or campaign_ids:
            return self._reason_campaign(
                question,
                question_lower,
                campaign_ids,
            )

        if self._is_return_question(question_lower):
            return self._reason_return(question, question_lower)

        if self._is_customer_count_question(question_lower):
            return self._reason_customer_count(question)

        if self._is_product_ranking_question(question_lower) or (
            "product" in question_lower
            and any(term in question_lower for term in ("revenue", "sales"))
            and any(term in question_lower for term in ("top", "most", "highest", "best"))
        ):
            return self._reason_product_ranking(question, question_lower)

        if "customer" in question_lower:
            return self._reason_customer_analytics(question, question_lower)

        if "product" in question_lower or "inventory" in question_lower or "stock" in question_lower:
            return self._reason_product_analytics(question, question_lower)

        if "support ticket" in question_lower or "support tickets" in question_lower or "ticket" in question_lower:
            return self._reason_support_analytics(question, question_lower)

        if "payment" in question_lower:
            return self._reason_payment_analytics(question, question_lower)

        if "shipment" in question_lower or "delivery" in question_lower:
            return self._reason_shipment_analytics(question, question_lower)

        if "seller" in question_lower:
            return self._reason_seller_analytics(question, question_lower)

        if any(term in question_lower for term in ("sales", "revenue", "orders", "order ", "order value")):
            return self._reason_sales_analytics(question, question_lower)

        raise ValueError(
            "The SQL reasoner does not support this structured data question yet."
        )

    def _analytics_plan(
        self,
        question: str,
        intent: str,
        tables: list[str],
        columns: list[str],
        **details: Any,
    ) -> dict[str, Any]:
        for table in tables:
            self._validate_table(table)
        for table, column in columns:
            self._validate_column(table, column)
        return {
            "question": question,
            "intent": intent,
            "entity_type": "analytics",
            "table": tables[0],
            "tables": tables,
            "operation": "SELECT",
            "columns": [column for _, column in columns],
            "filters": [],
            **details,
        }

    @staticmethod
    def _extract_date_filter(question_lower: str) -> dict[str, int] | None:
        year_range = re.search(
            r"\b(?:in|during|for|from|between)\s+(20\d{2})"
            r"(?:\s+(?:to|through|and)\s+(20\d{2}))?\b",
            question_lower,
        )
        if year_range:
            return {
                "start_year": int(year_range.group(1)),
                "end_year": int(year_range.group(2) or year_range.group(1)),
            }

        days = re.search(r"\b(?:last|past)\s+(\d{1,4})\s+days?\b", question_lower)
        if days:
            return {"last_days": min(int(days.group(1)), 3650)}
        return None

    def _reason_customer_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        if "lifetime value" in question_lower or "ltv" in question_lower:
            by_segment = "segment" in question_lower
            return self._analytics_plan(
                question,
                "CUSTOMER_LTV_BY_SEGMENT" if by_segment else "CUSTOMER_LTV_SUMMARY",
                ["customers"],
                [("customers", "customer_id"), ("customers", "lifetime_value")]
                + ([ ("customers", "customer_segment") ] if by_segment else []),
                dimension="customer_segment" if by_segment else None,
                date_filter=self._extract_date_filter(question_lower),
            )

        dimension = self._dimension_from_question(
            question_lower,
            {
                "segment": "customer_segment",
                "city": "city",
                "country": "country",
                "state": "state",
                "loyalty tier": "loyalty_tier",
                "loyalty": "loyalty_tier",
                "status": "status",
                "acquisition channel": "acquisition_channel",
                "channel": "acquisition_channel",
            },
        )
        if not dimension and any(word in question_lower for word in ("distribution", "breakdown", "by")):
            dimension = "customer_segment"
        if not dimension:
            raise ValueError(
                "For customer analytics, specify a segment, city, state, country, loyalty tier, status, acquisition channel, or lifetime value."
            )
        return self._analytics_plan(
            question,
            "CUSTOMER_DISTRIBUTION",
            ["customers"],
            [("customers", "customer_id"), ("customers", dimension)],
            dimension=dimension,
            date_filter=self._extract_date_filter(question_lower),
        )

    def _reason_product_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        if any(term in question_lower for term in ("sales by product", "revenue by product", "sales per product")):
            return self._analytics_plan(
                question,
                "SALES_BY_PRODUCT",
                ["orders", "order_items", "products"],
                [("order_items", "item_total"), ("order_items", "quantity"), ("order_items", "product_id"), ("order_items", "order_id"), ("products", "product_name"), ("orders", "order_date")],
                dimension="product",
                date_filter=self._extract_date_filter(question_lower),
            )
        if any(term in question_lower for term in ("inventory", "stock", "reorder")):
            explicit_threshold = re.search(
                r"\b(?:below|under|less than|at most)\s+(\d+)\b",
                question_lower,
            )
            low_stock = any(term in question_lower for term in ("low", "reorder", "below", "under", "less than", "at most"))
            return self._analytics_plan(
                question,
                "LOW_STOCK_PRODUCTS" if low_stock else "PRODUCT_INVENTORY",
                ["products"],
                [("products", column) for column in ("product_id", "product_name", "category", "inventory_quantity", "active_status")],
                threshold=int(explicit_threshold.group(1)) if explicit_threshold else 10,
            )

        dimension = self._dimension_from_question(
            question_lower, {"category": "category", "brand": "brand", "subcategory": "subcategory"}
        )
        if "rating" in question_lower or "price" in question_lower:
            measure = "rating" if "rating" in question_lower else "unit_price"
            required = [("products", measure)]
            if dimension:
                required.append(("products", dimension))
            return self._analytics_plan(
                question,
                "PRODUCT_METRICS",
                ["products"],
                required,
                measure=measure,
                dimension=dimension,
            )
        if dimension:
            return self._analytics_plan(
                question,
                "PRODUCT_DISTRIBUTION",
                ["products"],
                [("products", "product_id"), ("products", dimension)],
                dimension=dimension,
            )
        raise ValueError("Specify product category, brand, inventory, stock, price, or rating for product analytics.")

    def _reason_support_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        dimension = self._dimension_from_question(
            question_lower,
            {"status": "status", "issue": "issue_category", "category": "issue_category", "priority": "priority", "team": "assigned_team"},
        ) or "issue_category"
        return self._analytics_plan(
            question,
            "SUPPORT_TICKET_ANALYTICS",
            ["support_tickets"],
            [("support_tickets", column) for column in ("ticket_id", dimension, "resolution_time_hours", "satisfaction_score")],
            dimension=dimension,
            date_filter=self._extract_date_filter(question_lower),
        )

    def _reason_payment_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        dimension = self._dimension_from_question(
            question_lower, {"method": "payment_method", "status": "payment_status"}
        ) or "payment_status"
        return self._analytics_plan(
            question,
            "PAYMENT_ANALYTICS",
            ["payments"],
            [("payments", column) for column in ("payment_id", dimension, "amount", "payment_date")],
            dimension=dimension,
            date_filter=self._extract_date_filter(question_lower),
        )

    def _reason_shipment_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        dimension = self._dimension_from_question(
            question_lower,
            {"status": "delivery_status", "carrier": "carrier", "region": "destination_region"},
        ) or "delivery_status"
        return self._analytics_plan(
            question,
            "SHIPMENT_ANALYTICS",
            ["shipments"],
            [("shipments", column) for column in ("shipment_id", dimension, "delay_days", "shipment_date")],
            dimension=dimension,
            date_filter=self._extract_date_filter(question_lower),
        )

    def _reason_seller_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        if any(term in question_lower for term in ("how many", "count", "total number")) and not any(term in question_lower for term in ("revenue", "performance", "sales")):
            return self._analytics_plan(
                question, "SELLER_COUNT", ["sellers"], [("sellers", "seller_id")]
            )
        return self._analytics_plan(
            question,
            "SELLER_PERFORMANCE",
            ["sellers", "order_items"],
            [("sellers", "seller_id"), ("sellers", "seller_name"), ("order_items", "order_id"), ("order_items", "product_id"), ("order_items", "quantity"), ("order_items", "item_total")],
            date_filter=self._extract_date_filter(question_lower),
        )

    def _reason_sales_analytics(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        if "acquisition channel" in question_lower:
            return self._analytics_plan(
                question,
                "SALES_BY_ACQUISITION_CHANNEL",
                ["orders"],
                [("orders", "order_id"), ("orders", "acquisition_channel"), ("orders", "total_amount"), ("orders", "order_date")],
                dimension="acquisition_channel",
                date_filter=self._extract_date_filter(question_lower),
            )
        dimension = self._dimension_from_question(
            question_lower,
            {"month": "month", "monthly": "month", "region": "region", "category": "category", "product": "product", "status": "order_status"},
        )
        if dimension == "category":
            intent, tables = "SALES_BY_CATEGORY", ["orders", "order_items", "products"]
            columns = [("order_items", "item_total"), ("products", "category"), ("orders", "order_date")]
        elif dimension == "product":
            intent, tables = "SALES_BY_PRODUCT", ["orders", "order_items", "products"]
            columns = [("order_items", "item_total"), ("products", "product_name"), ("orders", "order_date")]
        elif dimension == "month":
            intent, tables = "SALES_BY_MONTH", ["orders"]
            columns = [("orders", "order_date"), ("orders", "total_amount"), ("orders", "order_id")]
        elif dimension == "region":
            intent, tables = "SALES_BY_REGION", ["orders"]
            columns = [("orders", "region"), ("orders", "order_date"), ("orders", "total_amount"), ("orders", "order_id")]
        elif dimension == "order_status":
            intent, tables = "ORDER_STATUS_DISTRIBUTION", ["orders"]
            columns = [("orders", "order_status"), ("orders", "order_id")]
        else:
            intent, tables = "SALES_SUMMARY", ["orders"]
            columns = [("orders", "order_date"), ("orders", "total_amount"), ("orders", "order_id")]
        return self._analytics_plan(
            question,
            intent,
            tables,
            columns,
            dimension=dimension,
            date_filter=self._extract_date_filter(question_lower),
        )

    @staticmethod
    def _dimension_from_question(
        question_lower: str, dimensions: dict[str, str]
    ) -> str | None:
        for phrase, column in sorted(dimensions.items(), key=lambda pair: len(pair[0]), reverse=True):
            if phrase in question_lower:
                return column
        return None

    @staticmethod
    def _is_customer_count_question(question_lower: str) -> bool:
        has_count_language = bool(
            re.search(r"\b(?:how many|count|number of|total)\b", question_lower)
        )
        has_grouping = bool(
            re.search(
                r"\b(?:by|per|distribution|breakdown|segment|city|state|country|"
                r"loyalty|channel|status)\b",
                question_lower,
            )
        )
        return "customer" in question_lower and has_count_language and not has_grouping

    def _reason_customer_count(self, question: str) -> dict[str, Any]:
        table = "customers"
        self._validate_table(table)
        self._validate_column(table, "customer_id")
        return {
            "question": question,
            "intent": "CUSTOMER_COUNT",
            "entity_type": "customer",
            "entity_id": None,
            "table": table,
            "tables": [table],
            "operation": "SELECT",
            "columns": ["customer_count"],
            "filters": [],
        }

    @staticmethod
    def _is_product_ranking_question(question_lower: str) -> bool:
        ranking_terms = (
            "top", "best-selling", "best selling", "top-selling",
            "top selling", "most sold", "selling",
        )
        return "product" in question_lower and any(
            term in question_lower for term in ranking_terms
        )

    def _reason_product_ranking(
        self, question: str, question_lower: str
    ) -> dict[str, Any]:
        for table, column in (
            ("products", "product_id"),
            ("products", "product_name"),
            ("order_items", "product_id"),
            ("order_items", "quantity"),
            ("order_items", "item_total"),
        ):
            self._validate_table(table)
            self._validate_column(table, column)

        by_revenue = any(
            term in question_lower
            for term in ("revenue", "sales value", "sales amount")
        )
        return {
            "question": question,
            "intent": (
                "TOP_PRODUCTS_BY_REVENUE" if by_revenue
                else "TOP_PRODUCTS_BY_QUANTITY"
            ),
            "entity_type": "product",
            "entity_id": None,
            "table": "products",
            "tables": ["products", "order_items"],
            "operation": "SELECT",
            "columns": ["product_name", "total_revenue" if by_revenue else "units_sold"],
            "filters": [],
        }

    def _reason_campaign(
        self,
        question: str,
        question_lower: str,
        campaign_ids: list[str],
    ) -> dict[str, Any]:
        table = "marketing_campaigns"
        self._validate_table(table)

        campaign_metric = None
        if len(campaign_ids) > 1:
            intent = "CAMPAIGN_COMPARISON"
            columns = [
                "campaign_id",
                "campaign_name",
                "actual_spend",
                "revenue_generated",
                "conversions",
                "clicks",
            ]
        elif campaign_ids and ("roi" in question_lower or "return on investment" in question_lower):
            intent = "CAMPAIGN_ROI"
            columns = [
                "campaign_id",
                "campaign_name",
                "actual_spend",
                "revenue_generated",
            ]
        elif not campaign_ids and self._is_campaign_summary_question(
            question_lower
        ):
            intent = "CAMPAIGN_SUMMARY"
            columns = [
                "campaign_count",
                "total_spend",
                "total_revenue",
                "total_conversions",
                "total_clicks",
            ]
        elif not campaign_ids and "channel" in question_lower:
            return self._analytics_plan(
                question,
                "CAMPAIGN_CHANNEL_PERFORMANCE",
                ["marketing_events"],
                [("marketing_events", column) for column in (
                    "channel", "event_id", "event_type", "conversion_flag",
                    "revenue_attributed", "event_timestamp",
                )],
                date_filter=self._extract_date_filter(question_lower),
            )
        elif not campaign_ids:
            if "roi" in question_lower or "return on investment" in question_lower:
                intent = "CAMPAIGN_RANKING"
                campaign_metric = "roi_percent"
            elif any(term in question_lower for term in ("conversion", "click", "spend", "revenue", "performance", "result", "top", "highest", "most")):
                intent = "CAMPAIGN_RANKING"
                if "conversion" in question_lower:
                    campaign_metric = "conversions"
                elif "click" in question_lower:
                    campaign_metric = "clicks"
                elif "spend" in question_lower:
                    campaign_metric = "actual_spend"
                else:
                    campaign_metric = "revenue_generated"
            else:
                raise ValueError("Specify campaign metrics, an acquisition channel, or a campaign ID.")
            columns = [
                "campaign_id", "campaign_name", "actual_spend",
                "revenue_generated", "conversions", "clicks",
            ]
        # Check broader intents first so performance questions containing
        # words such as revenue or conversions remain campaign queries.
        elif (
            "performance" in question_lower
            or "results" in question_lower
            or "analy" in question_lower
            or "spend" in question_lower
            and "revenue" in question_lower
        ):
            intent = "CAMPAIGN_PERFORMANCE"
            columns = [
                "campaign_id",
                "campaign_name",
                "actual_spend",
                "revenue_generated",
                "conversions",
                "clicks",
            ]
        elif "click" in question_lower:
            intent = "CLICKS"
            columns = [
                "campaign_id",
                "campaign_name",
                "clicks",
            ]
        elif "revenue" in question_lower:
            intent = "REVENUE"
            columns = [
                "campaign_id",
                "campaign_name",
                "revenue_generated",
            ]
        elif "spend" in question_lower:
            intent = "SPEND"
            columns = [
                "campaign_id",
                "campaign_name",
                "actual_spend",
            ]
        elif "conversion" in question_lower:
            intent = "CONVERSIONS"
            columns = [
                "campaign_id",
                "campaign_name",
                "conversions",
            ]
        else:
            raise ValueError(
                "A campaign ID is required for this campaign question."
            )

        derived_columns = {
            "campaign_count",
            "total_spend",
            "total_revenue",
            "total_conversions",
            "total_clicks",
        }
        for column in columns:
            if column not in derived_columns:
                self._validate_column(table, column)

        return {
            "question": question,
            "intent": intent,
            "entity_type": "campaign",
            "entity_id": campaign_ids[0] if campaign_ids else None,
            "entity_ids": campaign_ids,
            "table": table,
            "operation": "SELECT",
            "columns": columns,
            "filters": (
                [{
                    "column": "campaign_id",
                    "operator": "=",
                    "value": campaign_ids[0],
                }]
                if len(campaign_ids) == 1
                else []
            ),
            "campaign_metric": campaign_metric,
        }

    def _reason_return(
        self,
        question: str,
        question_lower: str,
    ) -> dict[str, Any]:
        table = "returns"
        self._validate_table(table)

        if "rate" in question_lower:
            intent = "RETURN_RATE"
            tables = ["returns", "orders"]
            columns = ["return_count", "order_count", "return_rate_percent"]
        elif "reason" in question_lower:
            intent = "RETURN_REASONS"
            tables = [table]
            columns = ["return_reason", "return_count"]
        elif "status" in question_lower:
            intent = "RETURN_STATUS"
            tables = [table]
            columns = ["return_status", "return_count"]
        elif (
            "resolution" in question_lower
            or "refund" in question_lower
            or "replacement" in question_lower
            or "store credit" in question_lower
        ):
            intent = "RETURN_RESOLUTIONS"
            tables = [table]
            columns = ["resolution_type", "return_count"]
        elif "trend" in question_lower or "over time" in question_lower:
            intent = "RETURN_TRENDS"
            tables = [table]
            columns = ["return_month", "return_count"]
        else:
            intent = "RETURN_TOTAL"
            tables = [table]
            columns = ["return_count"]

        for table_name in tables:
            self._validate_table(table_name)

        for column in columns:
            if column not in {"return_count", "order_count", "return_rate_percent", "return_month"}:
                self._validate_column(table, column)

        return {
            "question": question,
            "intent": intent,
            "entity_type": "return",
            "entity_id": None,
            "table": table,
            "tables": tables,
            "operation": "SELECT",
            "columns": columns,
            "filters": [],
        }

    @staticmethod
    def _is_return_question(question_lower: str) -> bool:
        return any(
            term in question_lower
            for term in (
                "return",
                "refund",
                "replacement",
                "store credit",
            )
        )

    @staticmethod
    def _is_campaign_summary_question(question_lower: str) -> bool:
        summary_phrases = (
            "overall campaign",
            "all campaigns",
            "campaign summary",
            "campaign totals",
            "summarize campaign",
            "summarise campaign",
            "campaign overview",
            "campaigns overview",
            "summary of campaign",
            "summary of all campaigns",
        )
        if any(phrase in question_lower for phrase in summary_phrases):
            return True

        if (
            ("summarize" in question_lower or "summarise" in question_lower or "summary" in question_lower)
            and "campaign" in question_lower
        ):
            return True

        return False

    def _validate_table(self, table_name: str) -> None:
        """
        Make sure the selected table exists in the actual schema.
        """

        valid_tables = set(self.schema.get("tables", {}).keys())

        if table_name not in valid_tables:
            raise ValueError(
                f"Table does not exist in the NovaMart database: {table_name}"
            )

    def _validate_column(
        self,
        table_name: str,
        column_name: str,
    ) -> None:
        """
        Make sure the selected column exists in the actual schema.
        """

        table_info = self.schema["tables"].get(table_name)

        if not table_info:
            raise ValueError(
                f"Table does not exist in the schema: {table_name}"
            )

        columns = {
            column["column_name"]
            for column in table_info.get("columns", [])
        }

        if column_name not in columns:
            raise ValueError(
                f"Column does not exist in table "
                f"{table_name}: {column_name}"
            )

    @staticmethod
    def _extract_campaign_ids(question: str) -> list[str]:
        """
        Extract one or more campaign IDs such as CMP-021.
        """

        matches = re.findall(
            r"\bCMP-\d+\b",
            question.upper(),
        )

        return list(dict.fromkeys(matches))

    @classmethod
    def _extract_campaign_id(cls, question: str) -> str | None:
        """Return the first campaign ID for compatibility with callers."""

        campaign_ids = cls._extract_campaign_ids(question)
        return campaign_ids[0] if campaign_ids else None
