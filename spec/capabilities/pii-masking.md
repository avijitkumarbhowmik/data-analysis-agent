# Capability: PII Masking (Privacy Boundary)

_Phase 1 — active. The defining constraint of the product._

## What It Does
Detects PII columns and masks them on every surface sent to the LLM (schema samples, result previews), so no raw data row and no un-masked PII value ever reaches Gemini — while execution still runs against the real, un-masked data.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| DataFrame | pandas frame | in-memory store | yes |
| surface to mask (schema sample / result preview) | frame/preview | prepare_context / execute_code | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| pii_columns map | dict | `datasets.pii_columns_json` |
| masked text/preview | string | LLM request payload only |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none — pure local computation) | — | detection is best-effort; on ambiguity a column is masked (fail-safe) |

## Business Rules
- Detect by column-name heuristics (name, PAN, aadhaar, phone, email, account) AND value patterns (PAN `^[A-Z]{5}[0-9]{4}[A-Z]$`, 12-digit Aadhaar, email, 10-digit phone, long account numbers).
- Mask with stable tokens (`<name_1>`, `<pan_3>`) so the model can still reason about grouping/joins.
- **Boundary:** masking applies ONLY to LLM-bound payloads; execution uses the real data; the user sees real results.
- When detection is uncertain, prefer masking (fail toward privacy).

## Success Criteria
- [ ] A test inspecting the outbound Gemini payload finds no raw data row and no un-masked PII value (PAN/Aadhaar/email/phone/account/name).
- [ ] Detected PII columns are recorded on the dataset.
- [ ] The real result returned to the user still contains real values (masking did not corrupt the answer).
