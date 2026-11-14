# AgentOps AI — NovaMart Intelligent Business Assistant

**Project handoff:** Aashna → Anvi → Aru  
**Current status:** Core database, RAG, SQL routing/orchestration, API, and a working Angular frontend are implemented. Frontend polish, verification, evaluation, security hardening, and final delivery remain.

AgentOps AI is a college group project that answers natural-language questions about a fictional e-commerce and marketing business, NovaMart. It uses structured data in PostgreSQL and business documents indexed with embeddings in PostgreSQL/pgvector. A FastAPI backend routes questions to SQL, RAG, or both, then returns an answer to an Angular frontend.

> **Dataset note:** NovaMart data and documents are synthetic and should be presented as such.

## 1. Handoff summary

### Work completed before Anvi's frontend work
The project repository already contained the project structure, synthetic dataset/documents, database/schema scripts, SQL workflow, and RAG components. The precise split of earlier contributions should be confirmed by the group; this README does not assign individual ownership beyond the handoff note above.

### Implemented and tested in the current environment
- PostgreSQL database `novamart` loaded with 12 business tables.
- Tables reported loaded: customers (10,000), leads (15,000), marketing_campaigns (50), marketing_events (50,000), order_items (125,202), orders (50,000), payments (50,000), products (2,000), returns (3,585), sellers (500), shipments (50,000), support_tickets (9,970).
- `document_chunks` table created with a `vector(384)` embedding column.
- pgvector server extension installed; current environment reports extension version **0.8.6**.
- Document ingestion completed: 36 documents processed, **204 chunks** inserted.
- SQL test scripts passed for the supported campaign workflow.
- RAG retrieval and the deterministic answer composer work without requiring a live LLM response.
- Orchestration supports `SQL`, `RAG`, `BOTH`, and `CHAT` (greeting) routing.
- FastAPI endpoints work, including `GET /health` and `POST /ask`.
- **Angular** frontend connects to FastAPI through the Angular dev-server proxy (`proxy.conf.json`).
- Document embeddings use the Sentence Transformers model `all-MiniLM-L6-v2` (384 dimensions, stored in pgvector). No paid embedding API is used.
- A deterministic `VerificationAgent` checks that each answer is backed by SQL rows or retrieved document evidence.
- Regression tests live in `tests/` (`pytest`); run with `backend\venv\Scripts\python.exe -m pytest` on the current machine.
- Assistant responses render Markdown with HTML escaping applied before Markdown conversion.
- End-to-end SQL and hybrid campaign examples have been demonstrated.

### Answer generation is deterministic
Answers are composed by `AnswerComposer`, a deterministic formatter that turns SQL result rows and retrieved RAG evidence into readable text. There is **no live LLM in the answer path**. The `LLMClient` class exists in `backend/app/llm/llm_client.py` but is not invoked by the orchestrator; it requires an OpenAI API key and account credits that are not configured. Do not promise live LLM-generated answers.

### Important limitations to know
- The SQL reasoner uses deterministic templates for campaign and return analytics, customer counts, and product sales rankings. It is not a general natural-language-to-SQL system. A generic question such as "How many orders were placed?" remains unsupported.
- **Answer generation is deterministic.** No live LLM is used. The `LLMClient` class is present but not wired into the orchestrator.
- The answer composer is deterministic and formats the current SQL/RAG results; it is not a replacement for a planned verification agent.
- RAG evidence has sometimes included extracted metadata in displayed content. Clean and retest this before the final demo.
- Casual greetings such as "hi" are handled by a dedicated `CHAT` route.
- Confirm that the current repository's `.env` and configuration are safe before sharing. **Never send real secrets, API keys, or passwords in the handoff.**

## 2. Architecture

```text
Angular frontend (frontend-angular/)
        |
        | POST /ask
        v
FastAPI backend
        |
        v
Orchestrator
   |      |      |
  SQL    RAG    BOTH
   |      |      |
PostgreSQL + pgvector
   \      |      /
    Answer Composer
          |
      JSON response
          |
       Frontend
```

### Main code locations

```text
backend/
  app/
    api/
      main.py                    # FastAPI endpoints and CORS
    orchestration/
      orchestrator.py            # SQL/RAG/BOTH routing
      answer_composer.py         # User-readable deterministic answers
    rag/
      document_loader.py
      document_cleaner.py
      chunker.py
      embedder.py
      vector_store.py
      retriever.py
      rag_agent.py
    sql/                          # SQL agent/reasoner modules
    llm/
      llm_client.py               # Optional live LLM client
frontend-angular/                 # Active Angular chat UI
frontend/                         # Unused Vite template (ignore)
scripts/
tests/
evaluation/
data/
docs/
agentops_requirements.txt
```

Actual filenames may vary slightly in the checked-out repository; inspect the folders before editing.

## 3. Environment requirements

Known working versions in the current development environment:
- Windows 10/11
- Python 3.12.4 (existing virtual environment at `backend/venv`; Python 3.12 is also the version noted in `agentops_requirements.txt`)
- PostgreSQL **18.6** with pgvector extension **0.8.6**
- sentence-transformers 6.1.0 (model `all-MiniLM-L6-v2`), torch 2.14.1
- psycopg 3.3.6, pydantic 2.14.3, torch 2.15.0
- Node.js 24.18.0
- npm 11.16.0
- FastAPI 0.141.1
- Uvicorn 0.53.0
- **Angular ^22.2.0** with TypeScript ~6.0.2 (the active UI in `frontend-angular/`)
- Markdown rendered by a custom safe-HTML formatter in `app.ts`

The versions above describe the environment where the workflow was exercised, not a guarantee that every other machine has the same setup.

## 4. Setup on a new Windows machine

### A. Get the project
Clone the group's repository or copy the complete `AgentOps-AI` folder from the current owner. Do not copy `node_modules`; npm can recreate it. Do not share a real `.env` file in public or group channels.

Open PowerShell in the repository root:

```powershell
cd E:\Downloads\AgentOps-AI
```

Use the actual path where Aru stores the project if it differs.

### B. Set up Python dependencies

```powershell
python --version
python -m pip install -r .\agentops_requirements.txt
```

On the current machine, use the existing environment at `backend\venv`:

```powershell
.\backend\venv\Scripts\Activate.ps1
```

The repository-root `.venv` is a stale copy whose configuration points to a missing Python 3.14 installation. Leave it untouched and use `backend\venv` instead. If dependencies fail, record the exact error rather than upgrading Python or packages at random.

### C. Install/check PostgreSQL and pgvector
The backend expects a PostgreSQL server and a database named `novamart`. On a fresh machine:
1. Install/start PostgreSQL.
2. Install the pgvector server extension compatible with that PostgreSQL installation.
3. Create the `novamart` database.
4. Load the project's schema and synthetic data using the repository's documented SQL/scripts.
5. Run the document ingestion script so `document_chunks` contains the current **204** chunks.
6. Confirm database connection settings before starting the API.

The exact schema/import command depends on the SQL/data files present in the repository. Inspect `README.md`, `scripts/`, and `data/`; do not assume the database is populated just because the code imports successfully.

### D. Configure environment variables
Review `.env.example` and create a local `.env` as needed. Keep credentials local. Database settings are loaded from `.env` by `backend/app/database_config.py` and passed to the SQL and RAG agents.

**There is no live LLM in the answer path.** The `LLMClient` class in `backend/app/llm/llm_client.py` is optional infrastructure and is not invoked by the orchestrator. It requires an OpenAI API key and account credits that are not configured. Do not promise live LLM-generated answers.

### E. Start the backend
From the repository root, in PowerShell terminal 1:

```powershell
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal open.

Check:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

### F. Start the frontend
In PowerShell terminal 2:

```powershell
cd .\frontend-angular
npm install
npm start
```

The active frontend is the **Angular** application in `frontend-angular/`. The `frontend/` directory in the repository root is an unused Vite template and should be ignored.

The dev server (`npm start`, i.e. `ng serve`) proxies `/api` to `http://127.0.0.1:8000` via `proxy.conf.json`. The backend CORS configuration allows `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:4200`, and `http://127.0.0.1:4200`. If the Angular dev server chooses a different port, update the allowed origins in `backend/app/api/main.py`.

## 5. Demo questions that are known to work

### SQL-only
Ask:
> What were the results of campaign CMP-021?

Expected route: `SQL`

Expected values:
- Campaign: CMP-021
- Name: NovaMart Growth Campaign 21
- Spend: 1,840,000.00
- Revenue: 5,270,000.00
- Conversions: 3,812
- Clicks: 47,919

### RAG-only
Ask:
> What is NovaMart return and refund policy?

Expected route: `RAG`

This depends on the ingested documents and should be verified on the receiving machine.

### Hybrid
Ask:
> What were the results of campaign CMP-021 and what strategy was recommended?

Expected route: `BOTH`

Expected to combine campaign metrics with relevant `Campaign Postmortem Cmp-021` and `Campaign Strategy` evidence. A retrieved excerpt was truncated, so do not present its missing ending as known fact.

### Return metrics
Ask:
> What is the return rate?

Expected route: `SQL`. Returns the total return count, total order count, and the computed return rate percentage.

## 5b. Current structured SQL scope

Implemented deterministic questions include campaign metrics and comparisons, return counts/rates/reasons/status/resolutions/trends, total customer count, top 10 products by units sold, and top 10 products by item revenue. Product rankings join `products` to `order_items` by `product_id`; category-guide document counts are not used as sales data. The customer and product templates were added in the current development milestone and still need to be exercised against the application after restarting the backend.

Questions that are NOT supported:

The SQL reasoner supports only defined query patterns. It is not an arbitrary business-SQL generator. Generated SQL is always checked by `SQLValidator` (SELECT-only, single statement, real tables and columns; derived aliases such as `return_count` are accepted). Examples that fail gracefully (with a clear unsupported-query message) include:

- "How many orders were placed?" — generic order aggregation
- "Which customer segment generated the most revenue?" — cross-table aggregation
- "Which regions had the highest sales?" — aggregation outside the supported scope

Do not demo these as supported SQL questions.

## 6. API contract

Request:

```json
{
  "question": "What were the results of campaign CMP-021?"
}
```

Endpoint: `POST http://127.0.0.1:8000/ask`

The response model contains:
- `question`
- `route` (`SQL`, `RAG`, or `BOTH`)
- `answer`
- `sources`

The API also exposes `GET /` and `GET /health`. Swagger UI is available at `/docs`.

## 7. Twelve-phase roadmap and handoff status

This is the current working roadmap used for the handoff. The original master specification describes a 13-step implementation order; the team roadmap groups some implementation tasks together into 12 phases.

| Phase | Scope | Status |
|---|---|---|
| 1 | Environment and project foundation | Complete |
| 2 | Synthetic dataset and documents | Complete |
| 3 | PostgreSQL and pgvector setup | Complete in Anvi's environment; repeat/verify on a new machine |
| 4 | RAG pipeline | Implemented and ingestion tested |
| 5 | SQL agent, orchestration, and answer composition | Implemented with campaign and return analytics, plus customer counts and top product rankings by units or revenue; broader analytics remain |
| 6 | FastAPI API layer | Implemented and tested |
| 7 | Angular frontend and API integration | Implemented (Angular dev build); Angular unit tests and production build were not re-run for this update |
| 8 | Verification/quality-control agent | Implemented as a deterministic evidence check (`verification_agent.py`); no retry/fallback loop |
| 9 | Business analysis and report generation | Not implemented |
| 10 | Evaluation framework and metrics | Partial: `pytest` suite (unit + live PostgreSQL integration); `evaluation/` not re-verified |
| 11 | Security, audit logging, and production hardening | Partial: SELECT-only SQL validation; no audit logging, auth or row limits documented |
| 12 | End-to-end regression tests, documentation, and final demo/deployment | In progress |

Do not mark a phase complete solely because its folder exists. Run its tests and record the evidence.

## 8. Recommended next tasks for Aru

Work in this order and make small changes with a test after each one:

1. **Reproduce the current setup:** backend health check, frontend load, one SQL query, one RAG query, and one BOTH query.
2. **Finish Phase 7:** remove metadata clutter from displayed RAG content without corrupting content; handle greetings/fallback questions; improve source display; check mobile layout and error states.
3. **Implement Phase 8 verification:** validate SQL claims against query results and RAG/hybrid claims against retrieved evidence; add bounded retry/fallback behavior. Preserve source provenance.
4. **Broaden and validate SQL support carefully:** only add question types that can be tested against the schema and expected answers. Keep database access read-only.
5. **Implement Phase 9 analysis/reporting:** add supported calculations and report output, clearly stating which features are implemented.
6. **Build Phase 10 evaluation:** separate routing, SQL, retrieval, hybrid, verification, and end-to-end tests; record correctness and groundedness.
7. **Complete Phase 11 security:** use read-only DB credentials, validate SQL, add timeouts/row limits, secure secrets, input/output validation, prompt-injection defenses for retrieved documents, and audit logging.
8. **Finish Phase 12:** clean install instructions, run end-to-end regression tests, document known limitations, and prepare a reliable demo.

## 9. Useful commands

From the repository root:

```powershell
# Run known SQL tests
python -m scripts.test_sql_agent
python -m scripts.test_sql_agent_cases
python -m scripts.test_sql_pipeline

# Start API
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000

# Full Python test suite (unit tests plus live PostgreSQL tests; DB tests skip if unavailable)
.\backend\venv\Scripts\python.exe -m pytest

# Frontend dependencies and dev server
cd .\frontend-angular
npm.cmd install
npm.cmd start
```

## Known limitations
- SQL reasoning covers defined campaign and returns patterns only; other business questions return an "unsupported" message.
- Answers are deterministic templates over SQL rows and retrieved text. No LLM writes answers.
- Auto-routing is keyword/rule based. Use the manual RAG / SQL / BOTH mode to override it.
- Campaign-ID questions only show documents that mention that ID. Multi-campaign reports are shown only when nothing more specific exists, and are labelled as general context.
- Evidence excerpts are cut at a character limit and may end mid-sentence.
- Verification confirms evidence exists; it does not fact-check each claim.

The SQL test commands above passed in Anvi's environment. Run them again after setup or code changes; results may differ on a fresh machine.

## 10. Handoff rules

- Work from a clean Git commit/branch when possible.
- Do not overwrite working code without first saving/committing it.
- Do not commit `.env`, API keys, passwords, database dumps containing private data, or `node_modules`.
- Make one focused change at a time and run the relevant test immediately.
- Keep SQL results, document evidence, and source metadata traceable.
- Clearly label NovaMart as a synthetic dataset.
- If a command fails, share the complete error and the command used before making broad environment changes.
