# Capability: Derived Datasets & Exports

_Phase 3._

## What It Does
Lets the user save a cleaned/derived DataFrame produced by a run back into the workspace as a new queryable dataset, and download results (CSV) and charts (image) locally.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| source_run_id | string | user | yes (save) |
| new dataset name | string | user | yes (save) |
| run_id + format | string | user | yes (export) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| derived dataset | record + file | DB (`datasets`, `is_derived=true`) + disk + store |
| downloaded file | CSV / PNG | user's machine |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local disk | write derived file / export | 500 on write failure |
| SQLite | insert derived dataset | 500 on DB error |

## Business Rules
- A derived dataset records its `source_run_id` and is immediately queryable like any upload.
- Exports contain the real result values (this is a local download for the user, not an LLM surface).

## Success Criteria
- [ ] Saving a derived dataset makes it appear in the workspace and answer a follow-up query.
- [ ] Exporting a run's result yields a downloadable CSV with the real values.
