"""Universal High-Resolution Static Chart Generator for AgentOps AI Reports.
Uses Matplotlib Agg backend with the platform's executive palette,
native Indian Rupee ₹ support, clean typography, and 200 DPI resolution.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional
import matplotlib

# Headless backend
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Configure Matplotlib fonts for Unicode Rupee symbol ₹ support
plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# Universal Palette
PALETTE = {
    "midnight_navy": "#081426",
    "deep_graphite": "#141C2B",
    "dark_card": "#0D1527",
    "border": "#24324D",
    "electric_cyan": "#00CFE8",
    "royal_blue": "#397BFF",
    "emerald": "#18B889",
    "violet": "#9476E8",
    "rose_pink": "#E85D9E",
    "champagne_gold": "#D6B36A",
    "warm_white": "#F7F8FA",
    "text_muted": "#8A99B5",
    "text_light": "#E2E8F0",
}


def _setup_axes_style(fig: plt.Figure, ax: plt.Axes, title: str) -> None:
    """Applies refined dark editorial styling to axes."""
    fig.patch.set_facecolor(PALETTE["dark_card"])
    ax.set_facecolor(PALETTE["dark_card"])
    ax.tick_params(colors=PALETTE["text_muted"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(PALETTE["border"])
        spine.set_linewidth(0.8)
    ax.grid(True, linestyle="--", linewidth=0.5, color=PALETTE["border"], alpha=0.5)
    ax.set_title(title, color=PALETTE["text_light"], fontsize=9.5, fontweight="bold", pad=10)


def generate_revenue_trend_chart(
    timeline_data: List[Dict[str, Any]],
    title: str = "Monthly Revenue & Order Trajectory",
    width: float = 6.8,
    height: float = 2.7,
) -> bytes:
    """Generate dual-axis combo chart for revenue (₹ in Lakhs) and order counts.
    Explicitly labels trailing 12-month windows with exact start and end months.
    """
    if not timeline_data:
        timeline_data = [{"month": "2025-01", "revenue": 1000000.0, "orders": 100}]

    slice_data = timeline_data[-12:] if len(timeline_data) >= 12 else timeline_data
    months = [str(item.get("month", "")) for item in slice_data]
    revenues = [float(item.get("revenue", 0)) / 100000.0 for item in slice_data]
    orders = [int(item.get("orders", 0)) for item in slice_data]

    # Explicitly label Trailing 12 Months with exact bounds if dataset exceeds 12 months
    chart_title = title
    if len(timeline_data) > 12 and "trailing" not in chart_title.lower():
        start_m, end_m = months[0], months[-1]
        chart_title = f"Monthly Trend — Trailing 12 Months ({start_m} to {end_m})"
    elif len(slice_data) == 12 and "trailing" not in chart_title.lower():
        start_m, end_m = months[0], months[-1]
        chart_title = f"Monthly Trend — Trailing 12 Months ({start_m} to {end_m})"

    fig, ax1 = plt.subplots(figsize=(width, height), dpi=200)
    _setup_axes_style(fig, ax1, chart_title)

    x = range(len(months))
    ax1.bar(x, revenues, color=PALETTE["royal_blue"], alpha=0.55, width=0.45, label="Revenue (₹ Lakhs)")
    ax1.set_ylabel("Revenue (₹ Lakhs)", color=PALETTE["electric_cyan"], fontsize=8, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=PALETTE["electric_cyan"])

    # Secondary axis for order count
    ax2 = ax1.twinx()
    ax2.plot(x, orders, color=PALETTE["champagne_gold"], marker="o", markersize=4, linewidth=1.8, label="Orders")
    ax2.set_ylabel("Fulfilled Orders", color=PALETTE["champagne_gold"], fontsize=8, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=PALETTE["champagne_gold"], labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color(PALETTE["border"])
        spine.set_linewidth(0.8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(months, rotation=30, ha="right", fontsize=7.5)

    # Combined Legend
    l1, lab1 = ax1.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(l1 + l2, lab1 + lab2, loc="upper left", facecolor=PALETTE["midnight_navy"], edgecolor=PALETTE["border"], fontsize=7)
    for text in legend.get_texts():
        text.set_color(PALETTE["text_light"])

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_category_donut_chart(
    category_data: List[Dict[str, Any]],
    title: str = "Revenue Contribution by Category",
    width: float = 4.2,
    height: float = 2.7,
) -> bytes:
    """Generate donut chart for category share with accurate percentages."""
    if not category_data:
        category_data = [{"category": "General", "revenue": 100.0, "share_pct": 100.0}]

    items = category_data[:6]
    labels = [str(item.get("category", "Other"))[:16] for item in items]
    values = [float(item.get("revenue", 0)) for item in items]

    colors = [
        PALETTE["electric_cyan"],
        PALETTE["champagne_gold"],
        PALETTE["emerald"],
        PALETTE["rose_pink"],
        PALETTE["royal_blue"],
        PALETTE["violet"],
    ][: len(labels)]

    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_facecolor(PALETTE["dark_card"])
    ax.set_facecolor(PALETTE["dark_card"])

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.76,
        textprops={"color": PALETTE["text_light"], "fontsize": 7.5},
        wedgeprops=dict(width=0.42, edgecolor=PALETTE["dark_card"], linewidth=1.5),
    )

    for autotext in autotexts:
        autotext.set_color(PALETTE["midnight_navy"])
        autotext.set_fontweight("bold")
        autotext.set_fontsize(6.5)

    ax.set_title(title, color=PALETTE["text_light"], fontsize=9.5, fontweight="bold", pad=10)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_top_products_bar_chart(
    products_data: List[Dict[str, Any]],
    title: str = "Top Performing Products by Net Billed Revenue",
    width: float = 6.8,
    height: float = 2.8,
) -> bytes:
    """Generate horizontal bar chart for top products with net billed revenue tags."""
    if not products_data:
        products_data = [{"product_name": "Product A", "total_revenue": 1000000.0}]

    items = list(reversed(products_data[:7]))
    names = [str(p.get("product_name", "Product"))[:26] for p in items]
    revs = [float(p.get("total_revenue", 0)) / 100000.0 for p in items]  # In ₹ Lakhs

    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    _setup_axes_style(fig, ax, title)

    bars = ax.barh(range(len(names)), revs, color=PALETTE["electric_cyan"], alpha=0.75, height=0.55, edgecolor=PALETTE["electric_cyan"])
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=7.5)
    ax.set_xlabel("Net Billed Revenue (₹ Lakhs)", color=PALETTE["text_muted"], fontsize=8)

    max_val = max(revs) if revs else 1.0
    for bar, val in zip(bars, revs):
        ax.text(
            bar.get_width() + (max_val * 0.015),
            bar.get_y() + bar.get_height() / 2,
            f"₹{val:.1f}L",
            va="center",
            ha="left",
            fontsize=7,
            color=PALETTE["champagne_gold"],
            fontweight="bold",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_campaign_roi_chart(
    campaign_data: List[Dict[str, Any]],
    title: str = "Top Campaigns by Capital Efficiency (Ranked by ROAS)",
    width: float = 6.8,
    height: float = 2.8,
) -> bytes:
    """Generate high-resolution horizontal bar chart comparing actual spend and attributed revenue
    for top campaigns ranked strictly by ROAS (Efficiency Multiplier). Matches Table 1.
    """
    if not campaign_data:
        campaign_data = [{"campaign_name": "Campaign A", "id": "CMP-001", "spend": 1000000.0, "revenue": 2500000.0, "roas": 2.5}]

    # Sort strictly by ROAS descending to guarantee consistency with Table 1
    items = sorted(campaign_data, key=lambda c: c.get("roas", 0.0), reverse=True)[:7]
    # Reverse so top ROAS appears at top of horizontal chart
    items = list(reversed(items))

    names = [f"{c.get('id', '')}: {str(c.get('campaign_name', 'Campaign'))[:22]}" for c in items]
    spends = [float(c.get("spend", 0)) / 100000.0 for c in items]  # In ₹ Lakhs
    revenues = [float(c.get("revenue", 0)) / 100000.0 for c in items]
    roas_vals = [float(c.get("roas", 0.0)) for c in items]

    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    _setup_axes_style(fig, ax, title)

    y = range(len(names))
    height_bar = 0.35

    ax.barh([i - height_bar / 2 for i in y], spends, height=height_bar, label="Actual Spend (₹ Lakhs)", color="#3B82F6", alpha=0.85)
    ax.barh([i + height_bar / 2 for i in y], revenues, height=height_bar, label="Attributed Rev (₹ Lakhs)", color=PALETTE["electric_cyan"], alpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=7.5)
    ax.set_xlabel("Financial Metric Amount (₹ in Lakhs)", color=PALETTE["text_muted"], fontsize=8)

    # Annotate ROAS on each campaign
    max_rev = max(revenues) if revenues else 1.0
    for i, (rev, roas) in enumerate(zip(revenues, roas_vals)):
        ax.text(
            rev + (max_rev * 0.02),
            i + height_bar / 2,
            f"{roas:.2f}x ROAS",
            va="center",
            ha="left",
            fontsize=7,
            color=PALETTE["emerald"],
            fontweight="bold",
        )

    # Set x limit to prevent label cutoff
    ax.set_xlim(0, max_rev * 1.25)

    legend = ax.legend(loc="lower right", facecolor=PALETTE["midnight_navy"], edgecolor=PALETTE["border"], fontsize=7)
    for text in legend.get_texts():
        text.set_color(PALETTE["text_light"])

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_customer_tiers_chart(
    tier_data: List[Dict[str, Any]],
    title: str = "Customer Loyalty Tiers Distribution",
    width: float = 4.2,
    height: float = 2.7,
) -> bytes:
    """Generate bar chart for customer loyalty tier distribution."""
    if not tier_data:
        tier_data = [{"tier": "Standard", "customer_count": 1000}]

    tiers = [str(t.get("tier", "Tier")).title() for t in tier_data]
    counts = [int(t.get("customer_count", 0)) for t in tier_data]

    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    _setup_axes_style(fig, ax, title)

    colors = [
        PALETTE["champagne_gold"],
        PALETTE["royal_blue"],
        PALETTE["emerald"],
        PALETTE["rose_pink"],
        PALETTE["violet"],
    ][: len(tiers)]

    bars = ax.bar(tiers, counts, color=colors, alpha=0.85, width=0.48)
    ax.set_ylabel("Registered Customers", color=PALETTE["text_muted"], fontsize=8)
    ax.tick_params(axis="x", labelsize=8)

    max_c = max(counts) if counts else 1
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + (max_c * 0.02),
            f"{int(h):,}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=PALETTE["text_light"],
            fontweight="bold",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
