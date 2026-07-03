# Capability: Live Query Feedback (Streaming + Cost)

_Phase 2._

## What It Does
Streams the answer as it is composed (SSE) and shows an estimated cost per query, so the user gets immediate feedback and cost transparency.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id, question | string | user | yes |
| token usage | object | Gemini response metadata | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| streamed answer deltas | SSE events | UI (progressive render) |
| cost `{input_tokens, output_tokens, usd}` | object | UI badge + `runs.cost_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (streaming) | stream answer + report token usage | fall back to non-streaming `/ask` (degrade) |

## Business Rules
- Cost is computed from reported token counts × the `gemini-2.5-flash` rate (configurable).
- Streaming carries only masked content; the final event includes code + result + enrichments.

## Success Criteria
- [ ] `/ask/stream` emits progressive answer events then a final event with code + result.
- [ ] The returned cost has `usd > 0` and token counts matching the model response.
