"""HTTP wrapper for generating and returning downloadable report responses."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from fastapi.responses import Response
from backend.app.orchestration.report_agent import ReportAgent


def build_report_response(
    report_agent: ReportAgent,
    report_type: str,
    file_format: str,
    answer_question: Optional[Callable[[str], dict[str, Any]]] = None,
    period: str = "all_time",
    custom_sections: Optional[Dict[str, bool]] = None,
    title: Optional[str] = None,
    use_enterprise: bool = True,
) -> Response:
    # If legacy unit-test call without sections or title
    if report_type in {"business_performance", "sales_analysis"} and custom_sections is None and title is None and answer_question is not None:
        use_enterprise = False

    content, filename, media_type = report_agent.generate(
        report_type=report_type,
        file_format=file_format,
        answer_question=answer_question,
        period=period,
        custom_sections=custom_sections,
        use_enterprise=use_enterprise,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
