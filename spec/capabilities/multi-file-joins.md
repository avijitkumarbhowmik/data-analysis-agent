# Capability: Multi-File Joins

_Phase 3._

## What It Does
Lets a workspace hold multiple datasets and answer questions that span them by joining frames in the sandbox.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| multiple files | uploads | user | yes |
| question spanning files | string | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| named frames (`df_loans`, `df_repay`) | in-memory | dataset store |
| joined answer + code | object | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | read + merge frames | error captured → retry loop |

## Business Rules
- Each dataset is exposed to generated code under a stable frame name; the masked schema lists all frames.
- Joins run locally on real data; only masked schema/results reach the LLM.

## Success Criteria
- [ ] A question requiring a join of two uploaded files returns a correct answer computed over the merged data.
- [ ] The generated code shows the actual merge.
