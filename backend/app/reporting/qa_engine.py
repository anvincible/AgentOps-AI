"""Automated Report Quality Assurance Engine for AgentOps AI.
Performs pre-flight business metric checks, structural validation,
and reconciliation checks before any deliverable is exported.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile

import openpyxl
import pymupdf

from backend.app.reporting.data_layer import ValidatedReportingData
from backend.app.reporting.models import ReportCategory, ReportDocument, ReportFormat, ReportTable


class ReportQAResult:
    """Stores automated QA audit findings and pass/fail status."""

    def __init__(self, is_valid: bool, issues: List[str], metrics_audited: Dict[str, Any]) -> None:
        self.is_valid = is_valid
        self.issues = issues
        self.metrics_audited = metrics_audited

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": self.issues,
            "metrics_audited": self.metrics_audited,
        }


class ReportQAEngine:
    """Pre-flight validator for AgentOps AI reporting pipeline."""

    def validate_data(self, data: ValidatedReportingData) -> ReportQAResult:
        """Audit the aggregated reporting data layer prior to document rendering."""
        issues: List[str] = []
        metrics: Dict[str, Any] = {}

        # 1. Financial totals & AOV consistency
        tot_rev = data.kpis.get("total_revenue", 0.0)
        tot_orders = data.kpis.get("total_orders", 0)
        aov = data.kpis.get("average_order_value", 0.0)
        active_cust = data.kpis.get("active_customers", 0)

        metrics["total_revenue"] = tot_rev
        metrics["total_orders"] = tot_orders
        metrics["aov"] = aov
        metrics["active_customers"] = active_cust

        if tot_orders < 0:
            issues.append(f"Invalid negative order count: {tot_orders}")
        if tot_rev < 0:
            issues.append(f"Invalid negative total revenue: {tot_rev}")

        if tot_orders > 0 and tot_rev > 0:
            expected_aov = tot_rev / tot_orders
            if abs(aov - expected_aov) > 1.0:
                issues.append(f"AOV mismatch: stated {aov:.2f} vs expected {expected_aov:.2f}")

        # 2. Revenue share validation (must sum to ~100%)
        if data.categories:
            shares = [c.get("share_pct", 0.0) for c in data.categories]
            sum_shares = sum(shares)
            metrics["category_count"] = len(data.categories)
            metrics["revenue_shares_sum"] = round(sum_shares, 2)

            if abs(sum_shares - 100.0) > 2.0:
                issues.append(f"Revenue shares sum to {sum_shares:.2f}%, expected 100% ± 2.0%")

            for cat in data.categories:
                if cat.get("revenue", 0) > 0 and cat.get("share_pct", 0.0) <= 0:
                    issues.append(f"Category '{cat.get('category')}' has revenue {cat.get('revenue')} but 0% share")

        # 3. Product data integrity
        if data.top_products:
            metrics["top_products_count"] = len(data.top_products)
            for idx, p in enumerate(data.top_products[:10]):
                p_name = p.get("product_name", "")
                p_id = p.get("product_id", "")
                p_orders = p.get("order_count", 0)

                if not p_name or p_name.strip() == "":
                    issues.append(f"Top product at index {idx} has empty product_name")
                if not p_id or p_id.strip() == "":
                    issues.append(f"Top product '{p_name}' has empty product_id")
                if p.get("total_revenue", 0) > 0 and p_orders <= 0:
                    issues.append(f"Top product '{p_name}' has revenue but 0 order_count")

        # 4. Campaign ROI & ROAS definitions & ranking integrity
        if data.campaigns:
            metrics["campaign_count"] = len(data.campaigns)
            for c in data.campaigns[:10]:
                spend = c.get("spend", 0.0)
                attr_rev = c.get("revenue", 0.0)
                roas = c.get("roas", 0.0)

                if spend > 0 and attr_rev > 0 and roas <= 0.0:
                    issues.append(f"Campaign '{c.get('campaign_name')}' has spend and revenue but ROAS is 0")

            # Check that campaigns_by_roas is strictly sorted
            if hasattr(data, "campaigns_by_roas") and data.campaigns_by_roas:
                for i in range(len(data.campaigns_by_roas) - 1):
                    if data.campaigns_by_roas[i]["roas"] < data.campaigns_by_roas[i + 1]["roas"]:
                        issues.append("campaigns_by_roas is not properly sorted in descending order.")
                        break

            # Check that campaigns_by_revenue is strictly sorted
            if hasattr(data, "campaigns_by_revenue") and data.campaigns_by_revenue:
                for i in range(len(data.campaigns_by_revenue) - 1):
                    if data.campaigns_by_revenue[i]["revenue"] < data.campaigns_by_revenue[i + 1]["revenue"]:
                        issues.append("campaigns_by_revenue is not properly sorted in descending order.")
                        break

            # Check that channel_summary is present and accurately calculated
            if hasattr(data, "channel_summary") and data.channel_summary:
                metrics["channel_count"] = len(data.channel_summary)
                for ch in data.channel_summary:
                    sp = ch.get("total_spend", 0.0)
                    rv = ch.get("total_revenue", 0.0)
                    if sp > 0 and rv > 0:
                        expected_roas = rv / sp
                        if abs(ch.get("roas", 0.0) - expected_roas) > 0.05:
                            issues.append(f"Channel '{ch.get('channel')}' has inaccurate channel ROAS calculation.")

        # 5. Customer counts & LTV
        if data.customer_tiers:
            metrics["tiers_count"] = len(data.customer_tiers)
            total_tier_cust = sum(t.get("customer_count", 0) for t in data.customer_tiers)
            if total_tier_cust <= 0:
                issues.append("Total customer count across loyalty tiers is zero")

        is_valid = len(issues) == 0
        return ReportQAResult(is_valid=is_valid, issues=issues, metrics_audited=metrics)

    def validate_insights(
        self,
        data: ValidatedReportingData,
        findings: List[str],
        recommendations: List[str],
    ) -> ReportQAResult:
        """Audit findings, terminology, attribution claims, and recommendations for epistemic rigor."""
        from backend.app.reporting.insight_validator import InsightValidator

        issues: List[str] = []
        metrics: Dict[str, Any] = {
            "findings_count": len(findings),
            "recommendations_count": len(recommendations),
        }

        # Validate findings
        for idx, f in enumerate(findings):
            # Epistemic structure
            valid_structure, struct_issues = InsightValidator.validate_epistemic_structure(f)
            issues.extend([f"Finding {idx+1}: {iss}" for iss in struct_issues])

            # Financial terminology & attribution claims
            valid_terms, term_issues = InsightValidator.validate_terminology(f)
            issues.extend([f"Finding {idx+1}: {iss}" for iss in term_issues])

            # Campaign rankings
            if data.campaigns:
                valid_rank, rank_issues = InsightValidator.validate_campaign_rankings(data.campaigns, f)
                issues.extend([f"Finding {idx+1}: {iss}" for iss in rank_issues])

            # Contradiction detection
            valid_contr, contr_issues = InsightValidator.validate_contradictions(f, data)
            issues.extend([f"Finding {idx+1}: {iss}" for iss in contr_issues])

        # Validate recommendations
        for idx, r in enumerate(recommendations):
            valid_rec, rec_issues = InsightValidator.validate_recommendation_structure(r)
            issues.extend([f"Recommendation {idx+1}: {iss}" for iss in rec_issues])

            valid_terms, term_issues = InsightValidator.validate_terminology(r)
            issues.extend([f"Recommendation {idx+1}: {iss}" for iss in term_issues])

            valid_contr, contr_issues = InsightValidator.validate_contradictions(r, data)
            issues.extend([f"Recommendation {idx+1}: {iss}" for iss in contr_issues])

        is_valid = len(issues) == 0
        return ReportQAResult(is_valid=is_valid, issues=issues, metrics_audited=metrics)

    def validate_document(
        self,
        doc: ReportDocument,
        data: Optional[ValidatedReportingData] = None,
    ) -> ReportQAResult:
        """Deep QA audit on the compiled ReportDocument model before rendering/exporting."""
        issues: List[str] = []
        metrics: Dict[str, Any] = {
            "tables_count": len(doc.tables),
            "findings_count": len(doc.key_drivers),
            "recommendations_count": len(doc.recommendations),
        }

        # 1. Audit Data Tables
        for tbl in doc.tables:
            title_lower = tbl.title.lower()

            # Verify sorting in ROAS-ranked tables
            if "ranked by roas" in title_lower or "capital efficiency" in title_lower:
                roas_col_idx = None
                for idx, c in enumerate(tbl.columns):
                    if "roas" in c.lower():
                        roas_col_idx = idx
                        break

                if roas_col_idx is not None and len(tbl.rows) > 1:
                    roas_vals: List[float] = []
                    for r_idx, row in enumerate(tbl.rows):
                        raw_val = str(row[roas_col_idx]).replace("x", "").replace(",", "").strip()
                        try:
                            roas_vals.append(float(raw_val))
                        except ValueError:
                            issues.append(f"Table '{tbl.title}' row {r_idx} ROAS '{raw_val}' could not be parsed as float.")

                    for i in range(len(roas_vals) - 1):
                        if roas_vals[i] < roas_vals[i + 1] - 0.01:
                            issues.append(
                                f"Table '{tbl.title}' is not sorted descending by ROAS: {roas_vals[i]} < {roas_vals[i+1]}"
                            )
                            break

            # Verify sorting in Revenue-ranked tables
            if "ranked by attributed revenue" in title_lower or "commercial scale" in title_lower:
                rev_col_idx = None
                for idx, c in enumerate(tbl.columns):
                    if "attributed rev" in c.lower() or "net revenue" in c.lower():
                        rev_col_idx = idx
                        break

                if rev_col_idx is not None and len(tbl.rows) > 1:
                    rev_vals: List[float] = []
                    for r_idx, row in enumerate(tbl.rows):
                        raw_val = str(row[rev_col_idx]).replace("₹", "").replace(",", "").strip()
                        try:
                            rev_vals.append(float(raw_val))
                        except ValueError:
                            pass
                    for i in range(len(rev_vals) - 1):
                        if rev_vals[i] < rev_vals[i + 1] - 1.0:
                            issues.append(
                                f"Table '{tbl.title}' is not sorted descending by Revenue: {rev_vals[i]} < {rev_vals[i+1]}"
                            )
                            break

            # Table 1: Category Breakdown Semantics
            if ("revenue contribution by merchandise category" in title_lower or "category breakdown" in title_lower) and "return" not in title_lower:
                cols_str = " ".join(tbl.columns).lower()
                if "orders containing category" not in cols_str and "order reach" not in cols_str:
                    issues.append(
                        f"Table '{tbl.title}' uses ambiguous order column; expected 'Orders Containing Category'."
                    )
                if not getattr(tbl, "footnote", None):
                    issues.append(
                        f"Table '{tbl.title}' missing explanatory footnote detailing multi-category shopping basket reach."
                    )

            # Table 2: Top SKUs Pricing Reconciliation
            if "top performing skus" in title_lower or "pricing reconciliation" in title_lower:
                cols_str = " ".join(tbl.columns).lower()
                for required_col in ["gross list value", "discounts applied", "net billed revenue"]:
                    if required_col not in cols_str:
                        issues.append(
                            f"Table '{tbl.title}' missing required reconciliation column: '{required_col}'."
                        )
                if not getattr(tbl, "footnote", None):
                    issues.append(
                        f"Table '{tbl.title}' missing pricing reconciliation equation footnote."
                    )

        # 2. Audit Narrative Content (Executive Summary, Drivers, Risks, Recommendations)
        all_narrative_texts = [doc.executive_summary] + doc.key_drivers + doc.risk_observations + doc.recommendations
        for text in all_narrative_texts:
            t_lower = text.lower()
            if "3-5% aov" in t_lower or "3–5% aov" in t_lower or "3-5% uplift" in t_lower or "3–5% uplift" in t_lower:
                issues.append("Narrative contains ungrounded projection: '3-5% AOV uplift'.")
            if "over 65%" in t_lower and "electronics and appliances" in t_lower:
                issues.append("Narrative contains outdated category concentration contradiction: 'over 65%'.")
            if "appliances" in t_lower and "electronics and appliances" in t_lower:
                issues.append("Narrative mentions nonexistent 'appliances' category instead of 'Home & Kitchen'.")

        is_valid = len(issues) == 0
        return ReportQAResult(is_valid=is_valid, issues=issues, metrics_audited=metrics)

    def validate_file(
        self,
        content: bytes,
        file_format: ReportFormat,
        expected_kpis: Dict[str, Any] = None,
        doc: Optional[ReportDocument] = None,
    ) -> ReportQAResult:
        """Audit the exported binary/text deliverable for structure, formatting, and reconciliation."""
        issues: List[str] = []
        metrics: Dict[str, Any] = {"file_size_bytes": len(content)}

        if len(content) < 500:
            issues.append(f"File size {len(content)} bytes is suspiciously small.")

        if file_format == ReportFormat.PDF:
            if not content.startswith(b"%PDF-"):
                issues.append("PDF deliverable does not start with standard '%PDF-' magic bytes.")
            if len(content) < 20000:
                issues.append("PDF deliverable size is under 20KB; likely missing layout or charts.")

            try:
                pdf_doc = pymupdf.open(stream=content, filetype="pdf")
                metrics["pdf_pages"] = len(pdf_doc)
                if len(pdf_doc) < 1:
                    issues.append("PDF deliverable has 0 pages.")

                full_text = " ".join(page.get_text() for page in pdf_doc)
                metrics["extracted_text_length"] = len(full_text)

                # Check for forbidden ungrounded projections
                if "3-5% aov" in full_text.lower() or "3–5% aov" in full_text.lower() or "3-5% uplift" in full_text.lower():
                    issues.append("PDF contains ungrounded projection: '3-5% AOV uplift'.")

                # Check for outdated static concentration claims
                if "over 65% of gross revenue is generated by electronics" in full_text.lower():
                    issues.append("PDF contains outdated static category concentration claim (over 65%).")

                # If doc is Executive Performance, verify critical tables and campaign rankings
                if doc and doc.category in (ReportCategory.EXECUTIVE_PERFORMANCE, ReportCategory.BUSINESS_PERFORMANCE):
                    if "Top Marketing Campaigns by Capital Efficiency" not in full_text:
                        issues.append("Executive PDF is missing the Top Marketing Campaigns by Capital Efficiency table.")

                    if "CMP-012" not in full_text:
                        issues.append("Executive PDF is missing top campaign CMP-012.")

                    pos_012 = full_text.find("CMP-012")
                    pos_037 = full_text.find("CMP-037")
                    pos_007 = full_text.find("CMP-007")
                    if pos_012 != -1 and pos_037 != -1 and pos_012 > pos_037:
                        issues.append("Executive PDF has campaign CMP-012 appearing after CMP-037 (incorrect ROAS ranking).")
                    if pos_037 != -1 and pos_007 != -1 and pos_037 > pos_007:
                        issues.append("Executive PDF has campaign CMP-037 appearing after CMP-007 (incorrect ROAS ranking).")

                    if "Orders Containing" not in full_text:
                        issues.append("Executive PDF missing 'Orders Containing Category' table header.")

                    if "Gross List Value" not in full_text:
                        issues.append("Executive PDF Top SKUs table missing 'Gross List Value' column.")

                # If doc is Campaign Performance, verify campaign rankings and claims
                if doc and doc.category in (ReportCategory.CAMPAIGN_PERFORMANCE, ReportCategory.MARKETING_PERFORMANCE):
                    if "CMP-012" not in full_text:
                        issues.append("Campaign PDF is missing top efficiency campaign CMP-012.")
                    pos_012 = full_text.find("CMP-012")
                    pos_037 = full_text.find("CMP-037")
                    if pos_012 != -1 and pos_037 != -1 and pos_012 > pos_037:
                        issues.append("Campaign PDF has CMP-012 appearing after CMP-037 (incorrect ROAS ranking).")
                    if "10-15%" in full_text.lower() or "10–15%" in full_text.lower():
                        issues.append("Campaign PDF contains unsupported budget reallocation projection (10-15%).")

                # If doc is Customer Intelligence, verify customer tiers and claims
                if doc and doc.category == ReportCategory.CUSTOMER_INTELLIGENCE:
                    if "90-day" in full_text.lower():
                        issues.append("Customer Intelligence PDF contains unverified 90-day dormancy claim.")
                    if "repeat-order uplift" in full_text.lower():
                        issues.append("Customer Intelligence PDF contains ungrounded repeat-order uplift claim.")
                    if "Customer Loyalty Tier Stratification" not in full_text:
                        issues.append("Customer Intelligence PDF is missing Customer Loyalty Tier Stratification table.")

                # If doc is Operations & Fulfillment, verify operational metrics
                if doc and doc.category == ReportCategory.OPERATIONS_FULFILLMENT:
                    if "0.0% delivery" in full_text.lower():
                        issues.append("Operations PDF contains invalid 0.0% delivery claim.")
                    if "Carrier Dispatch & Delivery Transit SLA" not in full_text and "Carrier" not in full_text:
                        issues.append("Operations PDF is missing Carrier SLA Performance table.")

                # If doc is Custom Report, verify absence of speculative claims
                if doc and doc.category == ReportCategory.CUSTOM_REPORT:
                    if "infrastructure resilience" in full_text.lower() or "inventory latency" in full_text.lower():
                        issues.append("Custom Business PDF contains unverified infrastructure/system claim.")

            except Exception as e:
                issues.append(f"PyMuPDF failed to parse generated PDF: {str(e)}")

        elif file_format == ReportFormat.XLSX:
            if not content.startswith(b"PK"):
                issues.append("Excel deliverable does not start with standard ZIP magic bytes 'PK'.")
            try:
                wb = openpyxl.load_workbook(io.BytesIO(content))
                sheets = wb.sheetnames
                metrics["worksheets"] = sheets
                if len(sheets) < 3:
                    issues.append(f"Excel workbook has only {len(sheets)} worksheets; expected at least 3.")

                # Reconcile Executive Summary or KPI Scorecard sheet
                if "KPI Scorecard" in sheets:
                    ws_kpi = wb["KPI Scorecard"]
                    if ws_kpi.max_row < 3:
                        issues.append("KPI Scorecard worksheet has fewer than 3 rows.")

                # Verify table headers in sheets
                for sheetname in sheets:
                    ws = wb[sheetname]
                    first_row_vals = [str(cell.value) for cell in ws[1] if cell.value is not None]
                    first_row_str = " ".join(first_row_vals).lower()
                    if "skus" in sheetname.lower() or "pricing reconciliation" in sheetname.lower():
                        if "gross list value" not in first_row_str:
                            issues.append(f"Excel sheet '{sheetname}' missing 'Gross List Value' header.")
            except Exception as e:
                issues.append(f"Excel workbook failed openpyxl parsing: {str(e)}")

        elif file_format == ReportFormat.CSV:
            text = content.decode("utf-8-sig", errors="replace")
            lines = text.strip().splitlines()
            metrics["csv_lines"] = len(lines)
            if len(lines) < 5:
                issues.append(f"CSV deliverable has only {len(lines)} lines.")

        is_valid = len(issues) == 0
        return ReportQAResult(is_valid=is_valid, issues=issues, metrics_audited=metrics)
