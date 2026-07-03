# Capability: Dataset Upload

_Phase 1 — active (single CSV). Extended in Phase 3 (multi-file, Excel)._

## What It Does
Accepts a CSV upload into a workspace, parses it to a pandas DataFrame, profiles its schema and column stats, detects PII columns, persists the file to disk, and loads it into the in-memory store for querying.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| file | multipart file (CSV) | user upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | record | DB (`datasets`) + disk (`data/workspaces/…`) |
| schema preview (columns, dtypes, row/col counts) | object | UI schema preview |
| pii_columns | list | UI badge + `datasets.pii_columns_json` |
| loaded DataFrame | in-memory | dataset store keyed by workspace |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | `read_csv` | 400 on unparseable/unsupported file |
| Local disk | write file | 500 on write failure |
| SQLite | insert dataset | 500 on DB error |

## Business Rules
- Phase 1 accepts a single CSV per workspace; the frame is named `df`.
- The real DataFrame is loaded for execution; PII detection runs at upload and records masked columns.
- Files persist to disk so datasets survive a restart (lazy-reloaded on next use).

## Success Criteria
- [ ] Uploading a valid CSV returns a schema with correct row/column counts.
- [ ] PII columns (e.g. name, PAN) are detected and listed in the response.
- [ ] After upload the dataset is queryable via `/ask` in the same session and after a restart.
- [ ] An unparseable file returns 400 with a clear message.
