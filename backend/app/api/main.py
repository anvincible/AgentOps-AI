
from typing import Any, Literal
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.app.database_config import load_database_config
from backend.app.api.report_endpoint import build_report_response
from backend.app.api.readiness import check_database_readiness
from backend.app.api.documents_endpoint import router as documents_router
from backend.app.api.data_endpoint import router as data_router
from backend.app.api.dashboard_endpoint import router as dashboard_router
from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.orchestration.report_agent import ReportAgent
from backend.app.safe_logging import log_sanitized_exception

logger = logging.getLogger(__name__)


app = FastAPI(
    title="AgentOps AI",
    description="NovaMart AI Agent API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(data_router)
app.include_router(dashboard_router)


class QuestionRequest(BaseModel):
    question: str
    clarification_context: dict[str, Any] | None = None
    department: str | None = None
    document_id: str | None = None


class ReportRequest(BaseModel):
    report_type: Literal[
        "business_performance",
        "sales_analysis",
        "campaign_performance",
        "executive_performance",
        "sales_performance",
        "customer_intelligence",
        "operations_fulfillment",
        "custom_report",
    ] = "executive_performance"
    format: Literal["pdf", "xlsx", "csv"] = "pdf"
    period: Literal["all_time", "this_year", "last_90_days", "last_30_days", "last_7_days"] = "all_time"
    title: str | None = None
    sections: dict[str, bool] | None = None


class Source(BaseModel):
    type: str
    title: str | None = None
    document_id: str | None = None
    filename: str | None = None
    document_type: str | None = None
    department: str | None = None
    page_number: int | None = None
    paragraph_number: int | None = None
    chunk_id: str | None = None


class QuestionResponse(BaseModel):
    question: str
    route: str
    answer: str
    sources: list[Source]
    verification: dict[str, Any] | None = None
    clarification: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None


database_config = load_database_config()
try:
    orchestrator = Orchestrator(**database_config)
except Exception as exc:
    log_sanitized_exception(
        logger,
        "Application initialization failed",
        exc,
    )
    raise RuntimeError("Application initialization failed.") from None
report_agent = ReportAgent()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "AgentOps AI",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "readiness": "/ready",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "AgentOps AI",
    }


@app.get("/ready")
def ready() -> dict[str, str]:
    return check_database_readiness(database_config)


@app.post("/ask", response_model=QuestionResponse)
def ask_question(
    request: QuestionRequest,
) -> dict[str, Any]:

    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        answer_options: dict[str, Any] = {
            "clarification_context": request.clarification_context,
        }
        if request.department and request.department.strip():
            answer_options["department"] = request.department.strip()
        if request.document_id and request.document_id.strip():
            answer_options["document_id"] = request.document_id.strip()
        result = orchestrator.answer(request.question, **answer_options)

        sources = []

        # SQL source
        if "sql" in result:
            sources.append({
                "type": "sql",
                "title": "NovaMart PostgreSQL database",
            })

        # RAG sources: expose only evidence selected by AnswerComposer.
        if "rag" in result:
            rag_result = result["rag"]
            evidence = rag_result.get("evidence", [])

            selected_evidence = (
                orchestrator.answer_composer.select_relevant_evidence(
                    evidence,
                    result["question"],
                )
            )

            for item in selected_evidence:
                sources.append({
                    "type": "document",
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename"),
                    "title": item.get("title"),
                    "document_type": item.get("document_type"),
                    "department": item.get("department"),
                    "page_number": item.get("page_number"),
                    "paragraph_number": item.get("paragraph_number"),
                    "chunk_id": item.get("chunk_id"),
                })

        return {
            "question": result["question"],
            "route": result["route"],
            "answer": result["answer"],
            "sources": sources or result.get("sources", []),
            "verification": result.get("verification"),
            "clarification": result.get("clarification"),
            "analysis": result.get("analysis"),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log_sanitized_exception(
            logger,
            "Question orchestration failed",
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to process question. Please try again later.",
        ) from None


@app.post("/reports")
@app.post("/api/reports")
def create_report(request: ReportRequest) -> Response:
    """Generate a report from predefined backend-owned questions and validated results."""
    try:
        return build_report_response(
            report_agent=report_agent,
            report_type=request.report_type,
            file_format=request.format,
            answer_question=orchestrator.answer,
            period=request.period,
            custom_sections=request.sections,
            title=request.title,
            use_enterprise=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_sanitized_exception(
            logger,
            "Report generation failed",
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate the report. Please try again later.",
        ) from None
