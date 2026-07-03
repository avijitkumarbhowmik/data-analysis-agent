# Capability: Data-Quality Flags

_Phase 2._

## What It Does
Proactively flags data-quality issues (nulls, duplicates, outliers) relevant to the columns a question touches, so the user knows how much to trust the answer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| DataFrame | pandas frame | in-memory store | yes |
| columns touched | list | generated_code / result | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| data_quality_flags | list `[{column, issue, count}]` | UI badges + `runs.data_quality_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (local pandas profiling) | null/dupe/outlier checks | omit flags, keep answer (degrade) |

## Business Rules
- Profiling runs locally on the real frame; no raw values leave the machine — only counts/summaries are shown to the user (never sent to the LLM un-masked).
- Flags are scoped to the columns the answer depends on to stay relevant.

## Success Criteria
- [ ] A fixture with injected nulls and duplicate rows raises at least one flag naming the affected column and count.
- [ ] A clean dataset raises no false flags.
