# API

---

## API Style

REST over HTTP, served by FastAPI at the single origin `http://localhost:8001`. All responses use the boilerplate envelope: success → `{ "data": {...} }`; error → `{ "detail": { "code", "message" } }` with the appropriate status. The built frontend is served at `/app`. No auth (single-user local tool — see Authentication).

Phase legend: **[P1]** real in Phase 1 · **[P2]** Phase 2 · **[P3]** Phase 3.

## Endpoints / Commands

### `POST /workspaces`  **[P1]**
**Purpose:** Create a named workspace.
**Request:** `{ "name": "Q2 loan book" }`
**Response:** `{ "data": { "id": "uuid", "name": "Q2 loan book", "created_at": "…" } }`
**Errors:** 400 (blank/duplicate name), 500.

### `GET /workspaces`  **[P1]**
**Purpose:** List all workspaces (for the sidebar).
**Response:** `{ "data": [ { "id", "name", "dataset_count", "updated_at" } ] }`

### `GET /workspaces/{id}`  **[P1]**
**Purpose:** Open a workspace — its datasets and recent runs.
**Response:** `{ "data": { "id", "name", "datasets": [ {id,name,filename,row_count,column_count,schema} ], "recent_runs": [ {id,question,status,created_at} ] } }`
**Errors:** 404.

### `POST /workspaces/{id}/datasets`  **[P1: single CSV] [P3: multi-file + Excel]**
**Purpose:** Upload a data file; parse, profile schema, detect PII, load into the in-memory store.
**Request:** `multipart/form-data` with `file`. (P3 accepts `.xlsx` and multiple files; a sheet picker selects sheets.)
**Response:** `{ "data": { "id", "name", "filename", "row_count", "column_count", "schema": [ {name,dtype,stats} ], "pii_columns": ["name","pan"] } }`
**Errors:** 400 (unsupported type / unparseable), 413 (too large), 500.

### `POST /workspaces/{id}/ask`  **[P1, enriched in P2]**
**Purpose:** Ask a plain-language question; run the agent; return the answer + exact code + result + Phase-2 enrichments.
**Request:** `{ "question": "show the payment-mode mix by region", "dataset_id": "uuid" | null }`
**Response:** `{ "data": { "run_id", "answer", "generated_code", "result_table": {columns, rows}, "status", "attempts", "chart_spec": {…}|null, "data_quality_flags": [...], "followups": [...], "cost": {…}, "clarifying_question"?: "…" } }`
- **[P2]** `chart_spec`, `data_quality_flags`, `followups`, `cost` are now **always present** on a successful run (each may be `null`/`[]` when not applicable). See the JSON shapes at the bottom of this file. `clarifying_question` remains **[P3]**.
**Errors:** 400 (no dataset in workspace), 404, 500 (run failed → `status: "failed"`, message in `answer`/`error`).

### `POST /workspaces/{id}/ask/stream`  **[P2]**
**Purpose:** Same as `/ask` but streams via Server-Sent Events. Owned by `backend-history-conversation` (`src/api/ask.py`).
**Request:** same body as `/ask`.
**Response:** `Content-Type: text/event-stream`:
- `event: delta` / `data: {"text": "<answer fragment>"}` — zero or more, streamed as the answer composes.
- `event: final` / `data:` = the **same JSON object** the non-streaming `/ask` returns under `data` (with `chart_spec`, `data_quality_flags`, `followups`, `cost`). Exactly one, terminal.
- `event: error` / `data: {"message": "…"}` on mid-stream failure → the frontend degrades to non-streaming `/ask`.

### `GET /workspaces/{id}/runs`  **[P2]**
**Purpose:** Run-history list for the workspace, newest-first. Owned by `backend-history-conversation` (`src/api/history.py`).
**Response:** `{ "data": [ { "id", "question", "status", "created_at", "has_chart": bool } ] }` (`has_chart` = `chart_spec_json` non-null).

### `GET /runs/{run_id}`  **[P1 — boilerplate, extended in P2]**
**Purpose:** Fetch one run's full, revisitable detail. Owned by `backend-history-conversation` (`src/api/history.py`).
**Response [P2]:** `{ "data": { "run_id", "status", "question", "answer", "generated_code", "attempts", "result_table": {columns, rows}, "chart_spec": {…}|null, "data_quality_flags": [...], "followups": [...], "cost": {…} } }`
**Errors:** 404.

### `POST /workspaces/{id}/notes`  **[P3]**
**Purpose:** Add/update a column note or business rule.
**Request:** `{ "dataset_id"?: "uuid", "column_name"?: "dpd", "note": "DPD = days past due", "is_business_rule": false }`
**Response:** `{ "data": { "id", "note", "is_business_rule" } }`

### `GET /workspaces/{id}/notes`  **[P3]**
**Purpose:** List notes/rules for the workspace (shown in the editor and injected into analysis context).

### `POST /workspaces/{id}/datasets/{dataset_id}/save-derived`  **[P3]**
**Purpose:** Save a cleaned/derived DataFrame produced by a run back into the workspace as a new dataset.
**Request:** `{ "source_run_id": "uuid", "name": "loans_clean" }`
**Response:** `{ "data": { "id", "name", "row_count", "column_count" } }`

### `GET /runs/{run_id}/export?format=csv|png`  **[P3]**
**Purpose:** Download a run's result table as CSV or its chart as an image.
**Response:** file download (`text/csv` or `image/png`).

### `GET /health`  **[P1 — boilerplate]**
Liveness check.

## Phase 2 shared JSON shapes (authoritative — backend + frontend build to these)

Full details in the capability files; the canonical shapes:

```jsonc
// chart_spec — see spec/capabilities/chart-generation.md for the palette + rules
chart_spec = null | {
  "kind": "dashboard" | "line" | "bar",
  "title": string, "subtitle": string,
  "series": [ { "key": string, "label": string } ],
  "kpis":   [ { "label": string, "value": number, "format": "percent"|"number",
               "seriesKey": string|null, "emphasis": boolean } ],
  "charts": [ { "heading": string, "axisLabel": string,
               "categories": [ { "label": string, "total": number,
                                 "segments": { "<seriesKey>": number } } ] } ],
  // kind == "line" replaces `charts` with:
  "points": [ { "x": string|number, "y": number, "series"?: string } ]
}
// values in kpis[].value / categories[].total / segments are fractions 0..1 (rendered as %)

// cost — usd = in/1000*RATE_IN + out/1000*RATE_OUT (rates in settings, non-zero defaults)
cost = { "input_tokens": int, "output_tokens": int, "usd": float }   // usd > 0

// data_quality_flags
data_quality_flags = [ { "level": "info"|"warn", "column": string|null, "message": string } ]

// followups — 2..3 plain-language question strings (or [] on degrade)
followups = [ string, string, ... ]
```

## Authentication

None. This is a single-user tool bound to `localhost` only; the data never leaves the machine, so there is no login, token, or tenancy. (If a future multi-user need arises, auth is added at the API layer — out of scope here.)
