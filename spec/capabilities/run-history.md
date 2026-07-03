# Capability: Run History

_Phase 2. (Persistence exists from Phase 1; this adds the revisitable UI + list API.)_

## What It Does
Persists and surfaces the full run history per workspace (query + code + result + timestamps), letting the user revisit any past run.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| run_id | string | user (selection) | for detail |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| run list | list | UI history panel |
| run detail (question, code, result, cost, ts) | object | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | select runs by workspace | 500 on DB error |

## Business Rules
- Every ask persists a run in Phase 1 already; Phase 2 exposes `GET /workspaces/{id}/runs` and the panel.
- Runs are ordered newest-first and survive restarts.

## Success Criteria
- [ ] After several asks, the history endpoint returns them all with code + result + timestamps.
- [ ] Selecting a past run shows its exact query, code, and result.
- [ ] History persists across an app restart.
