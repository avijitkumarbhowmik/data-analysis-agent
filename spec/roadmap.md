# Roadmap

---

## What This Agent Does

A private, single-user data-analysis agent for CSV/Excel and lending/financial data. The user creates named **workspaces** (e.g. "Q2 loan book"), uploads files, then asks questions in plain English and gets plain-language answers, summary tables, and interactive charts. The defining constraint is **privacy**: raw data rows never leave the machine and are never sent to the LLM. The agent writes Python/pandas that executes **locally** against the real DataFrame; the model only ever sees masked schema, column statistics, and computed results. Auto-detected PII columns (names, PAN, Aadhaar, phone, email, account numbers) are masked before any schema, sample, or result surface is sent to the LLM. The output is production-grade because the user acts on the numbers.

## Who Uses It

A single THF (True Home Finance) finance professional running the app locally on their own machine. Their role is to interrogate loan-book and financial datasets — asking questions like "what is the total outstanding principal for loans past 90 DPD?" — and to trust the answer enough to act on it. They are analytically literate but do not want to write pandas by hand; they want plain-language answers with the computation shown for audit.

## Core Problem Being Solved

Today this analysis is done by hand in Excel or by asking an analyst to write ad-hoc pandas/SQL — slow, error-prone, and not auditable. General-purpose LLM tools are ruled out because uploading raw lending data (with PII) to a hosted model is a compliance non-starter. This agent replaces that manual loop with a stateful, privacy-safe assistant that answers arbitrary questions over the user's own data without the raw rows ever leaving the machine.

## Success Criteria

- [ ] A user can create a workspace, upload a CSV, ask a plain-language question, and receive a correct plain-language answer computed over **all** rows (not a sample), with the exact pandas code shown collapsibly.
- [ ] No raw data row and no un-masked PII value is ever included in any payload sent to the LLM — verifiable by inspecting the outbound request in a test.
- [ ] A numeric answer produced by the agent matches an independently-computed ground-truth value over the full dataset (e.g. a total that a sampled subset would get wrong).
- [ ] Workspaces, uploaded datasets, and full run history (query + code + result + timestamps) persist across app restarts.
- [ ] When the agent's first generated code raises an error, it inspects the error, fixes the code, and retries (bounded), rather than failing the query.

## What This Agent Does NOT Do (Out of Scope)

- Multi-user / auth / sharing — this is a single-user local tool; no login, no tenancy.
- Cloud hosting or remote data storage — everything runs on `localhost:8001`, data on local disk.
- Sending raw rows or un-masked PII to any external service, ever.
- Writing to source systems or databases of record — it reads uploaded files and can only save derived datasets back into its own workspace.
- Freeform arbitrary code execution beyond pandas/numpy analysis in a restricted sandbox (no filesystem, network, or OS access from generated code).
- Real-time / streaming data ingestion — analysis is over uploaded snapshot files.
- Model fine-tuning or learning from feedback across sessions.

## Key Constraints

- **Privacy (hard):** raw rows never sent to the LLM; PII masked on every LLM-bound surface. This is non-negotiable and gated by a test.
- **LLM:** Gemini only, model pinned to `gemini-2.5-flash` via `AGENT_LLM_MODEL` in `.env`. Nothing may rely on the boilerplate's invalid `gemini-3.1-pro` default (see architecture).
- **Local execution:** generated pandas runs in-process against the in-memory DataFrame in a restricted namespace with a wall-clock timeout and a step/retry limit.
- **DB:** SQLite (`sqlite:///./data/agent.db`), schema kept portable (no SQLite-only tricks) for a clean future Postgres migration.
- **Platform:** Windows 11 + corporate TLS — every `uv` command must pass `--native-tls`.
- **Cost / latency:** single small model (`gemini-2.5-flash`); a query should typically complete in a few seconds; per-query cost is displayed (Phase 2).

## Assumptions

> **Assumed:** Phase 1 is single-turn (one question at a time) per the explicit brief; multi-turn **conversation memory** is deferred to Phase 2, where it pairs with follow-up suggestions. A chat agent normally needs turn memory in Phase 1, so this deferral is called out for confirmation.
> **Assumed:** Streaming is deferred to Phase 2 (Phase 1 returns the full answer in one response) to protect first-time-right, per the brief marking streaming nice-to-have.
> **Assumed:** Sandbox defaults — wall-clock timeout 15s, `max_attempts` 3 in Phase 1 (higher for complex questions in Phase 3). Tunable via settings.
> **Assumed:** One CSV per workspace in Phase 1; multiple files / Excel sheets arrive in Phase 3.
> **Assumed:** Charts render client-side with a lightweight library (Recharts) from a server-emitted JSON spec — no server-side plotting dependency.
> **Assumed:** The in-memory dataset store is a process-global keyed by workspace, lazily reloaded from disk after a restart using the `datasets` table as manifest.
> **Assumed:** Per-query cost (Phase 2) uses a configurable `gemini-2.5-flash` token rate.
> **Assumed:** The generator corrects `GeminiProvider.DEFAULT_MODEL` (currently the invalid `gemini-3.1-pro`) to `gemini-2.5-flash` so nothing can fall back to an invalid model; the pinned `.env` value is the source of truth regardless.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend is REAL on the one core path (create workspace → upload one CSV → ask one question → local pandas execution with PII masking → plain-language answer + collapsible code). Everything else in the frontend is a clearly-labelled NON-FUNCTIONAL stub so the user sees the full vision without mistaking a stub for a bug. The full LangGraph skeleton (state, nodes, edges, runner) is wired in Phase 1 even where later-phase nodes are pass-through stubs. Later phases wire the stubs into real features.

### Phase 1 — Workspace, Upload & Private Ask (the core loop)

- **Goal:** The user creates a named workspace, uploads one CSV, types a plain-language question, and gets back a correct plain-language answer computed locally over the full dataset — with the exact pandas code the agent ran shown in a collapsible panel, and with PII masked on everything sent to Gemini.
- **Capabilities delivered:** `workspace-management`, `dataset-upload`, `pii-masking`, `local-code-analysis`.
- **Independent slices (parallel build units):**
  - `backend-engine` (backend) — the privacy + execution core: in-memory dataset store, PII detection/masking, and the restricted pandas execution sandbox, with unit tests. **Deps: none.**
  - `backend-agent-api` (backend) — DB schema + migration, LangGraph nodes/edges/runner for the adaptive code loop, and the workspace/upload/ask API endpoints. **Deps: `backend-engine`** (imports the store, masking, and sandbox).
  - `frontend-workspace` (frontend) — workspace list + create, CSV upload, schema preview, ask box, answer with collapsible code, plus all later-phase surfaces as labelled stubs. **Deps: none** (built to the API contract in `spec/api.md`).
- **Key surfaces / files:**
  - `backend-engine`: `src/analysis/store.py`, `src/analysis/pii.py`, `src/analysis/sandbox.py`, `tests/unit/analysis/`
  - `backend-agent-api`: `src/db/models.py`, `alembic/` migration, `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/generate_code.md`, `src/prompts/compose_answer.md`, `src/api/workspaces.py`, `src/api/datasets.py`, `src/api/ask.py`, `src/api/__init__.py` (router wiring), `src/domain/`, `tests/phase1/`
  - `frontend-workspace`: `frontend/src/app/page.tsx`, `frontend/src/app/components/*`, `frontend/tests/e2e/phase1.spec.ts`
- **Gate command:** `uv run --native-tls alembic upgrade head` then `uv run --native-tls pytest tests/phase1 -q` (real Gemini via `.env`, SQLite driver) then `cd frontend && pnpm exec playwright test tests/e2e/phase1.spec.ts`. The pytest suite includes a **privacy assertion** (no raw row / un-masked PII in the outbound LLM payload) and a **full-data assertion** (agent's numeric answer over a ≥5,000-row fixture equals the independently-computed ground truth, a value a sampled subset would get wrong).
- **How the user tests it (handoff seed):**
  1. Run `uv run --native-tls alembic upgrade head`, then `cd frontend && pnpm build`, then from repo root `uv run python -m src`.
  2. Open `http://localhost:8001/app/`.
  3. Click **New workspace**, name it "Q2 loan book". Upload a loan-book CSV; confirm the schema preview (columns + row count) appears.
  4. In the ask box type e.g. "What is the total outstanding principal?" and submit. Expect a plain-language answer within a few seconds; click **Show code** to expand the exact pandas that ran.
  5. **Real:** workspace create/list/open, CSV upload + schema preview, ask → answer, collapsible code. **Labelled stubs (visibly disabled, "coming soon"):** charts, run-history panel, follow-up suggestions, data-quality flags, per-query cost, streaming, multi-file joins, Excel sheet picker, column notes, save-derived, export/download.

### Phase 2 — Rich Dashboard Output, Transparency & Live Feedback

- **Goal:** Every answer becomes a rich, auditable analytics **dashboard** — for a categorical/share/mix question the agent renders **KPI stat tiles + stacked horizontal % bar charts** (the default look); it also flags data-quality issues, suggests 2–3 follow-ups, streams the answer as it composes, shows an estimated USD cost per query, remembers the conversation across turns within a workspace, and persists a fully-revisitable run history. **No new DB migration** — the `runs` table already has `chart_spec_json`, `data_quality_json`, `followups_json`, `cost_json`, `plan`; the `enrich` graph node (currently a pass-through stub) is made real.
- **Capabilities delivered:** `chart-generation`, `data-quality-flags`, `followup-suggestions`, `conversation-memory`, `run-history`, `live-query-feedback` (streaming answer + per-query cost).
- **Shared contracts (all three slices build to these, no cross-talk):** `chart_spec`, `cost`, `data_quality_flags`, `followups` JSON shapes in `spec/api.md` + the capability files; the fixed series color palette in `spec/capabilities/chart-generation.md` / `spec/ui.md`.

- **Independent slices (parallel build units — DISJOINT file ownership):**
  - **`backend-enrich`** (backend) — makes the `enrich` node real: chart-spec generation, data-quality profiling, follow-up suggestion, cost estimation, and token-usage surfacing. **Deps: none.**
    - **OWNS:** `src/analysis/charts.py` (new), `src/analysis/quality.py` (new), `src/analysis/cost.py` (new), the **`enrich` function body ONLY** in `src/graph/nodes.py`, `src/llm/client.py` + `src/llm/providers/gemini.py` (surface token usage so `cost.usd > 0`), `src/config/settings.py` (add `AGENT_GEMINI_INPUT_USD_PER_1K` / `AGENT_GEMINI_OUTPUT_USD_PER_1K`, non-zero defaults), new prompts under `src/prompts/` (chart role/kind + followups), `tests/phase2/test_enrich.py`.
  - **`backend-history-conversation`** (backend) — run-history API, streaming (SSE) ask endpoint, and conversation-memory. **Deps: none** (disjoint files).
    - **OWNS:** `src/api/history.py` (new: `GET /workspaces/{id}/runs` + extend `GET /runs/{run_id}`), `src/api/ask.py` (add `/ask/stream` SSE + add the enrichment fields to the non-stream response), `src/api/__init__.py` (register the history router — **this slice owns that single edit**), `src/graph/runner.py` (hydrate `messages` from recent runs + expose a streaming run path), `src/graph/state.py` (only if a field must be added — `messages` already exists), and the **memory-injection wiring inside `generate_code` + `compose_answer` node bodies ONLY** in `src/graph/nodes.py`, `tests/phase2/test_history_memory_stream.py`.
  - **`frontend-transparency`** (frontend) — the dashboard + all transparency surfaces. **Deps: none** (builds to the API contract).
    - **OWNS:** all of `frontend/` — new components `KpiTiles`, `StackedBarChart`/`Dashboard`, `DataQualityBadges`, `FollowupChips`, `CostBadge`, `RunHistoryPanel`, chat-thread; edits to `page.tsx` + `AskPanel.tsx` (replace the Phase-2 stubs, wire streaming); `frontend/src/lib/api.ts` (types + SSE stream client + history client); extend `frontend/src/lib/formatNumber.ts` **only if needed** (reuse it, don't duplicate); `frontend/tests/e2e/phase2.spec.ts`.
  - **`nodes.py` coordination (hard rule):** `backend-enrich` edits ONLY the `enrich` function; `backend-history-conversation` edits ONLY `generate_code` + `compose_answer` (memory injection). Disjoint functions in the same file → no clash.

- **Gate fixture:** `tests/phase2/fixtures/regional_payment_modes.csv` — regional payment-mode / fee-receipt data. Columns: `region` (category, e.g. Mumbai, Delhi, Bengaluru, Pune, Chennai, Hyderabad, Kolkata, Ahmedabad …), `payment_date` (for the "over time" test), and one fee-receipt **volume** column per payment mode: `dynamic_qr`, `initiate_link`, `static_qr`, `cheque_dd` (integers). ≥ ~2,000 rows across ≥8 regions so shares differ per region. A copy with **injected nulls** (blank cells in `dynamic_qr`) and **duplicate rows** exercises data-quality flags.
- **Gate command:** `uv run --native-tls pytest tests/phase2 -q` (real Gemini via `.env`, SQLite) then `cd frontend && pnpm build` and `cd frontend && pnpm exec playwright test tests/e2e/phase2.spec.ts` against the live app on `http://localhost:8001`. **pytest asserts:**
  - a mix/share question ("show the payment-mode mix by region") over the fixture yields `chart_spec.kind == "dashboard"` with ≥1 `kpis` entry and ≥1 `charts` panel whose `categories[].segments` is non-empty;
  - an "…over time" question yields `chart_spec.kind == "line"` with non-empty `points`;
  - a single-scalar question yields `chart_spec == null`;
  - the nulls/dupes fixture raises ≥1 `data_quality_flags` entry;
  - ≥2 `followups` returned;
  - `cost.usd > 0`;
  - a second turn resolves context from the first (memory);
  - a run persists → `GET /workspaces/{id}/runs` lists it → `GET /runs/{run_id}` returns its `chart_spec`.
- **How the user tests it (handoff seed):** `cd frontend && pnpm build`, then from repo root `uv run python -m src`, open `http://localhost:8001/app/`. Create a workspace, upload the regional payment-mode CSV, then ask **"show the payment-mode mix by region"** → a **dashboard** renders: a row of KPI stat tiles (color-coded per payment mode, green emphasized total) above one-or-two **stacked horizontal % bar charts** (regions sorted by share) with a shared color legend; the answer streams in; a cost badge shows `$…`; 2–3 follow-up chips appear (click one → asks with prior context). Ask an "over time" question → a line chart. Upload the messy fixture → data-quality flags appear. Open the **Run history** panel and click a past run to revisit its full answer + dashboard. **Newly real:** dashboard/charts, quality flags, follow-ups, streaming, cost, conversation memory, history. **Still stubbed (labelled "coming soon", not bugs):** multi-file joins, Excel sheet picker, column notes, save-derived, export/download.

### Phase 3 — Advanced Analysis: Joins, Excel, Rules, Derived Data & Adaptive Depth

- **Goal:** The user can join multiple files, load multi-sheet Excel workbooks, attach persistent column notes / business rules that inform every analysis, save cleaned/derived datasets back into the workspace, download charts/reports/CSVs, and rely on adaptive reasoning — the agent asks a clarifying question when uncertain and uses a plan-then-execute flow with a longer iterate-until-right loop for complex questions.
- **Capabilities delivered:** `multi-file-joins`, `multi-sheet-excel`, `column-notes-and-rules`, `derived-datasets-and-exports`, `adaptive-reasoning`.
- **Independent slices (parallel build units):**
  - `backend-multisource` (backend) — multi-file/multi-sheet upload + parsing, multi-DataFrame store keyed by workspace, join support in the sandbox namespace. **Deps: none** (extends `src/analysis/store.py`, `src/api/datasets.py`).
  - `backend-rules-derived` (backend) — column-notes/business-rules API + injection into the context prompt, save-derived-dataset, and export/download endpoints. **Deps: none** (`src/api/notes.py`, `src/api/exports.py`, `src/analysis/context.py`).
  - `backend-adaptive` (backend) — real `clarify` and `plan` nodes + extended iterate-until-right loop with a higher step limit for complex questions. **Deps: none** (edits `src/graph/nodes.py` adaptive nodes + `src/graph/edges.py`).
  - `frontend-advanced` (frontend) — multi-file upload + join UI, Excel sheet picker, column-notes editor, save-derived button, export/download buttons, clarifying-question prompt. **Deps: none** (API contract).
  > Note: `backend-adaptive`, `backend-multisource`, and `backend-rules-derived` all touch `src/graph/` or `src/api/` but on **disjoint files**; if the router file `src/api/__init__.py` must register new routers, `backend-rules-derived` owns that single edit to avoid a conflict.
- **Key surfaces / files:** `src/analysis/store.py` (multi-df), `src/analysis/context.py`, `src/api/datasets.py`, `src/api/notes.py`, `src/api/exports.py`, `src/graph/nodes.py` (clarify/plan real), `src/graph/edges.py`, `src/db/models.py` (column_notes, derived flags) + migration, `frontend/src/app/components/*`, `tests/phase3/`, `frontend/tests/e2e/phase3.spec.ts`
- **Gate command:** `uv run --native-tls alembic upgrade head` then `uv run --native-tls pytest tests/phase3 -q` (real Gemini via `.env`, SQLite) then `cd frontend && pnpm exec playwright test tests/e2e/phase3.spec.ts`. Tests assert: a two-file join answers a question spanning both files; a multi-sheet `.xlsx` loads all sheets; a business rule ("exclude written-off loans") measurably changes a computed total vs. without the rule; a derived dataset is saved and re-queryable; an export produces a downloadable CSV; an ambiguous question triggers a clarifying question instead of running.
- **How the user tests it (handoff seed):** `cd frontend && pnpm build`, then `uv run python -m src`, open `http://localhost:8001/app/`. Upload two related CSVs and an `.xlsx`; ask a question that needs a join; add a column note "DPD = days past due" and a rule "exclude written-off loans" and confirm the answer changes; save a cleaned dataset back and query it; download a result as CSV; ask a deliberately vague question and confirm the agent asks a clarifying question before running. **All capabilities now real — no stubs remain.**
