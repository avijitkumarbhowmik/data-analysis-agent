# Capability: Live Query Feedback (Streaming + Cost)

_Phase 2._

## What It Does
Streams the answer as it is composed via Server-Sent Events (SSE) and reports an estimated USD cost per query, so the user gets immediate progressive feedback and cost transparency. If streaming fails, the frontend transparently falls back to the non-streaming `/ask`, which returns the **same fully-enriched payload**.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| workspace_id, question | string | user | yes |
| dataset_id | string | user/default | no |
| token usage | object `{input_tokens, output_tokens}` | Gemini response metadata | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer deltas | SSE `event: delta`, `data: {"text":"..."}` | UI progressive render |
| final payload | SSE `event: final`, `data:` = full `/ask` JSON (incl. chart_spec, data_quality_flags, followups, cost) | UI |
| cost `{input_tokens, output_tokens, usd}` | object | UI cost badge + `runs.cost_json` |

## SSE Contract (`POST /workspaces/{id}/ask/stream`)
- `Content-Type: text/event-stream`.
- Zero or more `event: delta` frames, each `data: {"text": "<answer fragment>"}`, streamed as the answer composes.
- Exactly one terminal `event: final` frame whose `data` is the **same JSON object** the non-streaming `/ask` returns under `data` (`run_id`, `answer`, `generated_code`, `result_table`, `status`, `attempts`, `chart_spec`, `data_quality_flags`, `followups`, `cost`).
- On any server error mid-stream, emit `event: error` with `data: {"message": "..."}` and close; the frontend then retries the non-streaming `/ask`.

## Cost Contract
`cost = { "input_tokens": int, "output_tokens": int, "usd": float }`, where
`usd = input_tokens/1000 * AGENT_GEMINI_INPUT_USD_PER_1K + output_tokens/1000 * AGENT_GEMINI_OUTPUT_USD_PER_1K`.
Both rates are new settings fields with sensible non-zero defaults (see `architecture.md` / `settings.py`). The LLM client/provider MUST surface token usage from the Gemini response so `usd > 0`.

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (streaming) | stream answer tokens + report token usage | frontend falls back to non-streaming `/ask` (degrade) |

## Business Rules
- Streaming carries only masked content; the final event includes the real code + result + enrichments (same privacy boundary as `/ask`).
- Cost is summed across all Gemini calls in the run (generate_code retries + compose + enrich role/followup calls).
- The non-streaming `/ask` ALSO returns `chart_spec`, `data_quality_flags`, `followups`, `cost` so the fallback path is fully featured.

## Success Criteria
- [ ] `/ask/stream` emits ≥1 `event: delta` then exactly one `event: final` carrying `chart_spec`, `data_quality_flags`, `followups`, and `cost`.
- [ ] The returned `cost.usd > 0` and token counts match the model response.
- [ ] Killing the stream mid-flight causes the frontend to complete the query via non-streaming `/ask` with an identical enriched result.
