# Architecture

---

## System Overview

A single-user, local FastAPI service that hosts both the API and the built Next.js frontend at one origin (`http://localhost:8001/app/`). The user drives it from the browser: create a workspace, upload data, ask questions. Each question runs a LangGraph agent that generates pandas code, executes it **locally** against an in-memory DataFrame, inspects the result or error, and composes a plain-language answer. The defining architectural rule is a hard privacy boundary: the LLM (Gemini) only ever receives **masked schema, column statistics, and computed result previews** — never a raw data row, and never an un-masked PII value. All state (workspaces, datasets, run history) persists to a local SQLite database; uploaded files persist to local disk and are loaded into an in-memory store keyed by workspace.

## Component Map

```
Browser (Next.js static export @ /app)
    │  HTTP (single origin :8001)
    ▼
FastAPI (src/api) ──────────────► SQLite (src/db, SQLAlchemy 2.0 + Alembic)
    │                                   ▲  workspaces, datasets, runs, column_notes
    ▼                                   │
Graph runner (src/graph/runner) ────────┘  persists each run (query+code+result+ts)
    │
    ▼
LangGraph agent (src/graph/agent) ── nodes: prepare_context → clarify → plan →
    │                                  generate_code ⇄ execute_code → inspect →
    │                                  compose_answer → enrich → finalize
    │
    ├──► In-memory dataset store (src/analysis/store)   ◄── real DataFrames (never sent to LLM)
    ├──► PII masking layer (src/analysis/pii)           ── masks LLM-bound surfaces
    ├──► Restricted pandas sandbox (src/analysis/sandbox)── executes generated code locally
    └──► LLM client (src/llm/client → Gemini)           ◄── receives ONLY masked schema/stats/results
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **Frontend** (`frontend/`) | Workspace UI, upload, ask box, answer + collapsible code, charts/history (later phases). Static export served by FastAPI at `/app`. |
| **API** (`src/api/`) | REST endpoints: workspaces, datasets (upload), ask, history, notes, exports. Validates input, delegates to the runner. |
| **Agent** (`src/graph/`) | LangGraph state machine implementing the adaptive code-execution loop. |
| **Analysis engine** (`src/analysis/`) | The privacy + execution core: in-memory store, PII masking, restricted sandbox, and (later) charts/quality/cost/context. Framework-agnostic, unit-testable in isolation. |
| **LLM** (`src/llm/`) | Gemini provider + client. Receives only masked payloads. |
| **Storage** (`src/db/`) | SQLAlchemy models + session; local disk for uploaded/derived files. |

## Data Flow

1. **Trigger:** user submits a question for a workspace → `POST /workspaces/{id}/ask`.
2. `run_agent` creates a `runs` row (status `pending`), builds the initial `AgentState`, and invokes the graph.
3. `prepare_context` loads the workspace's DataFrame(s) from the in-memory store (lazy-loading from disk on a cold process), computes schema + column statistics, and builds a **masked** context string (PII columns masked, only a few masked sample rows) to send to the LLM.
4. `generate_code` asks Gemini for pandas code, given the masked context and question (and, on a retry, the prior error). The code assigns its answer to a `result` variable.
5. `execute_code` runs that code in the restricted sandbox against the **real** DataFrame. It captures the real result (for the user) and a **masked** result preview (for the LLM).
6. `inspect` routes: on an execution error with attempts remaining, loop back to `generate_code` with the error; otherwise proceed.
7. `compose_answer` asks Gemini to turn the masked result preview into a plain-language answer.
8. `enrich` (Phase 2) adds chart spec, data-quality flags, follow-ups, and cost.
9. `finalize` persists the run (question, generated code, result preview, answer, timestamps, cost) and sets status `completed`.
10. **Output:** the API returns the answer + the exact code + the result table; the frontend shows the answer with a collapsible code panel.

## The Local Pandas Execution Sandbox (`src/analysis/sandbox.py`)

The heart of the system. Generated code is executed **in-process** but constrained:

- **Namespace:** `exec(code, safe_globals, local_ns)` where `safe_globals` exposes only `pd` (pandas), `np` (numpy), and the workspace DataFrame(s) bound to stable names (`df` for a single dataset; `df_<name>` for multiple). `__builtins__` is replaced with a curated whitelist (no `open`, `eval`, `exec`, `__import__`, `compile`, `input`, no `os`/`sys`/`subprocess`/`socket`). Import statements in generated code are rejected by a pre-execution AST check.
- **Contract:** the generated code must assign its answer to a variable named `result`. After execution the sandbox reads `local_ns["result"]` (a scalar, Series, or DataFrame) plus any captured stdout.
- **Result capture:** two views are produced — the **real** result (full values, returned to the user) and a **masked, size-capped** preview (PII masked, rows capped, sent to the LLM for answer composition).
- **Timeout:** a wall-clock limit (default 15s) enforced by running the `exec` in a worker thread and `join(timeout)` — **not** `signal.alarm`, which is unavailable on Windows. On timeout the run is aborted with an error.
- **Error feedback:** any exception is caught, its type + message (never the raw data) captured into `execution_error`, and fed back into `generate_code` on retry.
- **Step / retry limit:** `max_attempts` (Phase 1: 3; Phase 3 complex path: higher). When exhausted the agent composes a best-effort answer or surfaces a clear failure.
- **Guardrails:** AST validation rejects attribute access to dunder internals (`__globals__`, `__class__`, etc.) and any disallowed import/call before execution. This is the **LLM-Generated Code Execution** pattern (agentic-ai #22) wrapped in **Guardrails** (#18).

## The PII Detection & Masking Layer (`src/analysis/pii.py`)

Sits between the real DataFrame and every LLM-bound surface. It runs at upload time (to record PII columns on the dataset) and at every context/result build.

- **Detects** PII columns by (a) column-name heuristics (`name`, `pan`, `aadhaar`/`aadhar`, `phone`/`mobile`, `email`, `account`/`acct`/`a/c`) and (b) value-pattern matching on a sample: PAN `^[A-Z]{5}[0-9]{4}[A-Z]$`, Aadhaar 12-digit, email regex, 10-digit phone, long numeric account numbers.
- **Masks** detected columns before anything is sent to the LLM: schema samples, and any result preview that surfaces those columns. Masking replaces values with a stable token (e.g. `<name_1>`, `<pan_3>`) so the model can still reason about grouping/joins without seeing real values.
- **Boundary rule:** the DataFrame used for **execution** is always the real, un-masked data (the user acts on real numbers). Masking applies **only** to what is serialized into an LLM request. A Phase 1 test asserts no raw row and no un-masked PII value appears in the outbound Gemini payload.

## In-Memory Dataset Store (`src/analysis/store.py`)

A process-global mapping `workspace_id → { dataset_id → LoadedDataset }`, where `LoadedDataset` holds the real DataFrame, its schema, and its PII map. Datasets are loaded on upload and stay resident for the process lifetime (upload once, ask many). On a cold process (after restart) `prepare_context` lazily reloads a workspace's datasets from their on-disk files (persisted under `data/workspaces/<workspace_id>/`) using the `datasets` table as the manifest. Multi-file joins and multi-sheet Excel (Phase 3) extend this to multiple named DataFrames per workspace.

## DB Persistence Model

SQLite via SQLAlchemy 2.0 + Alembic. Tables: `workspaces`, `datasets`, `runs` (query + code + result + answer + timestamps + cost), `column_notes` (Phase 3). See `spec/data.md` for fields. **Portability:** all columns use portable types — `Text`, `Integer`, `Boolean`, timezone-aware `TIMESTAMP`, and SQLAlchemy's generic `JSON` type (maps to `TEXT` on SQLite, `JSONB` on Postgres). No SQLite-only pragmas, no `AUTOINCREMENT` tricks; primary keys are UUID strings. This keeps a future Postgres migration a driver + URL change plus an Alembic run.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`gemini-2.5-flash`) | Generates pandas code + composes answers | Node catches the error, sets `state["error"]`, routes to `handle_error`; the run is marked `failed` and the UI shows a clear message. Retries/backoff added in the resilience work. |
| Local SQLite (`data/agent.db`) | Persist workspaces, datasets, runs | Startup fails fast if the DB can't be opened/migrated. |
| Local disk (`data/workspaces/`) | Persist uploaded + derived files | Upload returns a 500 with a clear message if the write fails. |

## Stack

> Concrete choices for this project. Generic rules (model-naming, DB driver, dev port, real-key tests) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12+ (backend), TypeScript (frontend).
- **Agent framework:** LangGraph (already wired in the boilerplate — extended in place).
- **LLM provider + model:** Google Gemini, `gemini-2.5-flash`, pinned via `AGENT_LLM_MODEL` in `.env`. The provider/client surfaces per-call token usage (Phase 2 cost). Cost rates are settings: `AGENT_GEMINI_INPUT_USD_PER_1K` / `AGENT_GEMINI_OUTPUT_USD_PER_1K` (non-zero defaults; owned by `backend-enrich` in `src/config/settings.py`).
- **Backend:** FastAPI, served with the boilerplate's `uv run python -m src` on port 8001.
- **Database + ORM:** SQLite (`sqlite:///./data/agent.db`) + SQLAlchemy 2.0 + Alembic. Schema kept Postgres-portable.
- **Frontend:** Next.js 15 (static export → `frontend/out`) + React 19 + Tailwind, mounted by FastAPI at `/app` (single origin).
- **Dependency management:** `uv` (Python, **always with `--native-tls`** on this Windows + corporate-TLS machine) + `pnpm` (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | (boilerplate-pinned) | Agent state graph |
| pandas | ≥2.2 | Local dataframe analysis (the compute engine) |
| numpy | ≥1.26 | Numeric ops in the sandbox |
| openpyxl | ≥3.1 | Excel (`.xlsx`) parsing (Phase 3) |
| google-genai | (boilerplate-pinned) | Gemini client |
| sqlalchemy | 2.0.x | ORM |
| alembic | latest | Migrations |
| structlog | (boilerplate) | Structured request/response logging |
| python-multipart | latest | File upload parsing in FastAPI |
| pandas → chart spec | (native) | Chart data is emitted as a JSON spec; the frontend renders with a lightweight chart lib (e.g. Recharts) — no server-side plotting deps |

**Avoid:**
- Any path that sends a raw DataFrame row or un-masked PII to the LLM — the core violation.
- Hardcoding `gemini-3.1-pro` — the boilerplate's `GeminiProvider.DEFAULT_MODEL` is **invalid**. The model must come from `AGENT_LLM_MODEL` (`gemini-2.5-flash`); the generator should also correct that default so nothing can accidentally fall back to it.
- `signal.alarm` for the sandbox timeout — unavailable on Windows; use a worker-thread timeout.
- Running `exec` with real `__builtins__` or allowing imports in generated code — sandbox escape.
- SQLite-only schema tricks — breaks the portability constraint.
- Running `uv` without `--native-tls` — fails behind the corporate TLS proxy.

## Deployment Model

Long-running local service. One command builds the frontend (`cd frontend && pnpm build`), one command runs the app (`uv run python -m src`) which serves API + UI on `http://localhost:8001/app/`. No containerization, no cloud. SQLite + local disk under `data/`.

## Observability

Structured JSON logging is wired from Phase 1 via the boilerplate's `structlog` setup (`src/observability/`). Every run logs: `run_id`, `workspace_id`, question, generated code, attempt count, execution success/error, latency, and (Phase 2) token cost — to stdout. LangSmith is not required (Gemini, not LangChain-hosted), so the observability floor is structured request/response logging; a log line appears for every end-to-end run and is asserted present by the Phase 1 gate.
