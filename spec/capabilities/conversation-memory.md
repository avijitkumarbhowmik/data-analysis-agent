# Capability: Conversation Memory

_Phase 2. (Phase 1 is single-turn by design; see roadmap Assumed note.)_

## What It Does
Carries conversation history across turns within a workspace so follow-up questions resolve references ("now filter that to Mumbai", "what about last quarter?") using prior context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| messages (prior turns) | list `[{role, content}]` | runner (hydrated from recent runs) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| context-aware answer | string | UI thread |
| updated messages | list | state / next turn |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read recent runs to hydrate history | fall back to single-turn (degrade) |
| Gemini | generate/compose with history in context | node error → handle_error |

## Business Rules
- History is scoped per workspace and bounded to the most recent N turns.
- Only masked context (never raw rows) is carried into prompts.
- History survives restart (rehydrated from the `runs` table).

## Success Criteria
- [ ] A second turn that refers to the first ("filter that to X") produces a correct answer using the earlier turn's subject.
- [ ] History is scoped to the workspace — another workspace's turns do not leak in.
