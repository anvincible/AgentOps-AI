"""Report Data Models and Configuration Schemas for AgentOps AI Reporting System."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class ReportCategory(str, Enum):
    EXECUTIVE_PERFORMANCE = "executive_performance"
    BUSINESS_PERFORMANCE = "business_performance"  # legacy alias
    SALES_PERFORMANCE = "sales_performance"
    SALES_ANALYSIS = "sales_analysis"  # legacy alias
    CAMPAIGN_PERFORMANCE = "campaign_performance"
    MARKETING_PERFORMANCE = "marketing_performance"  # alias
    CUSTOMER_INTELLIGENCE = "customer_intelligence"
    OPERATIONS_FULFILLMENT = "operations_fulfillment"
    CUSTOM_REPORT = "custom_report"

    @classmethod
    def normalize(cls, val: Any) -> "ReportCategory":
        if isinstance(val, cls):
            return val
        s = str(val).lower() if val else "executive_performance"
        mapping = {
            "business_performance": cls.EXECUTIVE_PERFORMANCE,
            "executive_performance": cls.EXECUTIVE_PERFORMANCE,
            "sales_analysis": cls.SALES_PERFORMANCE,
            "sales_performance": cls.SALES_PERFORMANCE,
            "campaign_performance": cls.CAMPAIGN_PERFORMANCE,
            "marketing_performance": cls.CAMPAIGN_PERFORMANCE,
            "customer_intelligence": cls.CUSTOMER_INTELLIGENCE,
            "operations_fulfillment": cls.OPERATIONS_FULFILLMENT,
            "custom_report": cls.CUSTOM_REPORT,
        }
        return mapping.get(s, cls.EXECUTIVE_PERFORMANCE)

    @property
    def display_title(self) -> str:
        titles = {
            self.EXECUTIVE_PERFORMANCE: "Executive Business Performance Report",
            self.BUSINESS_PERFORMANCE: "Executive Business Performance Report",
            self.SALES_PERFORMANCE: "Sales Performance & Product Analytics Report",
            self.SALES_ANALYSIS: "Sales Performance & Product Analytics Report",
            self.CAMPAIGN_PERFORMANCE: "Marketing & Campaign ROI Performance Report",
            self.MARKETING_PERFORMANCE: "Marketing & Campaign ROI Performance Report",
            self.CUSTOMER_INTELLIGENCE: "Customer Intelligence & Cohort Analysis Report",
            self.OPERATIONS_FULFILLMENT: "Operations, Logistics & Fulfillment Health Report",
            self.CUSTOM_REPORT: "Custom Business Intelligence Report",
        }
        return titles.get(self, "NovaMart Business Intelligence Report")


class ReportFormat(str, Enum):
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"


class ReportPeriod(str, Enum):
    ALL_TIME = "all_time"
    THIS_YEAR = "this_year"
    LAST_90_DAYS = "last_90_days"
    LAST_30_DAYS = "last_30_days"
    LAST_7_DAYS = "last_7_days"


class ReportSectionConfig(BaseModel):
    executive_summary: bool = True
    include_executive_summary: bool = True
    kpi_overview: bool = True
    include_kpi_summary: bool = True
    charts: bool = True
    include_charts: bool = True
    data_tables: bool = True
    include_detailed_tables: bool = True
    business_insights: bool = True
    recommendations: bool = True
    include_recommendations: bool = True
    methodology_sources: bool = True
    include_sources: bool = True

    @model_validator(mode="before")
    @classmethod
    def sync_toggles(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync alias toggles
            if "include_charts" in data:
                data["charts"] = data["include_charts"]
            elif "charts" in data:
                data["include_charts"] = data["charts"]

            if "include_kpi_summary" in data:
                data["kpi_overview"] = data["include_kpi_summary"]
            elif "kpi_overview" in data:
                data["include_kpi_summary"] = data["kpi_overview"]

            if "include_detailed_tables" in data:
                data["data_tables"] = data["include_detailed_tables"]
            elif "data_tables" in data:
                data["include_detailed_tables"] = data["data_tables"]

            if "include_recommendations" in data:
                data["recommendations"] = data["include_recommendations"]
            elif "recommendations" in data:
                data["include_recommendations"] = data["recommendations"]

            if "include_sources" in data:
                data["methodology_sources"] = data["include_sources"]
            elif "methodology_sources" in data:
                data["include_sources"] = data["methodology_sources"]
        return data


class ReportRequestModel(BaseModel):
    report_type: Optional[str] = None
    category: Optional[ReportCategory] = None
    format: Any = ReportFormat.PDF
    period: Any = ReportPeriod.ALL_TIME
    title: Optional[str] = None
    sections: ReportSectionConfig = Field(default_factory=ReportSectionConfig)
    metrics: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def validate_request(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If category given but not report_type
            if "category" in data and "report_type" not in data:
                cat = data["category"]
                data["report_type"] = cat.value if hasattr(cat, "value") else str(cat)
            elif "report_type" in data and "category" not in data:
                data["category"] = ReportCategory.normalize(data["report_type"])

            if not data.get("report_type") and not data.get("category"):
                data["report_type"] = "executive_performance"
                data["category"] = ReportCategory.EXECUTIVE_PERFORMANCE

            # Normalize format
            fmt = data.get("format", "pdf")
            if isinstance(fmt, ReportFormat):
                data["format"] = fmt
            else:
                try:
                    data["format"] = ReportFormat(str(fmt).lower())
                except ValueError:
                    data["format"] = ReportFormat.PDF

            # Normalize period
            per = data.get("period", "all_time")
            if isinstance(per, ReportPeriod):
                data["period"] = per
            else:
                try:
                    data["period"] = ReportPeriod(str(per).lower())
                except ValueError:
                    data["period"] = ReportPeriod.ALL_TIME
        return data


class ReportKpiItem(BaseModel):
    label: str = ""
    name: str = ""
    value: Any = ""
    formatted_value: str = ""
    subtitle: Optional[str] = None
    change: Optional[str] = None
    change_pct: Optional[float] = None
    target: Optional[str] = None
    status: str = "normal"

    @model_validator(mode="before")
    @classmethod
    def sync_kpi(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "label" in data and "name" not in data:
                data["name"] = data["label"]
            elif "name" in data and "label" not in data:
                data["label"] = data["name"]

            if "value" in data and "formatted_value" not in data:
                data["formatted_value"] = str(data["value"])
            elif "formatted_value" in data and "value" not in data:
                data["value"] = data["formatted_value"]

            if "subtitle" in data and "target" not in data:
                data["target"] = data["subtitle"]
            elif "target" in data and "subtitle" not in data:
                data["subtitle"] = data["target"]

            if "change" in data and "change_pct" not in data:
                try:
                    cleaned = str(data["change"]).replace("%", "").replace("+", "").strip()
                    data["change_pct"] = float(cleaned)
                except Exception:
                    pass
        return data


class ReportTable(BaseModel):
    title: str = "Data Table"
    subtitle: Optional[str] = None
    footnote: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    headers: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    total_row: Optional[List[Any]] = None
    alignment: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_cols(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "columns" in data and "headers" not in data:
                data["headers"] = data["columns"]
            elif "headers" in data and "columns" not in data:
                data["columns"] = data["headers"]
        return data


class ReportChartItem(BaseModel):
    chart_id: str = "chart-1"
    title: str = "Chart Visualization"
    image_bytes: bytes = b""
    caption: Optional[str] = None
    width_inches: float = 6.5
    height_inches: float = 3.2


class ReportSourceItem(BaseModel):
    source_type: str = "database"
    reference: str = ""
    status: str = "validated"
    details: Optional[str] = None
    document_name: str = ""
    title: Optional[str] = None
    excerpt: str = ""
    confidence_score: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def sync_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "document_name" in data and not data.get("reference"):
                data["reference"] = data["document_name"]
            elif "reference" in data and not data.get("document_name"):
                data["document_name"] = data["reference"]

            if "excerpt" in data and not data.get("details"):
                data["details"] = data["excerpt"]
            elif "details" in data and not data.get("excerpt"):
                data["excerpt"] = data["details"]
        return data


class ReportDocument(BaseModel):
    request: Optional[ReportRequestModel] = None
    category: ReportCategory = ReportCategory.EXECUTIVE_PERFORMANCE
    period: ReportPeriod = ReportPeriod.ALL_TIME
    title: str = "NovaMart Business Intelligence Report"
    period_label: str = "All Time"
    period_start: str = ""
    period_end: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "AgentOps AI · NovaMart Intelligence"
    classification: str = "CONFIDENTIAL · EXECUTIVE MANAGEMENT DELIVERABLE"
    executive_summary: Any = ""
    kpi_cards: List[ReportKpiItem] = Field(default_factory=list)
    kpis: List[ReportKpiItem] = Field(default_factory=list)
    charts: List[ReportChartItem] = Field(default_factory=list)
    tables: List[ReportTable] = Field(default_factory=list)
    key_drivers: List[str] = Field(default_factory=list)
    risk_observations: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    methodology: str = ""
    sources: List[ReportSourceItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    raw_metrics: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_doc(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "kpi_cards" in data and not data.get("kpis"):
                data["kpis"] = data["kpi_cards"]
            elif "kpis" in data and not data.get("kpi_cards"):
                data["kpi_cards"] = data["kpis"]

            if "key_drivers" in data and not data.get("observations"):
                data["observations"] = data["key_drivers"]
            elif "observations" in data and not data.get("key_drivers"):
                data["key_drivers"] = data["observations"]

            if isinstance(data.get("executive_summary"), list):
                data["executive_summary"] = " ".join(data["executive_summary"])
        return data
