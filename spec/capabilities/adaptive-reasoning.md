# Capability: Adaptive Reasoning (Clarify + Plan + Iterate)

_Phase 3. (Phase 1 has the retry-on-error loop; this adds clarify, plan, and deeper iteration.)_

## What It Does
Scales reasoning depth to the question: asks a clarifying question when the request is ambiguous, produces a plan-then-execute flow for complex questions, and iterates the code loop with a higher step limit until the result is right.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| schema_summary + notes | string | prepare_context | yes |
| messages | list | conversation memory | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| clarifying_question | string | UI prompt (Human-in-the-Loop) |
| plan | string | UI plan panel + `runs.plan` |
| final answer (deeper iterate) | string | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | clarify decision; plan; code loop | node error → handle_error |
| Local sandbox | execute each step | error → retry up to raised `max_attempts` |

## Business Rules
- If the question is not answerable against the schema, the `clarify` node returns a question and ends the run (`needs_clarification`) instead of guessing.
- Complex questions get a numbered plan and a higher `max_attempts`; simple questions skip planning (adaptive, not always-on — avoids latency).
- Patterns: Planning (#6), Human-in-the-Loop (#13), ReAct (#17) per `harness/patterns/agentic-ai.md`.

## Success Criteria
- [ ] A deliberately ambiguous question returns a clarifying question and does not run code.
- [ ] A complex multi-step question produces a plan and a correct answer within the raised step limit.
- [ ] A simple question still answers in one pass (no unnecessary planning).
