# Capability: Run History

_Phase 2. (Persistence exists from Phase 1; this adds the list API, the extended detail, and the revisitable UI.)_

## What It Does
Surfaces the full run history per workspace and lets the user revisit any past run in full — including its chart, data-quality flags, follow-ups, cost, and result table.

## Endpoints (owned by `backend-history-conversation`, `src/api/history.py`)
- **`GET /workspaces/{id}/runs`** → list, newest-first:
  `{ "data": [ { "id", "question", "status", "created_at", "has_chart": bool } ] }`
  (`has_chart` = `runs.chart_spec_json` is non-null.)
- **`GET /runs/{run_id}`** (extend the existing boilerplate endpoint) → now also returns
  `chart_spec`, `data_quality_flags`, `followups`, `cost`, and `result_table` alongside
  `question`, `generated_code`, `answer`, `status`, `attempts` — so a past run is fully revisitable.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | for list |
| run_id | string | user selection | for detail |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| run list | list | UI history panel |
| full run detail (incl. chart_spec, flags, followups, cost, result_table) | object | UI (re-renders the full answer + dashboard) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | select runs by workspace; read enrichment JSON columns | 500 on DB error |

## Business Rules
- Every ask already persists a run (Phase 1); Phase 2 reads back the enrichment columns (`chart_spec_json`, `data_quality_json`, `followups_json`, `cost_json`) that Phase 2 now populates.
- Runs are ordered newest-first and survive restarts.
- No new table or migration — the columns already exist on `runs`.

## Success Criteria
- [ ] After several asks, `GET /workspaces/{id}/runs` lists them all with `id`, `question`, `status`, `created_at`, `has_chart`.
- [ ] `GET /runs/{run_id}` returns the run's `chart_spec`, `data_quality_flags`, `followups`, `cost`, and `result_table`; clicking a past run re-renders its full answer + dashboard.
- [ ] History persists across an app restart.
