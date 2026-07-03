# Capability: Multi-Sheet Excel

_Phase 3._

## What It Does
Loads multi-sheet `.xlsx` workbooks, exposing each sheet as a queryable frame with a sheet picker in the UI.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| .xlsx file | upload | user | yes |
| selected sheets | list | user (picker) | no (default all) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| one dataset per sheet | records | DB (`datasets`, `sheet_name`) + store |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas + openpyxl | `read_excel` per sheet | 400 on unreadable workbook |

## Business Rules
- Each sheet becomes a dataset with `sheet_name` set and its own schema + PII detection.
- PII masking applies per sheet as for CSVs.

## Success Criteria
- [ ] A two-sheet `.xlsx` loads both sheets as separate queryable datasets.
- [ ] A question against a chosen sheet returns a correct answer.
