import re
from datetime import date
from typing import Any

from backend.app.sql.schema_inspector import DatabaseSchemaLoader


class SQLGenerator:
    """
    Generates SQL queries from a structured SQL reasoning plan.

    Phase 3.8 responsibilities:
    - Receive a structured query plan from SQLReasoner
    - Generate SQL using the actual database schema
    - Keep SQL generation separate from question reasoning
    """

    def __init__(self, schema_loader: DatabaseSchemaLoader):
        self.schema_loader = schema_loader
        self.schema = schema_loader.load_schema()

    def get_schema(self) -> dict[str, Any]:
        """
        Return the loaded database schema.
        """
        return self.schema

    def generate_query(
        self, query_plan: dict[str, Any]
    ) -> tuple[str, tuple[Any, ...]]:
        """Generate a deterministic query and any bound parameter values."""
        if query_plan.get("entity_type") == "analytics":
            return self._generate_analytics_sql(query_plan)
        if query_plan.get("entity_type") == "customer":
            return self._generate_customer_query(query_plan)
        if query_plan.get("entity_type") == "product":
            return self._generate_product_query(query_plan)
        return self.generate_sql(query_plan), ()

    def generate_sql(self, query_plan: dict[str, Any]) -> str:
        """
        Generate SQL from a structured query plan.
        """

        if not query_plan:
            raise ValueError("Query plan cannot be empty.")

        table = query_plan.get("table")
        operation = query_plan.get("operation")
        columns = query_plan.get("columns")
        filters = query_plan.get("filters")

        if not table:
            raise ValueError("Query plan must contain a table.")

        if operation != "SELECT":
            raise ValueError("Only SELECT operations are supported.")

        if not columns:
            raise ValueError("Query plan must contain columns.")

        self._validate_table(table)

        if query_plan.get("entity_type") == "analytics":
            return self._generate_analytics_sql(query_plan)[0]

        if query_plan.get("entity_type") == "return":
            return self._generate_return_sql(query_plan)

        if query_plan.get("entity_type") == "customer":
            return self._generate_customer_query(query_plan)[0]

        if query_plan.get("entity_type") == "product":
            return self._generate_product_query(query_plan)[0]

        if query_plan.get("entity_type") == "campaign":
            campaign_sql = self._generate_campaign_sql(query_plan)
            if campaign_sql is not None:
                return campaign_sql

        if not filters:
            raise ValueError("Query plan must contain filters.")

        for column in columns:
            self._validate_column(table, column)

        sql_columns = ",\n    ".join(
            f"mc.{column}"
            for column in columns
        )

        where_conditions = []

        for filter_item in filters:
            column = filter_item.get("column")
            operator = filter_item.get("operator")
            value = filter_item.get("value")

            if not column or not operator or value is None:
                raise ValueError(
                    "Each filter must contain column, operator, and value."
                )

            self._validate_column(table, column)

            if operator != "=":
                raise ValueError(
                    "The current SQL generator only supports '=' filters."
                )

            escaped_value = str(value).replace("'", "''")

            where_conditions.append(
                f"mc.{column} = '{escaped_value}'"
            )

        where_clause = " AND ".join(where_conditions)

        return f"""
SELECT
    {sql_columns}
FROM {table} AS mc
WHERE {where_clause};
""".strip()

    def _generate_campaign_sql(
        self,
        query_plan: dict[str, Any],
    ) -> str | None:
        intent = query_plan.get("intent")

        if intent == "CAMPAIGN_PERFORMANCE" and query_plan.get("filters"):
            # Keep campaign-ID performance queries on the existing filtered
            # path below. An unfiltered overview is an aggregate, not a rank.
            return None

        if intent in {"CAMPAIGN_SUMMARY", "CAMPAIGN_PERFORMANCE"}:
            for column in (
                "campaign_id",
                "actual_spend",
                "revenue_generated",
                "conversions",
                "clicks",
            ):
                self._validate_column("marketing_campaigns", column)

            return """
SELECT
    COUNT(*) AS campaign_count,
    COALESCE(SUM(actual_spend), 0) AS total_spend,
    COALESCE(SUM(revenue_generated), 0) AS total_revenue,
    COALESCE(SUM(conversions), 0) AS total_conversions,
    COALESCE(SUM(clicks), 0) AS total_clicks
FROM marketing_campaigns;
""".strip()

        if intent in {"CAMPAIGN_COMPARISON", "CAMPAIGN_ROI"}:
            campaign_ids = query_plan.get("entity_ids", [])
            if not campaign_ids:
                raise ValueError(
                    "Campaign comparison requires campaign IDs."
                )

            if any(
                not isinstance(campaign_id, str)
                or not re.fullmatch(r"CMP-\d+", campaign_id)
                for campaign_id in campaign_ids
            ):
                raise ValueError("Campaign IDs have an invalid format.")

            for column in (
                "campaign_id",
                "campaign_name",
                "actual_spend",
                "revenue_generated",
                "conversions",
                "clicks",
            ):
                self._validate_column("marketing_campaigns", column)

            ids = ", ".join(
                f"'{campaign_id}'" for campaign_id in campaign_ids
            )
            roi_select = ""
            if intent == "CAMPAIGN_ROI":
                roi_select = """,
    ROUND(
        (revenue_generated - actual_spend)
        / NULLIF(actual_spend, 0) * 100,
        2
    ) AS roi_percent"""

            return f"""
SELECT
    campaign_id,
    campaign_name,
    actual_spend,
    revenue_generated,
    conversions,
    clicks{roi_select}
FROM marketing_campaigns
WHERE campaign_id IN ({ids})
ORDER BY campaign_id;
""".strip()

        if intent == "CAMPAIGN_RANKING":
            metric = query_plan.get("campaign_metric")
            allowed_metrics = {
                "conversions", "clicks", "actual_spend", "revenue_generated",
                "roi_percent",
            }
            if metric not in allowed_metrics:
                raise ValueError("Unsupported campaign ranking metric.")
            for column in (
                "campaign_id", "campaign_name", "actual_spend",
                "revenue_generated", "conversions", "clicks",
            ):
                self._validate_column("marketing_campaigns", column)
            roi_projection = ""
            nulls = ""
            if metric == "roi_percent":
                roi_projection = ", ROUND((revenue_generated - actual_spend) / NULLIF(actual_spend, 0) * 100, 2) AS roi_percent"
                nulls = " NULLS LAST"
            return f"""
SELECT campaign_id, campaign_name, actual_spend, revenue_generated,
       conversions, clicks{roi_projection}
FROM marketing_campaigns
ORDER BY {metric} DESC{nulls}, campaign_id
LIMIT 10;
""".strip()

        return None

    def _generate_customer_sql(self, query_plan: dict[str, Any]) -> str:
        return self._generate_customer_query(query_plan)[0]

    def _parameterized_date_filter(
        self,
        date_filter: dict[str, int] | None,
        table: str,
        alias: str,
        column: str,
    ) -> tuple[str, tuple[Any, ...]]:
        if not date_filter:
            return "", ()
        self._validate_table(table)
        self._validate_column(table, column)
        if "start_year" in date_filter:
            start = int(date_filter["start_year"])
            end = int(date_filter.get("end_year", start))
            if start < 2000 or end < start or end > 2100:
                raise ValueError("Date year range is outside the supported range.")
            return (
                f"{alias}.{column} >= %s AND {alias}.{column} < %s",
                (date(start, 1, 1), date(end + 1, 1, 1)),
            )
        if "last_days" in date_filter:
            days = int(date_filter["last_days"])
            if not 1 <= days <= 3650:
                raise ValueError("Date range must be between 1 and 3650 days.")
            return (
                f"{alias}.{column} >= CURRENT_DATE - (%s * INTERVAL '1 day')",
                (days,),
            )
        raise ValueError("Unsupported date filter.")

    def _generate_customer_query(
        self, query_plan: dict[str, Any]
    ) -> tuple[str, tuple[Any, ...]]:
        if query_plan.get("intent") != "CUSTOMER_COUNT":
            raise ValueError(
                f"Unsupported customer query intent: {query_plan.get('intent')}"
            )
        self._validate_column("customers", "customer_id")
        where, params = self._parameterized_date_filter(
            query_plan.get("date_filter"), "customers", "c", "registration_date"
        )
        sql = f"SELECT COUNT(*) AS customer_count FROM customers AS c {f'WHERE {where}' if where else ''};"
        return sql, params

    def _generate_product_sql(self, query_plan: dict[str, Any]) -> str:
        intent = query_plan.get("intent")
        for table, column in (
            ("products", "product_id"),
            ("products", "product_name"),
            ("order_items", "product_id"),
            ("order_items", "quantity"),
            ("order_items", "item_total"),
        ):
            self._validate_table(table)
            self._validate_column(table, column)

        if intent == "TOP_PRODUCTS_BY_QUANTITY":
            metric, alias = "SUM(oi.quantity)", "units_sold"
        elif intent == "TOP_PRODUCTS_BY_REVENUE":
            metric, alias = "SUM(oi.item_total)", "total_revenue"
        else:
            raise ValueError(f"Unsupported product query intent: {intent}")

        return f"""
SELECT
    p.product_name,
    {metric} AS {alias}
FROM products AS p
JOIN order_items AS oi ON oi.product_id = p.product_id
GROUP BY p.product_id, p.product_name
ORDER BY {alias} DESC, p.product_name
LIMIT 10;
""".strip()

    def _generate_product_query(
        self, query_plan: dict[str, Any]
    ) -> tuple[str, tuple[Any, ...]]:
        sql = self._generate_product_sql(query_plan)
        date_filter = query_plan.get("date_filter")
        if not date_filter:
            return sql, ()
        self._validate_column("order_items", "order_id")
        self._validate_column("orders", "order_id")
        where, params = self._parameterized_date_filter(
            date_filter, "orders", "o", "order_date"
        )
        sql = sql.replace(
            "JOIN order_items AS oi ON oi.product_id = p.product_id",
            "JOIN order_items AS oi ON oi.product_id = p.product_id\n"
            "JOIN orders AS o ON o.order_id = oi.order_id",
            1,
        )
        sql = sql.replace("GROUP BY", f"WHERE {where}\nGROUP BY", 1)
        return sql, params

    def _generate_analytics_sql(
        self, query_plan: dict[str, Any]
    ) -> tuple[str, tuple[Any, ...]]:
        intent = query_plan.get("intent")
        dimension = query_plan.get("dimension")
        date_filter = query_plan.get("date_filter")
        params: list[Any] = []

        def validate(table: str, *columns: str) -> None:
            self._validate_table(table)
            for column in columns:
                self._validate_column(table, column)

        def date_clause(table: str, alias: str, column: str) -> str:
            if not date_filter:
                return ""
            validate(table, column)
            if "start_year" in date_filter:
                start = int(date_filter["start_year"])
                end = int(date_filter.get("end_year", start))
                if start < 2000 or end < start or end > 2100:
                    raise ValueError("Date year range is outside the supported range.")
                params.extend((date(start, 1, 1), date(end + 1, 1, 1)))
                return f"{alias}.{column} >= %s AND {alias}.{column} < %s"
            if "last_days" in date_filter:
                days = int(date_filter["last_days"])
                if not 1 <= days <= 3650:
                    raise ValueError("Date range must be between 1 and 3650 days.")
                params.append(days)
                return f"{alias}.{column} >= CURRENT_DATE - (%s * INTERVAL '1 day')"
            raise ValueError("Unsupported date filter.")

        def where_line(where: str) -> str:
            return f"WHERE {where}" if where else ""

        if intent == "CUSTOMER_DISTRIBUTION":
            dimensions = {
                "customer_segment", "city", "state", "country",
                "loyalty_tier", "status", "acquisition_channel",
            }
            if dimension not in dimensions:
                raise ValueError("Unsupported customer grouping.")
            validate("customers", "customer_id", dimension)
            where = date_clause("customers", "c", "registration_date")
            sql = f"""
SELECT c.{dimension}, COUNT(*) AS customer_count
FROM customers AS c
{where_line(where)}
GROUP BY c.{dimension}
ORDER BY customer_count DESC, c.{dimension}
LIMIT 100;
"""
            return sql.strip(), tuple(params)

        if intent == "CUSTOMER_STATUS_COUNT":
            status_value = query_plan.get("status_value")
            if status_value not in {"ACTIVE", "NOT_ACTIVE"}:
                raise ValueError("Unsupported customer status filter.")
            validate("customers", "customer_id", "status")
            if status_value == "NOT_ACTIVE":
                sql = "SELECT COUNT(*) AS customer_count FROM customers WHERE status <> %s;"
                return sql, ("ACTIVE",)
            sql = "SELECT COUNT(*) AS customer_count FROM customers WHERE status = %s;"
            return sql, (status_value,)

        if intent in {"CUSTOMER_LTV_SUMMARY", "CUSTOMER_LTV_BY_SEGMENT", "CUSTOMER_LTV_BY_DIMENSION"}:
            validate("customers", "customer_id", "lifetime_value")
            ltv_dimension = query_plan.get("dimension")
            if intent != "CUSTOMER_LTV_SUMMARY":
                if ltv_dimension not in {"customer_segment", "city", "country", "loyalty_tier", "acquisition_channel"}:
                    raise ValueError("Unsupported lifetime value grouping.")
                validate("customers", ltv_dimension)
                select = f"c.{ltv_dimension},"
                group = f"GROUP BY c.{ltv_dimension}"
                order = f"c.{ltv_dimension}"
            else:
                select, group, order = "", "", "average_lifetime_value DESC"
            where = date_clause("customers", "c", "registration_date")
            sql = f"""
SELECT {select}COUNT(*) AS customer_count,
       ROUND(AVG(c.lifetime_value), 2) AS average_lifetime_value,
       ROUND(SUM(c.lifetime_value), 2) AS total_lifetime_value
FROM customers AS c
{where_line(where)}
{group}
ORDER BY {order};
"""
            return sql.strip(), tuple(params)

        if intent == "CUSTOMER_REVENUE_BY_SEGMENT":
            validate("customers", "customer_id", "customer_segment")
            validate("orders", "order_id", "customer_id", "order_date", "total_amount")
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT c.customer_segment, COUNT(DISTINCT c.customer_id) AS customer_count,
       COUNT(o.order_id) AS order_count,
       ROUND(SUM(o.total_amount), 2) AS total_revenue,
       ROUND(AVG(o.total_amount), 2) AS average_order_value
FROM customers AS c
JOIN orders AS o ON o.customer_id = c.customer_id
{where_line(where)}
GROUP BY c.customer_segment
ORDER BY total_revenue DESC;
"""
            return sql.strip(), tuple(params)

        if intent == "PRODUCT_DISTRIBUTION":
            if dimension not in {"category", "brand", "subcategory"}:
                raise ValueError("Unsupported product grouping.")
            validate("products", "product_id", dimension, "rating")
            sql = f"""
SELECT p.{dimension}, COUNT(*) AS product_count,
       ROUND(AVG(p.rating), 2) AS average_rating
FROM products AS p
GROUP BY p.{dimension}
ORDER BY product_count DESC, p.{dimension}
LIMIT 100;
"""
            return sql.strip(), ()

        if intent in {"PRODUCT_INVENTORY", "LOW_STOCK_PRODUCTS"}:
            validate(
                "products", "product_id", "product_name", "category",
                "inventory_quantity", "active_status",
            )
            if intent == "LOW_STOCK_PRODUCTS":
                threshold = int(query_plan.get("threshold", 10))
                if not 0 <= threshold <= 100000:
                    raise ValueError("Stock threshold is outside the supported range.")
                params.append(threshold)
                where = "WHERE p.inventory_quantity <= %s"
            else:
                where = ""
            sql = f"""
SELECT p.product_id, p.product_name, p.category,
       p.inventory_quantity, p.active_status
FROM products AS p
{where}
ORDER BY p.inventory_quantity ASC, p.product_name
LIMIT 20;
"""
            return sql.strip(), tuple(params)

        if intent == "PRODUCT_METRICS":
            measure = query_plan.get("measure")
            if dimension is not None and dimension not in {"category", "brand", "subcategory"}:
                raise ValueError("Unsupported product metric grouping.")
            if measure == "rating":
                validate("products", "rating")
                if dimension:
                    validate("products", dimension)
                    sql = f"SELECT {dimension}, COUNT(*) AS product_count, ROUND(AVG(rating), 2) AS average_rating, MIN(rating) AS lowest_rating, MAX(rating) AS highest_rating FROM products WHERE rating IS NOT NULL GROUP BY {dimension} ORDER BY average_rating DESC;"
                else:
                    sql = (
                        "SELECT ROUND(AVG(rating), 2) AS average_rating, "
                        "MIN(rating) AS lowest_rating, MAX(rating) AS highest_rating "
                        "FROM products WHERE rating IS NOT NULL;"
                    )
            elif measure == "unit_price":
                validate("products", "unit_price")
                if dimension:
                    validate("products", dimension)
                    sql = f"SELECT {dimension}, COUNT(*) AS product_count, ROUND(AVG(unit_price), 2) AS average_price, MIN(unit_price) AS lowest_price, MAX(unit_price) AS highest_price FROM products WHERE unit_price IS NOT NULL GROUP BY {dimension} ORDER BY average_price DESC;"
                else:
                    sql = (
                        "SELECT ROUND(AVG(unit_price), 2) AS average_price, "
                        "MIN(unit_price) AS lowest_price, MAX(unit_price) AS highest_price "
                        "FROM products WHERE unit_price IS NOT NULL;"
                    )
            else:
                raise ValueError("Unsupported product metric.")
            return sql, ()

        if intent == "SALES_SUMMARY":
            validate("orders", "order_id", "total_amount", "order_date")
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT COUNT(*) AS order_count,
       ROUND(COALESCE(SUM(o.total_amount), 0), 2) AS total_revenue,
       ROUND(COALESCE(AVG(o.total_amount), 0), 2) AS average_order_value
FROM orders AS o
{where_line(where)};
"""
            return sql.strip(), tuple(params)

        if intent == "SALES_BY_ACQUISITION_CHANNEL":
            validate("orders", "order_id", "acquisition_channel", "total_amount", "order_date")
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT o.acquisition_channel, COUNT(*) AS order_count,
       ROUND(SUM(o.total_amount), 2) AS total_revenue,
       ROUND(AVG(o.total_amount), 2) AS average_order_value
FROM orders AS o
{where_line(where)}
GROUP BY o.acquisition_channel
ORDER BY total_revenue DESC;
"""
            return sql.strip(), tuple(params)

        if intent in {"SALES_BY_MONTH", "SALES_BY_REGION"}:
            validate("orders", "order_id", "order_date", "total_amount")
            if intent == "SALES_BY_MONTH":
                key, label = "DATE_TRUNC('month', o.order_date)::date", "sales_month"
            else:
                validate("orders", "region")
                key, label = "o.region", "region"
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT {key} AS {label}, COUNT(*) AS order_count,
       ROUND(SUM(o.total_amount), 2) AS total_revenue,
       ROUND(AVG(o.total_amount), 2) AS average_order_value
FROM orders AS o
{where_line(where)}
GROUP BY {key}
ORDER BY total_revenue DESC
LIMIT 100;
"""
            return sql.strip(), tuple(params)

        if intent in {"SALES_BY_CATEGORY", "SALES_BY_PRODUCT"}:
            validate("products", "product_id", "product_name", "category")
            validate("order_items", "order_id", "product_id", "item_total", "quantity")
            validate("orders", "order_id", "order_date")
            if intent == "SALES_BY_CATEGORY":
                key, label, grouping = "p.category", "category", "p.category"
            else:
                key, label, grouping = "p.product_name", "product_name", "p.product_id, p.product_name"
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT {key} AS {label}, COUNT(DISTINCT o.order_id) AS order_count,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.item_total), 2) AS total_revenue
FROM products AS p
JOIN order_items AS oi ON oi.product_id = p.product_id
JOIN orders AS o ON o.order_id = oi.order_id
{where_line(where)}
GROUP BY {grouping}
ORDER BY total_revenue DESC
LIMIT 100;
"""
            return sql.strip(), tuple(params)

        if intent == "ORDER_STATUS_DISTRIBUTION":
            validate("orders", "order_id", "order_status")
            return (
                "SELECT order_status, COUNT(*) AS order_count FROM orders "
                "GROUP BY order_status ORDER BY order_count DESC, order_status;",
                (),
            )

        if intent == "SELLER_COUNT":
            validate("sellers", "seller_id")
            return "SELECT COUNT(*) AS seller_count FROM sellers;", ()

        if intent == "SELLER_PERFORMANCE":
            validate("sellers", "seller_id", "seller_name")
            validate("order_items", "seller_id", "order_id", "product_id", "quantity", "item_total")
            validate("orders", "order_id", "order_date")
            where = date_clause("orders", "o", "order_date")
            sql = f"""
SELECT s.seller_name, COUNT(DISTINCT oi.order_id) AS order_count,
       COUNT(DISTINCT oi.product_id) AS products_sold,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.item_total), 2) AS total_revenue
FROM sellers AS s
JOIN order_items AS oi ON oi.seller_id = s.seller_id
JOIN orders AS o ON o.order_id = oi.order_id
{where_line(where)}
GROUP BY s.seller_id, s.seller_name
ORDER BY total_revenue DESC
LIMIT 20;
"""
            return sql.strip(), tuple(params)

        if intent == "SUPPORT_TICKET_ANALYTICS":
            dimensions = {"status", "issue_category", "priority", "assigned_team"}
            if dimension not in dimensions:
                raise ValueError("Unsupported support ticket grouping.")
            validate(
                "support_tickets", "ticket_id", dimension, "ticket_date",
                "resolution_time_hours", "satisfaction_score",
            )
            where = date_clause("support_tickets", "t", "ticket_date")
            sql = f"""
SELECT t.{dimension}, COUNT(*) AS ticket_count,
       ROUND(AVG(t.resolution_time_hours), 2) AS average_resolution_hours,
       ROUND(AVG(t.satisfaction_score), 2) AS average_satisfaction
FROM support_tickets AS t
{where_line(where)}
GROUP BY t.{dimension}
ORDER BY ticket_count DESC, t.{dimension}
LIMIT 100;
"""
            return sql.strip(), tuple(params)

        if intent == "PAYMENT_ANALYTICS":
            if dimension not in {"payment_method", "payment_status"}:
                raise ValueError("Unsupported payment grouping.")
            validate("payments", "payment_id", dimension, "amount", "payment_date")
            where = date_clause("payments", "p", "payment_date")
            sql = f"""
SELECT p.{dimension}, COUNT(*) AS payment_count,
       ROUND(SUM(p.amount), 2) AS total_payment_amount,
       ROUND(AVG(p.amount), 2) AS average_payment_amount
FROM payments AS p
{where_line(where)}
GROUP BY p.{dimension}
ORDER BY total_payment_amount DESC, p.{dimension};
"""
            return sql.strip(), tuple(params)

        if intent == "SHIPMENT_ANALYTICS":
            if dimension not in {"delivery_status", "carrier", "destination_region"}:
                raise ValueError("Unsupported shipment grouping.")
            validate("shipments", "shipment_id", dimension, "delay_days", "shipment_date")
            where = date_clause("shipments", "sh", "shipment_date")
            sql = f"""
SELECT sh.{dimension}, COUNT(*) AS shipment_count,
       ROUND(AVG(sh.delay_days), 2) AS average_delay_days,
       COUNT(*) FILTER (WHERE sh.delay_days > 0) AS delayed_shipments
FROM shipments AS sh
{where_line(where)}
GROUP BY sh.{dimension}
ORDER BY shipment_count DESC, sh.{dimension};
"""
            return sql.strip(), tuple(params)

        if intent == "CAMPAIGN_CHANNEL_PERFORMANCE":
            validate(
                "marketing_events", "channel", "event_id", "event_type",
                "conversion_flag", "revenue_attributed", "event_timestamp",
            )
            where = date_clause("marketing_events", "e", "event_timestamp")
            sql = f"""
SELECT e.channel, COUNT(*) AS event_count,
       COUNT(*) FILTER (WHERE e.event_type = 'click') AS clicks,
       COUNT(*) FILTER (WHERE e.conversion_flag IS TRUE) AS conversions,
       ROUND(COALESCE(SUM(e.revenue_attributed), 0), 2) AS attributed_revenue
FROM marketing_events AS e
{where_line(where)}
GROUP BY e.channel
ORDER BY attributed_revenue DESC, e.channel;
"""
            return sql.strip(), tuple(params)

        raise ValueError(f"Unsupported analytics query intent: {intent}")

    def _generate_return_sql(self, query_plan: dict[str, Any]) -> str:
        intent = query_plan.get("intent")

        required_columns = {
            "RETURN_TOTAL": ["return_id"],
            "RETURN_REASONS": ["return_reason"],
            "RETURN_STATUS": ["return_status"],
            "RETURN_RESOLUTIONS": ["resolution_type"],
            "RETURN_TRENDS": ["return_date"],
        }

        for column in required_columns.get(intent, []):
            self._validate_column("returns", column)

        if intent == "RETURN_TOTAL":
            return """
SELECT COUNT(*) AS return_count
FROM returns;
""".strip()

        if intent == "RETURN_REASONS":
            return """
SELECT
    return_reason,
    COUNT(*) AS return_count
FROM returns
WHERE return_reason IS NOT NULL
GROUP BY return_reason
ORDER BY return_count DESC, return_reason;
""".strip()

        if intent == "RETURN_STATUS":
            return """
SELECT
    return_status,
    COUNT(*) AS return_count
FROM returns
WHERE return_status IS NOT NULL
GROUP BY return_status
ORDER BY return_count DESC, return_status;
""".strip()

        if intent == "RETURN_RESOLUTIONS":
            return """
SELECT
    resolution_type,
    COUNT(*) AS return_count
FROM returns
WHERE resolution_type IS NOT NULL
GROUP BY resolution_type
ORDER BY return_count DESC, resolution_type;
""".strip()

        if intent == "RETURN_TRENDS":
            return """
SELECT
    DATE_TRUNC('month', return_date)::date AS return_month,
    COUNT(*) AS return_count
FROM returns
WHERE return_date IS NOT NULL
GROUP BY DATE_TRUNC('month', return_date)::date
ORDER BY return_month;
""".strip()

        if intent == "RETURN_RATE":
            self._validate_table("orders")
            self._validate_column("returns", "return_id")
            self._validate_column("orders", "order_id")
            return """
SELECT
    r.return_count,
    o.order_count,
    ROUND(
        r.return_count::numeric / NULLIF(o.order_count, 0) * 100,
        2
    ) AS return_rate_percent
FROM (
    SELECT COUNT(*) AS return_count
    FROM returns
) AS r
CROSS JOIN (
    SELECT COUNT(*) AS order_count
    FROM orders
) AS o;
""".strip()

        raise ValueError(
            f"Unsupported return query intent: {intent}"
        )

    def _validate_table(self, table_name: str) -> None:
        """
        Verify that the table exists in the loaded database schema.
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
        Verify that a column exists in the selected table.
        """

        table_info = self.schema["tables"].get(table_name)

        if not table_info:
            raise ValueError(
                f"Table does not exist in the schema: {table_name}"
            )

        valid_columns = {
            column["column_name"]
            for column in table_info.get("columns", [])
        }

        if column_name not in valid_columns:
            raise ValueError(
                f"Column does not exist in table "
                f"{table_name}: {column_name}"
            )
