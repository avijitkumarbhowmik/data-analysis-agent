# Capability: Follow-up Suggestions

_Phase 2._

## What It Does
After each answer, suggests 2–3 relevant follow-up questions the user can click to ask next (with prior-turn context via conversation memory).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| answer + masked result | string | compose_answer | yes |
| schema_summary | string | prepare_context | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| followups | list of strings | UI chips + `runs.followups_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | propose follow-ups from masked context | omit chips, keep answer (degrade) |

## Business Rules
- 2–3 suggestions, grounded in the workspace schema (not generic).
- Clicking a chip issues a new ask that carries conversation context.

## Success Criteria
- [ ] Each answer returns ≥2 follow-up suggestions relevant to the dataset's columns.
- [ ] Clicking a suggestion asks it with the prior turn in context.
