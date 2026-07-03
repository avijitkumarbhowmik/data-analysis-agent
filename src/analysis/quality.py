"""Local data-quality profiling — nulls, duplicate rows, numeric outliers.

100% local pandas over the REAL frame; no LLM required. Only counts/percentages
surface to the user — never a raw value. Scoped to the columns the answer touched,
plus a whole-frame duplicate-row check.

Contract (see spec/capabilities/data-quality-flags.md):
    [ { "level": "info"|"warn", "column": str|None, "message": str } ]
"""

from __future__ import annotations

import pandas as pd

_NULL_WARN_PCT = 5.0
_OUTLIER_WARN_PCT = 5.0


def _pct(part: int, whole: int) -> float:
    return (part / whole * 100.0) if whole else 0.0


def profile(df: pd.DataFrame, touched_columns: list[str] | None = None) -> list[dict]:
    """Profile ``df`` and return data-quality flags.

    ``touched_columns`` scopes the null/outlier checks to the columns the answer
    depended on; when empty/None, all columns are profiled. Duplicate-row detection
    is always whole-frame.
    """
    flags: list[dict] = []
    if df is None or len(df) == 0:
        return flags

    n = int(len(df))

    # --- whole-frame duplicate rows -------------------------------------
    try:
        dupes = int(df.duplicated().sum())
        if dupes > 0:
            flags.append(
                {
                    "level": "warn",
                    "column": None,
                    "message": f"{dupes} exact duplicate rows ({_pct(dupes, n):.1f}% of {n})",
                }
            )
    except Exception:  # noqa: BLE001 — degrade, keep the answer
        pass

    # --- per-column nulls + outliers ------------------------------------
    cols = [c for c in (touched_columns or []) if c in df.columns]
    if not cols:
        cols = [str(c) for c in df.columns]

    for col in cols:
        try:
            series = df[col]
        except Exception:  # noqa: BLE001
            continue

        # nulls
        try:
            nulls = int(series.isna().sum())
            if nulls > 0:
                pct = _pct(nulls, n)
                level = "warn" if pct > _NULL_WARN_PCT else "info"
                flags.append(
                    {
                        "level": level,
                        "column": col,
                        "message": f"{col} has {nulls} nulls ({pct:.1f}%)",
                    }
                )
        except Exception:  # noqa: BLE001
            pass

        # outliers (numeric only, 1.5x IQR)
        try:
            if pd.api.types.is_numeric_dtype(series):
                s = series.dropna()
                if len(s) >= 4:
                    q1 = s.quantile(0.25)
                    q3 = s.quantile(0.75)
                    iqr = q3 - q1
                    if iqr > 0:
                        lo = q1 - 1.5 * iqr
                        hi = q3 + 1.5 * iqr
                        out = int(((s < lo) | (s > hi)).sum())
                        if out > 0:
                            pct = _pct(out, n)
                            level = "warn" if pct > _OUTLIER_WARN_PCT else "info"
                            flags.append(
                                {
                                    "level": level,
                                    "column": col,
                                    "message": f"{col} has {out} outliers beyond 1.5x IQR ({pct:.1f}%)",
                                }
                            )
        except Exception:  # noqa: BLE001
            pass

    return flags
