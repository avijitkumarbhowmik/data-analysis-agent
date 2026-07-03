# Data Model

---

## Storage Technology

SQLite (`sqlite:///./data/agent.db`) via SQLAlchemy 2.0 + Alembic. Uploaded and derived files live on local disk under `data/workspaces/<workspace_id>/`. The schema is deliberately **Postgres-portable**: UUID-string primary keys, portable column types (`Text`, `Integer`, `Boolean`, timezone-aware `TIMESTAMP`), and SQLAlchemy's generic `JSON` type (→ `TEXT` on SQLite, `JSONB` on Postgres). No SQLite-only pragmas or `AUTOINCREMENT`.

## Entities

### Entity: Workspace
A named analysis context the user returns to across days.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (UUID) | yes | Primary key |
| name | Text | yes | User-given name (e.g. "Q2 loan book"), unique |
| created_at | TIMESTAMP(tz) | yes | Creation time |
| updated_at | TIMESTAMP(tz) | yes | Last activity |

### Entity: Dataset
A file loaded into a workspace (Phase 1: one CSV; Phase 3: multiple files, Excel sheets, derived datasets).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (UUID) | yes | Primary key |
| workspace_id | Text (FK → workspaces.id) | yes | Owning workspace |
| name | Text | yes | Frame name used in code (e.g. `df`, `df_loans`) |
| filename | Text | yes | Original upload filename |
| file_path | Text | yes | On-disk path under `data/workspaces/…` |
| sheet_name | Text | no | Excel sheet (Phase 3; null for CSV) |
| row_count | Integer | yes | Rows parsed |
| column_count | Integer | yes | Columns parsed |
| schema_json | JSON | yes | `[{name, dtype, stats}]` — column schema + basic stats |
| pii_columns_json | JSON | yes | List of detected PII column names + type |
| is_derived | Boolean | yes | True for datasets saved back by the agent (Phase 3); default false |
| source_run_id | Text (FK → runs.id) | no | The run that produced a derived dataset (Phase 3) |
| created_at | TIMESTAMP(tz) | yes | Upload/creation time |

### Entity: Run
One question and its full analysis trail — the persisted run history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (UUID) | yes | Primary key |
| workspace_id | Text (FK → workspaces.id) | yes* | Owning workspace (*nullable only for the boilerplate's legacy rows) |
| dataset_id | Text (FK → datasets.id) | no | Primary dataset queried (null for multi-file) |
| question | Text | yes | User's plain-language question (maps to boilerplate `input_text`) |
| plan | Text | no | Analysis plan (Phase 3) |
| generated_code | Text | no | Exact pandas the agent ran |
| result_preview | Text | no | Masked result preview (as sent to the LLM) |
| answer | Text | no | Plain-language answer (maps to boilerplate `output_text`) |
| chart_spec_json | JSON | no | Chart spec (Phase 2) |
| data_quality_json | JSON | no | Data-quality flags (Phase 2) |
| followups_json | JSON | no | Suggested follow-up questions (Phase 2) |
| cost_json | JSON | no | `{input_tokens, output_tokens, usd}` (Phase 2) |
| attempts | Integer | yes | Number of generate→execute cycles; default 1 |
| status | Text | yes | pending / completed / failed / needs_clarification |
| error_message | Text | no | Error if failed |
| created_at | TIMESTAMP(tz) | yes | Ask time |
| completed_at | TIMESTAMP(tz) | no | Finish time |

> The boilerplate ships a `runs` table with `input_text`/`output_text`/`status`. The Phase 1 Alembic migration **extends** it with the columns above (keeping `input_text`=question, `output_text`=answer) rather than replacing it.

### Entity: ColumnNote  *(Phase 3)*
Persistent column notes / business rules that inform every analysis in a workspace.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (UUID) | yes | Primary key |
| workspace_id | Text (FK → workspaces.id) | yes | Owning workspace |
| dataset_id | Text (FK → datasets.id) | no | Scoped to a dataset, or workspace-wide if null |
| column_name | Text | no | Column the note is about (null = general rule) |
| note | Text | yes | e.g. "DPD = days past due" |
| is_business_rule | Boolean | yes | True for rules that alter computation (e.g. "exclude written-off loans") |
| created_at | TIMESTAMP(tz) | yes | Creation time |

### Relationships

- `Workspace` 1—N `Dataset`, 1—N `Run`, 1—N `ColumnNote`.
- `Run` N—1 `Dataset` (primary dataset, optional); a derived `Dataset` N—1 `Run` (its source).
- Deleting a workspace cascades to its datasets, runs, notes, and on-disk files.

## Data Lifecycle

- **Created:** workspace on create; dataset on upload (row + on-disk file + in-memory load); run at ask-time (`pending` → `completed`/`failed`); note on save (Phase 3).
- **Updated:** run row updated as the graph progresses; workspace `updated_at` on any activity.
- **Deleted:** on explicit workspace delete (cascade). No automatic archival/expiry — this is a personal tool; the user owns retention. In-memory datasets are evicted on process restart and lazily reloaded from disk on next use.

## Sensitive Data

The dataset contents are the sensitive asset — lending data with PII (names, PAN, Aadhaar, phone, email, account numbers). Protections:
- Raw rows and files never leave the machine; only the local SQLite DB and disk hold them.
- PII columns are detected at upload (recorded in `datasets.pii_columns_json`) and **masked on every LLM-bound surface** (schema samples, result previews) — the LLM never sees an un-masked PII value or a raw row. See `src/analysis/pii.py` in `spec/architecture.md`.
- `result_preview` stored in `runs` is the masked preview; the real result is returned to the user in-session but the masked form is what was sent to the LLM and what is persisted as the audit trail.
