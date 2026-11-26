# AgentOps AI — NovaMart Intelligent Business Assistant

An intelligent business assistant that lets users ask natural-language questions about a fictional e-commerce and marketing business, **NovaMart**. It combines structured business data stored in PostgreSQL with business documents indexed using embeddings, then routes each question to SQL analytics, Retrieval-Augmented Generation (RAG), or a hybrid workflow.

> **Dataset disclaimer:** NovaMart's datasets and business documents are synthetic and are used for demonstration and academic purposes.

## Overview

AgentOps AI is designed to make business information easier to explore without manually querying databases or searching through documents. The application uses a deterministic orchestration and answer-composition workflow to return readable answers supported by structured query results and/or retrieved document evidence.

### Key capabilities

- **Natural-language business queries** through an Angular chat interface.
- **SQL analytics** using supported, deterministic query templates over business tables.
- **RAG-based document search** with semantic retrieval from ingested business documents.
- **Hybrid answers** that combine structured metrics with relevant document evidence.
- **Evidence verification** that checks answer support against SQL results and retrieved excerpts.
- **Clarification and unsupported-query handling** for questions outside the supported templates.
- **Markdown-formatted responses** in the chat UI, with HTML escaping before Markdown conversion.
- **API health and interactive documentation** through FastAPI.

## Architecture

```text
                         Angular Frontend
                                |
                         POST /ask (Proxy)
                                |
                           FastAPI API
                                |
                          Orchestrator
                     /          |          \
                   SQL         RAG         BOTH
                    |           |            |
             PostgreSQL   Document Search    |
                    |      + Embeddings      |
                    |      + pgvector        |
                    \___________|____________/
                                |
                      Answer Composer
                                |
                     Verification Agent
                                |
                       JSON API Response
                                |
                         Angular Chat UI
```

### Routing modes

| Route | Purpose |
|---|---|
| `SQL` | Answer supported business analytics questions using database query results. |
| `RAG` | Answer document-focused questions using retrieved evidence. |
| `BOTH` | Combine structured data and relevant document evidence. |
| `CHAT` | Handle casual greetings and conversational messages. |

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Angular 22, TypeScript |
| Backend | Python, FastAPI, Uvicorn |
| Database | PostgreSQL 18 |
| Vector search | pgvector 0.8.6 |
| Embeddings | Sentence Transformers — `all-MiniLM-L6-v2` (384 dimensions) |
| Database access | Psycopg 3 |
| Validation | Pydantic, SQL validation |
| Testing | Pytest, focused regression suites |
| API documentation | FastAPI Swagger UI (`/docs`) |

## Data and Knowledge Base

The current database contains **12 business tables** loaded with synthetic NovaMart data:

| Table | Approximate Records |
|---|---:|
| Customers | 10,000 |
| Leads | 15,000 |
| Marketing campaigns | 50 |
| Marketing events | 50,000 |
| Order items | 125,202 |
| Orders | 50,000 |
| Payments | 50,000 |
| Products | 2,000 |
| Returns | 3,585 |
| Sellers | 500 |
| Shipments | 50,000 |
| Support tickets | 9,970 |

The document knowledge base currently contains **36 processed documents and 204 document chunks**. Text is embedded with `all-MiniLM-L6-v2` and stored in PostgreSQL using pgvector.

## Supported Business Analytics

The deterministic SQL templates cover supported query patterns across:

- Customer counts, distributions, segments, locations, loyalty tiers, status, and acquisition channels
- Customer lifetime-value summaries and segment comparisons
- Product rankings, categories, brands, inventory, low-stock items, prices, and ratings
- Sales totals, average order value, monthly/region/category/product/channel summaries, and order statuses
- Seller counts and performance
- Marketing campaign rankings, ROI, comparisons, and event-channel metrics
- Support-ticket breakdowns
- Payment and shipment breakdowns
- Return counts and return-rate calculations

The SQL reasoner is **template-based, not a general natural-language-to-SQL system**. Free-form SQL, arbitrary compound filters, and unsupported analytics are not available.

## Example Questions

### SQL analytics
- What were the results of campaign CMP-021?
- What is the return rate?
- Which products have the highest sales?
- How are customers distributed across segments?

### Document/RAG
- What is NovaMart's return and refund policy?
- What does the campaign strategy document recommend?

### Hybrid
- What were the results of campaign CMP-021 and what strategy was recommended?

> The examples above demonstrate the supported workflows. Document-dependent responses should be verified against the documents available in the local setup.

## Evidence and Verification

The deterministic `VerificationAgent` checks whether:

- SQL claims can be reproduced from the returned query rows.
- RAG claims and citations align with the selected document excerpts.
- Hybrid responses use both structured data and document evidence.

This is a focused evidence check—not a general-purpose fact checker. The current implementation does not include an automatic retry/fallback loop.

## Project Structure

```text
AgentOps-AI/
├── backend/
│   └── app/
│       ├── api/                 # FastAPI endpoints
│       ├── orchestration/       # Routing and answer composition
│       ├── rag/                # Document ingestion, embedding, retrieval
│       ├── sql/                 # SQL agent and supported query templates
│       └── llm/                 # Optional LLM client (not active in answer path)
├── frontend-angular/            # Active Angular frontend
├── frontend/                    # Unused Vite template
├── data/                         # Synthetic data and documents
├── docs/                         # Project documentation
├── scripts/                       # Setup, ingestion, and testing scripts
├── tests/                          # Regression tests
├── evaluation/                     # Evaluation resources
└── agentops_requirements.txt       # Python dependencies
```

## Getting Started

### Prerequisites

- Windows 10/11 (the documented setup is Windows-oriented)
- Python 3.12
- PostgreSQL 18 with pgvector installed
- Node.js and npm
- Git

> Versions listed here reflect the development environment used during project testing. Other compatible versions may require adjustments.

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd AgentOps-AI
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with the repository URL.

### 2. Install Python dependencies

From the project root:

```powershell
python -m pip install -r .\agentops_requirements.txt
```

If using the existing backend virtual environment:

```powershell
.\backend\venv\Scripts\Activate.ps1
```

### 3. Configure PostgreSQL and pgvector

1. Install and start PostgreSQL.
2. Install a pgvector extension compatible with your PostgreSQL version.
3. Create the `novamart` database.
4. Load the project schema and synthetic dataset using the SQL/scripts included in the repository.
5. Run the document-ingestion script to populate `document_chunks`.
6. Verify database connection settings before launching the backend.

The exact data-loading commands depend on the scripts and SQL files included in the repository. Check the relevant setup scripts before running them.

### 4. Configure environment variables

Review `.env.example` and create a local `.env` file if required by the project. Keep database credentials and other secrets out of GitHub.

**Never commit real passwords, API keys, tokens, or private database dumps.**

### 5. Start the backend

From the repository root, run:

```powershell
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

Backend URLs:

- API root: `http://127.0.0.1:8000/`
- Health check: `http://127.0.0.1:8000/health`
- Swagger documentation: `http://127.0.0.1:8000/docs`

### 6. Start the Angular frontend

Open another terminal:

```powershell
cd .\frontend-angular
npm install
npm start
```

The Angular development server uses `proxy.conf.json` to proxy API requests to the FastAPI backend. The active frontend is `frontend-angular/`; the root `frontend/` directory is an unused Vite template.

## API

### `POST /ask`

Request:

```json
{
  "question": "What were the results of campaign CMP-021?"
}
```

The response includes:

- `question`
- `route` (`SQL`, `RAG`, `BOTH`, or conversational `CHAT` handling)
- `answer`
- `sources`

Other available endpoints include `GET /` and `GET /health`. Interactive API documentation is available at `/docs`.

## Testing and Validation

The project has focused regression tests and SQL workflow tests. The current local audit reported successful checks for supported SQL workflows, RAG retrieval/evidence handling, orchestration routes, FastAPI endpoints, Angular integration through the development proxy, and frontend build/component tests.

Useful commands from the project root:

```powershell
# SQL agent tests
python -m scripts.test_sql_agent
python -m scripts.test_sql_agent_cases
python -m scripts.test_sql_pipeline

# Backend API
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000

# Frontend
cd .\frontend-angular
npm install
npm start
```

For the full Python test suite, use the Python environment configured for the project and run:

```powershell
python -m pytest
```

## Current Implementation Status

| Component | Status |
|---|---|
| Project foundation and environment | Complete |
| Synthetic dataset and documents | Complete |
| PostgreSQL and pgvector setup | Complete in the current development environment |
| Document ingestion and RAG pipeline | Implemented and tested |
| SQL analytics | Supported deterministic templates implemented |
| FastAPI API layer | Implemented and tested locally |
| Angular chat frontend and API integration | Implemented; local build and tests reported passing |
| Orchestration and answer composition | Implemented |
| Evidence verification | Implemented as deterministic checks |
| Business analysis/report generation module | Not implemented |
| General evaluation benchmark runner | Not implemented; focused regression/evaluation checks exist |
| Authentication and audit logging | Not implemented |
| Production deployment/hardening | Not completed |
| Overview, Agent Execution, Data Explorer, Knowledge & Evidence, Evaluation & Verification modules | Deferred/planned; currently show planned-module pages |

## Important Limitations

- **No live LLM answer generation:** answers are composed deterministically from SQL results and retrieved evidence. An optional `LLMClient` exists but is not wired into the orchestrator.
- **SQL is template-based:** only defined query patterns are supported; it is not arbitrary natural-language-to-SQL.
- **Verification is focused:** it checks evidence consistency but is not a general fact checker and does not have an automatic retry loop.
- **Some UI modules are deferred:** only the Angular Assistant workflow is implemented as an active module.
- **PrimeUI licensing decision pending:** the current PrimeNG 22 setup requires a licensing decision and an authorized key, if applicable, before final configuration.
- **Not production-hardened:** authentication, audit logging, deployment configuration, and further security hardening remain future work.

## Academic Project Context

AgentOps AI is developed as a college group project. The repository handoff records the sequence **Ashna → Anvi → Aru**. Earlier contribution details should be confirmed by the group; this README does not make individual contribution claims beyond that handoff note.

## Future Scope

- Extend SQL analytics with more supported query patterns.
- Implement or remove deferred dashboard and agent-observability modules based on scope.
- Add business analysis and report generation if required.
- Expand evaluation coverage and benchmark metrics.
- Add authentication, audit logging, and production security hardening.
- Evaluate and integrate live LLM answer generation if appropriate.
- Deploy the application for broader access.

## Team

**AgentOps AI — NovaMart Intelligent Business Assistant**

College group project. Please refer to the repository history and project documentation for contribution details.

