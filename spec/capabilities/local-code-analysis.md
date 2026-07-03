# Capability: Local Code Analysis (the Ask loop)

_Phase 1 — active. The core loop. Depth extended in Phase 3 (plan + longer iterate)._

## What It Does
Answers a plain-language question by having Gemini generate pandas code, executing it locally in a restricted sandbox against the real DataFrame, inspecting the result or error (retrying on error up to a limit), and composing a plain-language answer — returning the answer, the exact code, and the result table.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id | string | URL | yes |
| question | string | user | yes |
| dataset_id | string | user/default | no |
| masked schema + stats | string | prepare_context | yes |
| prior execution_error | string | retry loop | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string | UI answer card |
| generated_code | string | UI collapsible code panel |
| result_table (real values) | object | UI table |
| run record | record | DB (`runs`) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | generate pandas; compose answer | node sets `error` → `handle_error`; run marked failed |
| Local sandbox | execute pandas on real frame | error captured → retry up to `max_attempts` (3); timeout → fatal |

## Business Rules
- Generated code must assign its answer to `result`, use only the provided frame name(s), `pd`/`np`, no imports, no file/network/OS access (AST-validated).
- On an execution error, feed the error back and regenerate, up to `max_attempts` (Phase 1: 3).
- Compute runs over the **full** dataset — never a sample.
- The LLM sees only the masked result preview; the user sees the real result.
- Every run is persisted (question + code + result preview + answer + timestamps).

## Success Criteria
- [ ] A question over a ≥5,000-row fixture returns a numeric answer equal to the independently-computed full-data ground truth (a value a sample would get wrong).
- [ ] The exact executed pandas is returned and shown collapsibly.
- [ ] When the first generated code raises, the agent fixes it and retries rather than failing (asserted by injecting a knowingly-hard question and checking `attempts > 1` succeeds).
- [ ] Generated code attempting an import or file access is rejected by the sandbox.
