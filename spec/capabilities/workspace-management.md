# Capability: Workspace Management

_Phase 1 — active._

## What It Does
Lets the user create, list, and open named workspaces that persist across sessions and hold their datasets and run history.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| name | string | user (New workspace) | yes |
| workspace_id | string | user (selection) | for open |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| workspace | record | DB (`workspaces`) + sidebar |
| workspace list | list | sidebar |
| workspace detail (datasets + recent runs) | object | main panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | insert/select workspace | 400 on duplicate/blank name; 500 on DB error |

## Business Rules
- Workspace names are unique and non-blank.
- Opening a workspace returns its datasets and recent runs.
- Deleting a workspace cascades to its datasets, runs, notes, and on-disk files.

## Success Criteria
- [ ] Creating a workspace returns an id and it appears in `GET /workspaces`.
- [ ] A duplicate name is rejected with 400.
- [ ] Workspaces persist across an app restart (still listed after reboot).
