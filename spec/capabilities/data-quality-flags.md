# Capability: Data-Quality Flags

_Phase 2._

## What It Does
Profiles the REAL DataFrame locally (nulls, duplicate rows, numeric outliers) and returns a list of data-quality flags so the user knows how much to trust the answer. Computation is 100% local (`src/analysis/quality.py`); the LLM is not required (may only be used to phrase a message, never to compute).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| DataFrame | pandas frame | in-memory store | yes |
| columns touched | list of strings | generated_code / result_table columns | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| data_quality_flags | list (contract below) | API response + `runs.data_quality_json` + UI badges |

## Contract
```jsonc
data_quality_flags = [
  { "level": "info" | "warn",
    "column": string | null,   // null = whole-frame flag (e.g. duplicate rows)
    "message": string }        // human-readable, e.g. "region has 42 nulls (3.1%)"
]
```

## Detection Rules (local)
- **Nulls:** per touched column, count + % of nulls; `warn` if > 5%, else `info`, skip if 0.
- **Duplicates:** whole-frame exact duplicate row count; `warn` if any, `column: null`.
- **Outliers:** per touched numeric column, count of values beyond 1.5×IQR; `info` (or `warn` if > 5%).

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (local pandas profiling) | null/dupe/outlier checks | omit flags, keep answer (degrade) |
| Gemini (optional) | phrase a message only | fall back to templated message |

## Business Rules
- Profiling runs locally on the real frame; only counts/percentages surface to the user, never raw values, and nothing un-masked reaches the LLM.
- Flags are scoped to the columns the answer depends on (plus whole-frame duplicates) to stay relevant.

## Success Criteria
- [ ] A fixture with injected nulls and duplicate rows raises ≥1 flag naming the affected column (or `null` for dupes) with a count in the message.
- [ ] A clean dataset raises no false `warn` flags.
