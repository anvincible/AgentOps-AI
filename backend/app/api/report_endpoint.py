"""Small, testable HTTP wrapper for an in-memory report artifact."""

from typing import Any, Callable

from fastapi.responses import Response

from backend.app.orchestration.report_agent import ReportAgent


def build_report_response(
    report_agent: ReportAgent,
    report_type: str,
    file_format: str,
    answer_question: Callable[[str], dict[str, Any]],
) -> Response:
    content, filename, media_type = report_agent.generate(
        report_type, file_format, answer_question
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
