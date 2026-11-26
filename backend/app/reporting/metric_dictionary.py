"""Centralized Metric Dictionary and Definitions for AgentOps AI Reporting.
Maintains authoritative formulas, units, database sources, validation constraints,
and explicit distinctions between Zero, Missing, Unavailable, and Not Applicable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MetricValueStatus(str, Enum):
    VALID = "valid"
    ZERO = "zero"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class MetricDefinition(BaseModel):
    """Authoritative definition and metadata for an enterprise business metric."""
    metric_id: str
    name: str
    category: str
    unit: str
    formula: str
    source_table: str
    description: str
    assumptions: str
    limitations: str
    is_financial: bool = False
    requires_holdout_test: bool = False


# Central Registry of Approved Enterprise Metrics
ENTERPRISE_METRIC_REGISTRY: Dict[str, MetricDefinition] = {
    "total_gross_revenue": MetricDefinition(
        metric_id="total_gross_revenue",
        name="Gross Billed Revenue",
        category="Sales & Commercial",
        unit="INR (₹)",
        formula="SUM(orders.total_amount) WHERE order_status = 'delivered' AND payment_status = 'paid'",
        source_table="orders",
        description="Cumulative commercial customer billings for successfully completed orders.",
        assumptions="Reflects customer checkout invoice totals prior to vendor COGS, shipping subsidy, and platform overhead.",
        limitations="Does not represent net GAAP enterprise profit or operating margin.",
        is_financial=True,
    ),
    "net_item_revenue": MetricDefinition(
        metric_id="net_item_revenue",
        name="Net Line-Item Revenue",
        category="Merchandising",
        unit="INR (₹)",
        formula="SUM(order_items.item_total) = SUM((quantity * unit_price) - discount)",
        source_table="order_items",
        description="Actual net revenue realized per product line item after deducting promotional discounts.",
        assumptions="Unit price corresponds to the transaction-time catalog price; discount reflects applied coupons.",
        limitations="Excludes tax and shipping charges allocated at the order header level.",
        is_financial=True,
    ),
    "gross_list_revenue": MetricDefinition(
        metric_id="gross_list_revenue",
        name="Gross List Value (Pre-Discount)",
        category="Merchandising",
        unit="INR (₹)",
        formula="SUM(order_items.quantity * products.unit_price)",
        source_table="order_items, products",
        description="Theoretical revenue if all units were sold at full catalog list price with zero promotions.",
        assumptions="Catalog price reflects current benchmark price.",
        limitations="Does not equal actual bank receipts due to promotional vouchers.",
        is_financial=True,
    ),
    "total_orders": MetricDefinition(
        metric_id="total_orders",
        name="Total Fulfilled Orders",
        category="Operations",
        unit="Count",
        formula="COUNT(orders.order_id) WHERE order_status = 'delivered'",
        source_table="orders",
        description="Total distinct order consignments successfully processed and fulfilled.",
        assumptions="Cancelled, abandoned, and failed orders are excluded.",
        limitations="Does not measure individual physical items in multi-line baskets.",
    ),
    "average_order_value": MetricDefinition(
        metric_id="average_order_value",
        name="Average Order Value (AOV)",
        category="Commercial",
        unit="INR (₹)",
        formula="total_gross_revenue / total_orders",
        source_table="orders",
        description="Mean transaction ticket size across all fulfilled orders.",
        assumptions="Equally weighted per transaction regardless of customer tenure.",
        limitations="A high AOV does not prove multi-item shopping baskets; it frequently reflects high-ticket single SKUs (e.g. OLED TVs).",
        is_financial=True,
    ),
    "average_units_per_order": MetricDefinition(
        metric_id="average_units_per_order",
        name="Average Basket Unit Depth",
        category="Merchandising",
        unit="Units / Order",
        formula="AVG(unit_count) FROM (SELECT order_id, SUM(quantity) as unit_count FROM order_items GROUP BY order_id)",
        source_table="order_items",
        description="Average number of physical product units purchased per customer transaction.",
        assumptions="Aggregated across all merchandise categories.",
        limitations="Varies substantially between FMCG grocery and durable consumer electronics.",
    ),
    "active_customers": MetricDefinition(
        metric_id="active_customers",
        name="Active Transacting Customers",
        category="Customer",
        unit="Accounts",
        formula="COUNT(DISTINCT orders.customer_id)",
        source_table="orders",
        description="Number of unique registered customer accounts that placed at least one completed order.",
        assumptions="Accounts represent verified unique platform identifiers.",
        limitations="Does not distinguish between single-purchase guest accounts and multi-year loyalists without tier segmentation.",
    ),
    "category_revenue_share": MetricDefinition(
        metric_id="category_revenue_share",
        name="Category Revenue Contribution Share",
        category="Merchandising",
        unit="Percentage (%)",
        formula="(Category Net Line-Item Revenue / Total Departmental Revenue) * 100",
        source_table="order_items, products",
        description="Proportion of total merchandise turnover generated by a specific product division.",
        assumptions="All 6 divisions sum to 100.0% within rounding tolerance.",
        limitations="Reflects top-line commercial turnover; does not reflect category gross margin contribution.",
    ),
    "category_return_rate": MetricDefinition(
        metric_id="category_return_rate",
        name="Category Return Incidence Rate",
        category="Reverse Logistics",
        unit="Percentage (%)",
        formula="(Category Returned Orders / Category Fulfilled Orders) * 100",
        source_table="returns, order_items, products",
        description="Percentage of fulfilled orders within a category that resulted in a logged return claim.",
        assumptions="Order-item level return tracking joined via order_item_id.",
        limitations="Does not isolate product defects from buyer remorse or carrier transit damage without inspection logs.",
    ),
    "return_contribution_share": MetricDefinition(
        metric_id="return_contribution_share",
        name="Category Return Contribution to Total Returns",
        category="Reverse Logistics",
        unit="Percentage (%)",
        formula="(Category Returned Orders / Total Enterprise Returned Orders) * 100",
        source_table="returns, order_items, products",
        description="Proportion of total enterprise return volume originating from a specific category.",
        assumptions="Must sum to 100.0% across all categories.",
        limitations="Categories with higher order volume naturally generate more returns even with low return rates.",
    ),
    "campaign_spend": MetricDefinition(
        metric_id="campaign_spend",
        name="Actual Promotional Media Spend",
        category="Marketing",
        unit="INR (₹)",
        formula="SUM(marketing_campaigns.actual_spend)",
        source_table="marketing_campaigns",
        description="Total paid advertising and promotional capital disbursed across media channels.",
        assumptions="Reflects media platform billing invoices; agency management fees excluded.",
        limitations="Historical spend; does not account for ad auction price inflation.",
        is_financial=True,
    ),
    "attributed_ad_revenue": MetricDefinition(
        metric_id="attributed_ad_revenue",
        name="Campaign Attributed Commercial Revenue",
        category="Marketing",
        unit="INR (₹)",
        formula="SUM(marketing_campaigns.revenue_generated)",
        source_table="marketing_campaigns",
        description="Commercial turnover attributed to marketing campaign touchpoints.",
        assumptions="Reflects tracking pixel / platform recorded revenue; attribution model is not specified in database.",
        limitations="Does not prove incremental causality; includes customers who may have purchased organically.",
        is_financial=True,
        requires_holdout_test=True,
    ),
    "campaign_roas": MetricDefinition(
        metric_id="campaign_roas",
        name="Return on Ad Spend (ROAS Multiplier)",
        category="Marketing",
        unit="Multiplier (x)",
        formula="Attributed Revenue / Actual Media Spend",
        source_table="marketing_campaigns",
        description="Top-line gross commercial turnover generated per Rupee of media investment.",
        assumptions="Media spend > 0; attributed revenue measured over standard campaign reporting window.",
        limitations="A ROAS > 1.0x does NOT mean the campaign is net profitable; COGS and operational costs must be deducted.",
        is_financial=True,
    ),
    "revenue_based_net_yield_pct": MetricDefinition(
        metric_id="revenue_based_net_yield_pct",
        name="Revenue-Based Ad Net Yield (%)",
        category="Marketing",
        unit="Percentage (%)",
        formula="((Attributed Revenue - Media Spend) / Media Spend) * 100",
        source_table="marketing_campaigns",
        description="Percentage excess of attributed top-line revenue over direct media outlay.",
        assumptions="Measures media spread efficiency; equivalent to (ROAS - 1.0) * 100.",
        limitations="Must NOT be described as 'Net Profit' or 'Profit Margin'. Excludes product procurement and logistics expenses.",
        is_financial=True,
    ),
    "revenue_based_net_yield_amount": MetricDefinition(
        metric_id="revenue_based_net_yield_amount",
        name="Revenue-Based Net Ad Yield Spread",
        category="Marketing",
        unit="INR (₹)",
        formula="Attributed Revenue - Media Spend",
        source_table="marketing_campaigns",
        description="Absolute Rupee spread between top-line attributed commercial revenue and direct media spend.",
        assumptions="Measures top-line commercial contribution above ad spend.",
        limitations="Does not represent net earnings; COGS, payment processing, and picking/packing are not deducted.",
        is_financial=True,
    ),
    "on_time_delivery_rate": MetricDefinition(
        metric_id="on_time_delivery_rate",
        name="Carrier On-Time Delivery Compliance Rate",
        category="Operations",
        unit="Percentage (%)",
        formula="(On-Time Delivered Shipments / Total Delivered Shipments) * 100",
        source_table="shipments",
        description="Proportion of completed deliveries fulfilled with zero transit delay.",
        assumptions="Evaluated exclusively on completed consignments with delivery_status = 'DELIVERED'.",
        limitations="Does not measure in-transit consignments whose final delivery timing is pending.",
    ),
    "fulfillment_rate": MetricDefinition(
        metric_id="fulfillment_rate",
        name="Shipment Consignment Fulfillment Rate",
        category="Operations",
        unit="Percentage (%)",
        formula="(Delivered Shipments / Total Shipments Assigned) * 100",
        source_table="shipments",
        description="Proportion of total assigned shipment dispatches that have completed final delivery.",
        assumptions="Total assigned shipments equals Delivered plus In-Transit consignments.",
        limitations="In-transit consignments represent active deliveries in transit.",
    ),
    "customer_lifetime_value": MetricDefinition(
        metric_id="customer_lifetime_value",
        name="Customer Lifetime Value (Historical Account Valuation)",
        category="Customer",
        unit="INR (₹)",
        formula="AVG(customers.lifetime_value)",
        source_table="customers",
        description="Historical transacting account valuation as recorded in the master customer profile ledger.",
        assumptions="Recorded across registered accounts within each loyalty tier.",
        limitations="Does not denote predictive future LTV or net contribution-margin-based LTV.",
        is_financial=True,
    ),
}


class ValidatedMetricValue:
    """Stores a single calculated metric value along with its definition, status, and reporting context."""

    def __init__(
        self,
        metric_id: str,
        value: Any,
        status: MetricValueStatus = MetricValueStatus.VALID,
        period_label: str = "All Time",
        notes: Optional[str] = None,
    ) -> None:
        self.metric_id = metric_id
        self.definition = ENTERPRISE_METRIC_REGISTRY.get(metric_id)
        self.value = value
        self.status = status
        self.period_label = period_label
        self.notes = notes

    @property
    def is_available(self) -> bool:
        return self.status in (MetricValueStatus.VALID, MetricValueStatus.ZERO)

    def format_value(self) -> str:
        if self.status == MetricValueStatus.UNAVAILABLE:
            return "Unavailable"
        if self.status == MetricValueStatus.MISSING:
            return "Missing Data"
        if self.status == MetricValueStatus.NOT_APPLICABLE:
            return "N/A"
        if self.status == MetricValueStatus.ZERO:
            return "0"
        if isinstance(self.value, float):
            return f"{self.value:,.2f}"
        if isinstance(self.value, int):
            return f"{self.value:,}"
        return str(self.value)
