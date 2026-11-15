
from typing import Any, Literal
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.app.database_config import load_database_config
from backend.app.api.report_endpoint import build_report_response
from backend.app.orchestration.orchestrator import Orchestrator
from backend.app.orchestration.report_agent import ReportAgent

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


class QuestionRequest(BaseModel):
    question: str
    clarification_context: dict[str, Any] | None = None


class ReportRequest(BaseModel):
    report_type: Literal["business_performance", "sales_analysis", "campaign_performance"]
    format: Literal["pdf", "xlsx"]


class Source(BaseModel):
    type: str
    title: str | None = None
    document_id: str | None = None
    filename: str | None = None
    document_type: str | None = None
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


orchestrator = Orchestrator(**load_database_config())
report_agent = ReportAgent()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "AgentOps AI",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "AgentOps AI",
    }


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
        result = orchestrator.answer(
            request.question,
            clarification_context=request.clarification_context,
        )

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
        logger.exception("Question orchestration failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to process question. Please try again later.",
        ) from exc


@app.post("/reports")
def create_report(request: ReportRequest) -> Response:
    """Generate a report from predefined backend-owned questions and validated results."""
    try:
        return build_report_response(
            report_agent,
            request.report_type,
            request.format,
            orchestrator.answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate the report. Please try again later.",
        ) from exc
