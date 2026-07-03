# Capability: Conversation Memory

_Phase 2. (Phase 1 is single-turn by design; see roadmap Assumed note.)_

## What It Does
Carries conversation history across turns within a workspace so follow-up questions resolve references ("those regions", "that total", "now filter to Mumbai") using prior context. The runner hydrates `messages` from the workspace's recent completed runs and passes them into graph state; `generate_code` and `compose_answer` include the prior turns in their prompts.

## Data source (NO new table)
Reads the **existing `runs` table** — the last N (default 5) completed runs for the workspace, ordered oldest→newest, each contributing a `{role:"user", content: question}` and a `{role:"assistant", content: answer}` message. No migration; `messages` already exists in `src/graph/state.py`.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| messages (prior turns) | list `[{role, content}]` | runner (hydrated from recent runs) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| context-aware answer | string | UI thread |
| new run row | record | `runs` table (becomes memory for the next turn) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read last N completed runs to hydrate `messages` | fall back to single-turn (empty history, degrade) |
| Gemini | generate/compose with history in context | node error → handle_error |

## Ownership note (coordination)
`backend-history-conversation` owns the runner hydration AND the memory-injection wiring **inside `generate_code` + `compose_answer` node bodies**. `backend-enrich` edits ONLY the `enrich` node body. This split keeps `src/graph/nodes.py` conflict-free.

## Business Rules
- History is scoped per workspace and bounded to the most recent N (default 5) turns; only completed runs contribute.
- Only masked context (never raw rows) is carried into prompts.
- History survives restart (rehydrated from the `runs` table).

## Success Criteria
- [ ] A second turn that refers to the first ("filter that to X" / "those regions") produces a correct answer using the earlier turn's subject.
- [ ] History is scoped to the workspace — another workspace's turns do not leak in.
