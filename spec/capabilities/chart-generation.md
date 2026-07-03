# Capability: Chart Generation

_Phase 2._

## What It Does
Produces an interactive chart when a question's result is visualizable (trend, distribution, breakdown), by emitting a JSON chart spec from the computed result that the frontend renders.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| result_table (real) | object | execute_code | yes |
| question | string | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | JSON `{type, x, y, series}` | UI chart area + `runs.chart_spec_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | choose chart type/axes from masked result shape | omit chart, keep answer (degrade) |

## Business Rules
- Chart data comes from the real computed result; only shape/column names (PII-masked) inform the LLM's chart-type choice.
- No server-side plotting — a spec is emitted; the client renders it.
- A non-chartable result (single scalar) yields no chart.

## Success Criteria
- [ ] A "…over time" question yields a chart_spec with a time x-axis and numeric series.
- [ ] A single-number answer yields no chart_spec and still returns the answer.
