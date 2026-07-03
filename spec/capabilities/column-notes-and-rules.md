# Capability: Column Notes & Business Rules

_Phase 3._

## What It Does
Lets the user attach persistent column notes and business rules (e.g. "DPD = days past due", "exclude written-off loans") that are injected into the analysis context so every answer respects them.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| note / rule | object | user (editor) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| note record | record | DB (`column_notes`) |
| rules injected into context | string | prepare_context → LLM |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | store/read notes | 500 on DB error |
| Gemini | analysis honoring rules | node error → handle_error |

## Business Rules
- Notes/rules persist per workspace and are included in the masked context on every ask.
- A business rule (e.g. exclude written-off loans) measurably changes computed results.

## Success Criteria
- [ ] Adding a rule "exclude written-off loans" changes a computed total vs. the same question without the rule.
- [ ] Notes persist across restart and appear in the context for later questions.
