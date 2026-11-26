"""Insight Validator and Epistemic Integrity Engine for AgentOps AI Reporting.
Validates business observations, rankings, financial terminology, recommendations,
and executes pre-render Contradiction Detection across narrative, tables, and charts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class InsightValidationError(Exception):
    """Raised when a business insight fails mathematical, ranking, or terminology validation."""
    pass


class InsightValidator:
    """Pre-generation and post-generation validator for business insights, rankings, and recommendations."""

    FORBIDDEN_PROFIT_TERMS = [
        "net profitable",
        "net profit of",
        "profit-based roi",
        "net accretive to profit",
        "bottom-line profit",
    ]

    UNSUPPORTED_ATTRIBUTION_CLAIMS = [
        "uses last-click attribution",
        "under our last-click model",
        "verified last-click attribution",
        "last-touch model confirms",
    ]

    UNSUPPORTED_CUSTOMER_BEHAVIOUR_CLAIMS = [
        ("aov establishes multi-item", "Average Order Value (AOV) reflects order currency ticket size, not multi-item basket depth without unit count data."),
        ("aov proves multi-item", "AOV alone cannot prove multi-item shopping baskets; high-ticket single SKUs can inflate AOV without basket depth."),
        ("orders per customer proves customer retention", "Average orders per customer does not establish customer retention without cohort survival analysis."),
        ("90-day dormancy", "90-day customer dormancy percentage is unverified in operational database records."),
        ("repeat-order uplift", "Arbitrary repeat-order uplift percentages are unsupported without empirical test results."),
    ]

    UNSUPPORTED_PROJECTIONS = [
        "0.15x roas",
        "3-5% aov",
        "3–5% aov",
        "3-5% uplift",
        "3–5% uplift",
        "10-15% budget reallocation",
        "10–15% budget reallocation",
        "5-8% repeat order",
        "guaranteed revenue",
        "guaranteed roas",
        "projected roas expansion",
    ]

    UNSUPPORTED_SYSTEM_CLAIMS = [
        ("infrastructure resilience", "Infrastructure resilience statements are ungrounded in operational transactional ledger data."),
        ("inventory-update latency", "Inventory-update latency statements are unsupported by database schema."),
        ("caching prevents bottlenecks", "Caching assertions cannot be verified from database tables alone."),
    ]

    @classmethod
    def validate_campaign_rankings(
        cls,
        campaigns: List[Dict[str, Any]],
        finding_text: str,
    ) -> Tuple[bool, List[str]]:
        """Validate that any claim regarding campaign performance, efficiency, or scale
        references the mathematically correct campaign.
        """
        issues: List[str] = []
        if not campaigns:
            return True, []

        top_by_roas = max(campaigns, key=lambda c: c.get("roas", 0.0))
        top_by_rev = max(campaigns, key=lambda c: c.get("revenue", 0.0))
        top_by_conv = max(campaigns, key=lambda c: c.get("conversions", 0))

        text_lower = finding_text.lower()

        # 1. Highest Return Efficiency / ROAS Check
        if any(term in text_lower for term in ["highest return efficiency", "highest roas", "superior return efficiency", "most efficient campaign", "capital efficiency leader"]):
            expected_name = top_by_roas.get("campaign_name", "")
            expected_id = top_by_roas.get("id", "")
            if expected_name not in finding_text and expected_id not in finding_text:
                issues.append(
                    f"Finding claims highest return efficiency/ROAS but does not cite top ROAS campaign "
                    f"'{expected_name}' ({expected_id}, ROAS {top_by_roas.get('roas'):.2f}x)."
                )

        # 2. Highest Revenue / Scale Leader Check
        if any(term in text_lower for term in ["largest gross revenue", "highest attributed revenue", "scale leader", "highest volume driver"]):
            expected_name = top_by_rev.get("campaign_name", "")
            expected_id = top_by_rev.get("id", "")
            if expected_name not in finding_text and expected_id not in finding_text:
                issues.append(
                    f"Finding claims highest attributed revenue/scale but does not cite scale leader "
                    f"'{expected_name}' ({expected_id}, Rev {top_by_rev.get('revenue')})."
                )

        # 3. Highest Conversions Check
        if any(term in text_lower for term in ["highest conversion volume", "most conversions"]):
            expected_name = top_by_conv.get("campaign_name", "")
            expected_id = top_by_conv.get("id", "")
            if expected_name not in finding_text and expected_id not in finding_text:
                issues.append(
                    f"Finding claims highest conversion volume but does not cite conversion leader "
                    f"'{expected_name}' ({expected_id}, Conv {top_by_conv.get('conversions')})."
                )

        # 4. Check for Conflating Highest Revenue with Most Efficient
        if ("highest revenue" in text_lower or "scale leader" in text_lower) and ("most efficient" in text_lower or "highest efficiency" in text_lower):
            if top_by_rev.get("id") != top_by_roas.get("id"):
                issues.append(
                    f"Contradiction: Scale leader '{top_by_rev.get('id')}' is erroneously described as most efficient; "
                    f"true efficiency leader is '{top_by_roas.get('id')}' ({top_by_roas.get('roas'):.2f}x ROAS vs {top_by_rev.get('roas'):.2f}x ROAS)."
                )

        return len(issues) == 0, issues

    @classmethod
    def validate_terminology(cls, text: str) -> Tuple[bool, List[str]]:
        """Validate financial terminology and attribution phrasing."""
        issues: List[str] = []
        text_lower = text.lower()

        # Check for ungrounded profit claims on ad spend
        for term in cls.FORBIDDEN_PROFIT_TERMS:
            if term in text_lower:
                issues.append(
                    f"Misleading financial terminology: '{term}' used. Attributed revenue exceeding ad spend "
                    f"does not establish net profitability (COGS and overhead must be accounted for)."
                )

        # Check for ungrounded attribution assertions
        for claim in cls.UNSUPPORTED_ATTRIBUTION_CLAIMS:
            if claim in text_lower:
                issues.append(
                    f"Unsupported attribution assertion: '{claim}'. The underlying database does not "
                    f"document last-click attribution; attribution limitations must be labeled as general considerations."
                )

        # Check for ungrounded customer behaviour claims
        for trigger, explanation in cls.UNSUPPORTED_CUSTOMER_BEHAVIOUR_CLAIMS:
            if trigger in text_lower:
                issues.append(f"Unsupported customer behaviour assertion: '{trigger}'. {explanation}")

        # Check for ungrounded infrastructure or latency claims
        for trigger, explanation in cls.UNSUPPORTED_SYSTEM_CLAIMS:
            if trigger in text_lower:
                issues.append(f"Unsupported system assertion: '{trigger}'. {explanation}")

        # Check for 0.0% delivery described as meeting benchmarks
        if "0.0%" in text and any(b in text_lower for b in ["benchmark", "satisfying", "compliance", "tolerance"]):
            issues.append("Contradiction: A 0.0% delivery rate cannot be described as satisfying enterprise benchmarks.")

        return len(issues) == 0, issues

    @classmethod
    def validate_recommendation_structure(cls, rec_text: str) -> Tuple[bool, List[str]]:
        """Ensure recommendations are qualified with explicit assumptions, limitations, and actions."""
        issues: List[str] = []
        rec_lower = rec_text.lower()

        # Check for ungrounded arbitrary percentage projections (e.g. '0.15x ROAS expansion' or '3-5% AOV uplift')
        for proj in cls.UNSUPPORTED_PROJECTIONS:
            if proj in rec_lower:
                issues.append(
                    f"Recommendation contains unsupported projection '{proj}'. Propose an empirical testable experiment instead."
                )

        if "projected" in rec_lower or "estimated" in rec_lower:
            if "assumption" not in rec_lower and "limitation" not in rec_lower:
                issues.append(
                    "Recommendation contains numerical projection without stating explicit assumptions or limitations."
                )

        # Must have Actionable context or experimental framing
        if "Action:" not in rec_text and "Action Item:" not in rec_text and "test" not in rec_lower and "experiment" not in rec_lower:
            issues.append("Recommendation lacks a concrete, testable action item or experiment design.")

        return len(issues) == 0, issues

    @classmethod
    def validate_epistemic_structure(cls, finding_text: str) -> Tuple[bool, List[str]]:
        """Ensure findings clearly distinguish measured fact from interpretation and implication."""
        issues: List[str] = []

        required_tags = ["[Measured Fact]", "[Interpretation]"]
        for tag in required_tags:
            if tag not in finding_text:
                issues.append(f"Finding missing standard epistemic tag '{tag}'.")

        return len(issues) == 0, issues

    @classmethod
    def validate_contradictions(
        cls,
        text: str,
        data: Any,
    ) -> Tuple[bool, List[str]]:
        """Scans narrative and textual findings against underlying data layer to detect
        contradictions in percentages, category shares, campaign rankings, or customer conclusions.
        """
        issues: List[str] = []
        text_lower = text.lower()

        # 1. Category Concentration Contradiction Detection
        # Searches for statements like: "Electronics and Home Appliances account for over 65%" or similar
        # Detects any sentence with a percentage claim and category names
        known_categories = [
            "electronics",
            "sports",
            "beauty",
            "grocery",
            "home & kitchen",
            "home appliances",
            "fashion",
            "fashion & apparel",
        ]

        if hasattr(data, "categories") and data.categories:
            cat_map: Dict[str, float] = {}
            for c in data.categories:
                c_name = c.get("category", "").lower()
                cat_map[c_name] = c.get("share_pct", 0.0)

            # Match sentences with percentage claims
            sentences = re.split(r"[.!?]\s+", text)
            for s in sentences:
                s_lower = s.lower()
                # Must be a revenue/sales/turnover/receipts/concentration claim, NOT a returns or defect claim
                if not any(term in s_lower for term in ["revenue", "turnover", "receipts", "concentration", "share"]):
                    continue
                if any(term in s_lower for term in ["return", "defect", "cancellation", "refund", "incident"]):
                    continue

                # Check if sentence mentions multiple categories and states combined concentration
                is_concentration_phrase = any(
                    term in s_lower for term in [
                        "over", "more than", "account for", "combined", "together represent", "generate over"
                    ]
                )
                if not is_concentration_phrase:
                    continue

                pct_matches = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*%", s)
                if not pct_matches:
                    continue

                claimed_pct = float(pct_matches[0])
                mentioned_cats = [cat for cat in known_categories if cat in s_lower]

                if len(mentioned_cats) >= 2:
                    # Sum the actual shares of the mentioned categories
                    actual_sum = 0.0
                    for cat in mentioned_cats:
                        for k, v in cat_map.items():
                            if cat in k or k in cat:
                                actual_sum += v
                                break

                    if abs(claimed_pct - actual_sum) > 2.5:
                        issues.append(
                            f"Contradiction in category concentration: text claims ~{claimed_pct:.1f}% for "
                            f"{', '.join(mentioned_cats)}, but actual data total is {actual_sum:.2f}%."
                        )

        # 2. Customer Behaviour Contradiction Check
        for trigger, err_msg in cls.UNSUPPORTED_CUSTOMER_BEHAVIOUR_CLAIMS:
            if trigger in text_lower:
                issues.append(f"Unsupported customer behaviour inference: {err_msg}")

        # 3. Campaign Performance Ranking Contradiction Check
        if hasattr(data, "campaigns") and data.campaigns:
            valid_rank, rank_issues = cls.validate_campaign_rankings(data.campaigns, text)
            issues.extend(rank_issues)

        # 4. Financial Terminology Violations
        valid_terms, term_issues = cls.validate_terminology(text)
        issues.extend(term_issues)

        return len(issues) == 0, issues

    @classmethod
    def classify_statement(cls, text: str) -> str:
        """Classify statement into one of the 5 approved epistemic tiers:
        A. Measured Fact
        B. Calculated Comparison
        C. Interpretation
        D. Hypothesis
        E. Recommendation
        """
        t = text.lower()
        if "recommendation" in t or "action:" in t or "test" in t or "experiment" in t:
            return "E. Recommendation"
        if "[measured fact]" in t:
            return "A. Measured Fact"
        if "[calculated comparison]" in t or "compared to" in t or "multiple" in t or "ratio" in t:
            return "B. Calculated Comparison"
        if "[interpretation]" in t or "suggests" in t or "indicates" in t:
            return "C. Interpretation"
        if "hypothesis" in t or "hypothesize" in t or "potential" in t:
            return "D. Hypothesis"
        return "A. Measured Fact"

    @classmethod
    def reconcile_contradictions(
        cls,
        text: str,
        data: Any,
    ) -> str:
        """Automatically repairs detectable percentage or ranking contradictions in narrative text."""
        reconciled = text

        # 1. Reconcile category concentration claim if hardcoded "over 65%" exists
        if "over 65% of gross revenue is generated by electronics" in reconciled.lower():
            if hasattr(data, "categories") and len(data.categories) >= 2:
                c1 = data.categories[0]
                c2 = data.categories[1]
                actual_pct = c1.get("share_pct", 46.9) + c2.get("share_pct", 11.1)
                reconciled = re.sub(
                    r"[Oo]ver 65% of gross revenue is generated by [A-Za-z &]+",
                    f"{actual_pct:.1f}% of gross revenue is generated by {c1.get('category')} and {c2.get('category')}",
                    reconciled,
                )

        return reconciled
