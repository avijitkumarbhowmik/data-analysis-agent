# UI

---

## UI Type

Web app — a single-page workspace console built with Next.js 15 + React 19 + Tailwind, exported statically to `frontend/out` and served by FastAPI at `http://localhost:8001/app/`. Single origin, so the frontend calls the API with same-origin relative paths (`/workspaces`, `/workspaces/{id}/ask`, …).

Phase legend: **[P1]** real · **[P2]** / **[P3]** wired later — shown in Phase 1 as clearly-labelled, visibly-disabled "coming soon" stubs so the user sees the vision without mistaking a stub for a bug.

## Views / Screens

### Screen: Workspace Console (single page)  **[P1]**
**Purpose:** The whole app. A left sidebar of workspaces, a main panel for the selected workspace: upload, ask, and answers.

**Layout & elements:**
- **Sidebar (left) [P1]:** list of workspaces (`GET /workspaces`) + **New workspace** button (modal → `POST /workspaces`). Selecting one opens it.
- **Dataset area [P1]:** CSV upload dropzone (`POST /workspaces/{id}/datasets`); on success shows a **schema preview** (columns, dtypes, row count) and a small badge listing detected/masked PII columns ("PII masked: name, PAN").
  - **[P3 stub]** multi-file upload + join builder, Excel **sheet picker** — shown disabled with "coming soon".
- **Ask box [P1]:** a text input + **Ask** button (`POST /workspaces/{id}/ask`).
- **Answer card [P1]:** plain-language answer, a result table when present, and a collapsible **Show code** panel with the exact pandas that ran. Shows attempt count if >1 ("fixed and retried").
  - **[P2 stub]** interactive **chart** area ("Charts — coming soon"), **cost** badge ("Est. cost — coming soon"), **follow-up** chips ("Suggested follow-ups — coming soon"), **data-quality** flags ("Data-quality checks — coming soon"), streaming indicator.
- **Run history panel [P2 stub]:** a "History — coming soon" panel listing past runs; in P2 becomes a real revisitable list (`GET /workspaces/{id}/runs`).
- **Column notes / rules [P3 stub]:** a "Notes & business rules — coming soon" editor.
- **Save-derived / Export [P3 stub]:** "Save cleaned dataset" and "Download CSV / chart" buttons, disabled with "coming soon".

**Actions available (P1 real):** create workspace, select workspace, upload CSV, ask a question, expand/collapse the code, read the answer + table.

### Phase 2 additions (wire the stubs) — owned by `frontend-transparency`, all of `frontend/`

**The dashboard visual system (the PRIMARY rich output).** Rendered from `chart_spec` (contract in `spec/api.md` + `spec/capabilities/chart-generation.md`). Self-contained styling, NO external CDNs, works in **light AND dark** themes. Components: `Dashboard` (container), `KpiTiles`, `StackedBarChart`, shared legend.

- **Header:** `title` (bold) + grey `subtitle` caption below it.
- **KPI stat tiles (row):** one card per `kpis[]` entry — a label + a big bold color-coded percentage/number (via `formatNumber.ts`). Tile accent color = the palette color of its `seriesKey` (by `series[]` index); a tile with `emphasis:true` uses the green `#16a34a` "total" accent. Light card bg, subtle border; readable in dark mode.
- **Stacked horizontal % bars:** render `charts[]` as **one or two panels side by side** (e.g. "Top N regions" / "Bottom N regions"). Each panel: `heading`, a y-axis of `categories[].label` rows sorted descending by `total`, each bar's length = `total` (as %), each bar split into `segments` colored by series index. Clean 0%–6%-style x-axis with gridlines (`slate-200` light / `slate-700` dark) and the `axisLabel`.
- **Shared legend (bottom):** maps each `series[].label` → its palette color.
- **Fixed palette (authoritative, matches chart-generation.md):** index0 `#1e40af`, index1 `#ea580c`, index2 `#64748b`, index3 `#b91c1c`; emphasized total `#16a34a`.
- **Other kinds:** `kind:"line"` renders `points` as a line chart; `kind:"bar"` a simple bar; `chart_spec:null` → no chart, answer only.

**Number formatting:** REUSE `frontend/src/lib/formatNumber.ts` (17.8%, comma-grouped counts, ≤2 decimals) — do not duplicate; extend it only if a new formatter is genuinely needed.

**Other Phase 2 surfaces:**
- **Streaming:** the answer **streams** in via SSE (`/ask/stream`), progressively appending `delta` text; on any stream error the client silently falls back to non-streaming `/ask` and renders the same enriched result.
- **Cost badge (`CostBadge`):** shows real `cost.usd` (e.g. "$0.0021") with tokens on hover.
- **Follow-up chips (`FollowupChips`):** 2–3 chips from `followups`; clicking one asks it with prior-turn context.
- **Data-quality badges (`DataQualityBadges`):** render `data_quality_flags`; `warn` styled amber, `info` neutral.
- **Chat thread:** the ask area becomes a **multi-turn thread** (conversation memory) — prior turns visible above the input.
- **Run-history panel (`RunHistoryPanel`):** real, revisitable list from `GET /workspaces/{id}/runs` (shows question, time, a chart indicator when `has_chart`); clicking a run loads `GET /runs/{run_id}` and re-renders its full answer + dashboard.

**Still stubbed in Phase 2 (labelled "coming soon", never a dead/broken button):** multi-file joins, Excel sheet picker, column notes/rules, save-derived, export/download.

### Phase 3 additions (wire the stubs)
- Multi-file upload + join UI; Excel sheet picker; column-notes/business-rules editor; **Save cleaned dataset** button; **Download CSV/chart** buttons; a **clarifying-question** prompt when the agent is uncertain (answer inline → re-ask).

## Error States

- **Loading:** ask button shows a spinner / "Running…"; upload shows a progress state; (P2) streaming shows a live indicator.
- **Empty:** "Create a workspace to begin"; within a workspace with no dataset, "Upload a CSV to start asking questions."
- **Errors:** upload errors (unsupported type, parse failure) and ask errors (run failed, no dataset) surface as a red banner with the API `detail.message`; network errors show "is the server running?". A failed run shows the error and, if the code loop exhausted its attempts, says so plainly.
- **Stub clarity:** every not-yet-real surface carries a visible "coming soon" label and is disabled — never a dead button that looks broken.

## Tech Stack

Next.js 15 + React 19 + Tailwind, static export (`output: 'export'` → `frontend/out`), served by FastAPI at `/app`. Built with `pnpm build`. Charts (Phase 2) via a lightweight client chart library (e.g. Recharts). Playwright for E2E smoke tests under `frontend/tests/e2e/`.
