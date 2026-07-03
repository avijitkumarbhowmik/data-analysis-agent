# Capability: Chart Generation

_Phase 2._

## What It Does
Turns a computed `result_table` into a rich, self-contained **analytics dashboard** (KPI stat tiles + stacked horizontal % bar charts) — or a line/bar chart — by emitting a single `chart_spec` JSON object that the frontend renders. The default look for a categorical/share/mix question is the dashboard. The LLM's ONLY role is choosing the chart **kind** and mapping masked columns to **roles** (category / series / measure); all numbers come from the already-computed `result_table`, which is shaped into the spec on the **backend** (`src/analysis/charts.py`).

## Privacy
`result_table` is the aggregate the agent computed locally and already returns to the user, so shaping it into `chart_spec` server-side is privacy-safe. The LLM sees only the **masked result shape** (column names/dtypes, row count) to pick `kind` + roles — never raw rows, never un-masked PII.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| result_table (real, computed) | object `{columns, rows}` | execute_code node | yes |
| question | string | user | yes |
| masked result shape | string | prepare/enrich (column names + dtypes only) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | JSON (contract below) or `null` | `enrich` node → API response + `runs.chart_spec_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | from the masked result shape, choose `kind` ∈ {dashboard,line,bar} + role mapping (which column is category, which are series, which is measure) | fall back to a deterministic heuristic (>=1 category col + >=2 numeric series → dashboard; a datetime/ordered x + 1 numeric → line; else bar; single scalar → null). Chart is best-effort; the answer is never blocked. |

## The `chart_spec` Contract (backend emits, frontend renders — both build to THIS)

```jsonc
chart_spec = null            // when the result is a single scalar / not chartable
// OR:
{
  "kind": "dashboard" | "line" | "bar",
  "title": string,
  "subtitle": string,                                  // grey caption under the title
  "series": [ { "key": string, "label": string } ],    // ordered; frontend assigns color by INDEX from the fixed palette
  "kpis": [
    { "label": string,
      "value": number,                                 // fraction 0..1 when format=percent, else a raw count
      "format": "percent" | "number",
      "seriesKey": string | null,                      // ties the tile accent color to a series; null = neutral
      "emphasis": boolean }                            // true → the emphasized green "total" tile
  ],
  "charts": [                                           // at most 2 panels (split top/bottom when many categories)
    { "heading": string,                               // e.g. "Top 8 regions (by volume)"
      "axisLabel": string,                             // x-axis label, e.g. "% of total fee receipts"
      "categories": [
        { "label": string,                            // a category (region/branch) — y-axis row
          "total": number,                             // fraction 0..1 = this category's share of the whole (bar length)
          "segments": { "<seriesKey>": number, ... } } // each series' contribution to this category (fractions 0..1)
      ] }
  ],
  // for kind == "line" ONLY, replace `charts` with:
  "points": [ { "x": string | number, "y": number, "series"?: string } ]
}
```

### Fixed series color palette (works in light AND dark themes — ONE cohesive system)
Frontend assigns color by `series[]` index; this palette is authoritative and shared with `ui.md`:

| Index | Series (default domain) | Color |
|-------|-------------------------|-------|
| 0 | Dynamic QR | `#1e40af` (dark blue) |
| 1 | Initiate Link | `#ea580c` (orange) |
| 2 | Static QR | `#64748b` (slate/grey) |
| 3 | Cheque + DD | `#b91c1c` (dark red) |
| — | emphasized "total" KPI tile | `#16a34a` (green) |

Gridlines: `slate-200` (light) / `slate-700` (dark). No external CDNs; styling is self-contained.

## Business Rules
- `kpis[].value` and `charts[].categories[].total` and `segments` values are **fractions of the whole (0..1)**, rendered as `%` by the frontend.
- `categories` are sorted **descending by `total`**; when there are many categories, split into **at most two** panels (e.g. Top N / Bottom N).
- `series` order is stable and drives color assignment; the frontend never re-derives colors from labels.
- Numbers are formatted via the existing `frontend/src/lib/formatNumber.ts` (17.8%, comma-grouped counts, ≤2 decimals) — **reuse, do not duplicate**.
- A single-scalar / non-chartable result yields `chart_spec = null`; the answer still returns.
- Backend computes every number in the spec from `result_table`; the LLM never supplies a numeric value.

## Success Criteria
- [ ] A mix/share question ("show the payment-mode mix by region") over the regional payment-mode fixture yields `chart_spec.kind == "dashboard"` with ≥1 `kpis` entry and ≥1 `charts` panel whose `categories[].segments` is non-empty.
- [ ] An "…over time" question yields `chart_spec.kind == "line"` with a non-empty `points` array.
- [ ] A single-number answer yields `chart_spec == null` and still returns the answer.
- [ ] All `kpis[].value` and `categories[].total` are in `[0,1]`; `categories` are sorted descending by `total`; at most 2 panels.
