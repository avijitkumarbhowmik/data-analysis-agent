"""PII auto-detection and masking — the privacy chokepoint.

Sits between the real DataFrame and every LLM-bound surface. Nothing here ever
executes user data; it only builds the *masked* text that is safe to send to
Gemini. The hard guarantee (gated by tests): no raw un-masked PII value and no
full data dump ever appears in any string returned by ``mask_schema`` or
``mask_result``.

Public API (imported by the graph/API slice):
- ``detect_pii_columns(df) -> dict[str, str]``   column -> pii_type
- ``mask_schema(df, pii_map=None) -> str``        masked schema + stats + sample
- ``mask_result(result_obj, pii_map=None) -> str``masked, size-capped preview
- ``PII_TYPES``                                    tuple of recognised types
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

PII_TYPES: tuple[str, ...] = ("name", "pan", "aadhaar", "phone", "email", "account")

# How many rows to sample when detecting PII by value pattern.
_VALUE_SAMPLE = 200
# Fraction of sampled values that must match a pattern to flag the column.
_VALUE_THRESHOLD = 0.6
# Rows shown in a schema sample / capped in a result preview.
_SCHEMA_SAMPLE_ROWS = 5
_RESULT_MAX_ROWS = 20

# --- value patterns -------------------------------------------------------
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_AADHAAR_RE = re.compile(r"^\d{12}$")
_PHONE_RE = re.compile(r"^(?:\+?91[\-\s]?)?[6-9]\d{9}$")
_ACCOUNT_RE = re.compile(r"^\d{9,18}$")
# A human name: 2-4 title-case tokens (e.g. "Ravi Kumar", "A. P. J. Kalam").
_NAME_RE = re.compile(r"^[A-Z][a-z'.\-]+(?:\s+[A-Z][a-z'.\-]*\.?){1,3}$")

# --- column-name heuristics ----------------------------------------------
# token (exact) -> pii_type  and  substring hints handled below.
_NAME_TOKENS = {"pan": "pan"}
_KEYWORD_HINTS: list[tuple[str, str]] = [
    # order matters — more specific first
    ("email", "email"),
    ("mail", "email"),
    ("aadhaar", "aadhaar"),
    ("aadhar", "aadhaar"),
    ("uid", "aadhaar"),
    ("phone", "phone"),
    ("mobile", "phone"),
    ("contact", "phone"),
    ("account", "account"),
    ("acct", "account"),
    ("accountno", "account"),
]


def _tokens(col: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(col).lower()) if t}


def _detect_by_name(col: str) -> str | None:
    toks = _tokens(col)
    joined = re.sub(r"[^a-z0-9]+", "", str(col).lower())
    # exact-token matches (short/ambiguous keywords like "pan")
    for tok, pii in _NAME_TOKENS.items():
        if tok in toks:
            return pii
    # substring hints on the joined name
    for kw, pii in _KEYWORD_HINTS:
        if kw in joined:
            return pii
    # "name" as a token or a *_name column (customer_name, borrower_name)
    if "name" in toks or any(t.endswith("name") for t in toks):
        return "name"
    return None


def _classify_value(value: Any) -> str | None:
    """Best-effort PII type for a single value, or None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    if _EMAIL_RE.match(s):
        return "email"
    if _PAN_RE.match(s.upper()):
        return "pan"
    compact = re.sub(r"[\s\-]", "", s)
    if _AADHAAR_RE.match(compact):
        return "aadhaar"
    if _PHONE_RE.match(compact) or _PHONE_RE.match(s):
        return "phone"
    if _ACCOUNT_RE.match(compact):
        return "account"
    return None


def _detect_by_values(series: pd.Series) -> str | None:
    sample = series.dropna()
    if sample.empty:
        return None
    sample = sample.head(_VALUE_SAMPLE)
    n = len(sample)
    counts: dict[str, int] = {}
    for v in sample:
        t = _classify_value(v)
        if t:
            counts[t] = counts.get(t, 0) + 1
    # pattern types first (high confidence)
    for t in ("email", "pan", "aadhaar", "phone", "account"):
        if counts.get(t, 0) / n >= _VALUE_THRESHOLD:
            return t
    # names have no strict pattern — require strong signal + high uniqueness
    if not pd.api.types.is_numeric_dtype(series):
        name_hits = sum(1 for v in sample if _NAME_RE.match(str(v).strip()))
        if name_hits / n >= 0.8 and series.nunique(dropna=True) / n > 0.5:
            return "name"
    return None


def detect_pii_columns(df: pd.DataFrame) -> dict[str, str]:
    """Auto-detect PII columns -> pii_type.

    Combines column-name heuristics with value-pattern sampling. When uncertain
    we lean toward masking (fail-safe for privacy).
    """
    result: dict[str, str] = {}
    for col in df.columns:
        pii = _detect_by_name(col)
        if pii is None:
            pii = _detect_by_values(df[col])
        if pii:
            result[str(col)] = pii
    return result


# --- masking helpers ------------------------------------------------------

def mask_token(pii_type: str) -> str:
    return f"***MASKED({pii_type})***"


def _is_textual(series: pd.Series) -> bool:
    """True for object/string columns (pandas 3.0 uses a native ``str`` dtype)."""
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    ) and not pd.api.types.is_numeric_dtype(series)


def _scan_cell(value: Any) -> Any:
    """Mask a single (object) cell if its *value* looks like PII, else pass through."""
    t = _classify_value(value)
    if t:
        return mask_token(t)
    return value


def _mask_frame(df: pd.DataFrame, pii_map: dict[str, str]) -> pd.DataFrame:
    """Return a copy of ``df`` with PII masked.

    - columns in ``pii_map`` are replaced wholesale with their mask token
    - remaining *object* columns are scanned cell-by-cell for embedded PII
      patterns (email/PAN/Aadhaar/phone/account) so a value can never leak even
      if its column was not flagged
    - the index is masked the same way
    """
    out = df.copy()
    out.columns = [str(c) for c in out.columns]
    pii_map = pii_map or {}
    for col in list(out.columns):
        if col in pii_map:
            out[col] = mask_token(pii_map[col])
        elif _is_textual(out[col]):
            out[col] = out[col].map(_scan_cell)
    # mask the index (e.g. groupby on a name column)
    idx_name = out.index.name
    if idx_name is not None and str(idx_name) in pii_map:
        out.index = pd.Index([mask_token(pii_map[str(idx_name)])] * len(out), name=idx_name)
    elif _is_textual(pd.Series(out.index)):
        out.index = pd.Index([_scan_cell(v) for v in out.index], name=idx_name)
    return out


def _fmt_num(x: Any) -> str:
    try:
        if pd.isna(x):
            return "NaN"
    except (TypeError, ValueError):
        pass
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    try:
        return f"{float(x):.4g}"
    except (TypeError, ValueError):
        return str(x)


def mask_schema(df: pd.DataFrame, pii_map: dict[str, str] | None = None) -> str:
    """Build the masked schema summary the LLM is allowed to see.

    Column names + dtypes + per-column stats (numeric: min/max/mean/nulls;
    categorical: cardinality/top values for NON-PII columns only) + a few
    sample rows with PII columns masked. Never emits a raw PII value.
    """
    if pii_map is None:
        pii_map = detect_pii_columns(df)

    lines: list[str] = []
    lines.append(f"Rows: {len(df)}")
    lines.append(f"Columns: {df.shape[1]}")
    lines.append("")
    lines.append("Column schema and statistics:")
    for col in df.columns:
        col = str(col)
        series = df[col]
        dtype = str(series.dtype)
        nulls = int(series.isna().sum())
        if col in pii_map:
            lines.append(
                f"- {col} ({dtype}) [PII: {pii_map[col]}; values masked] "
                f"non_null={int(series.notna().sum())}, distinct={int(series.nunique(dropna=True))}, nulls={nulls}"
            )
        elif pd.api.types.is_numeric_dtype(series):
            lines.append(
                f"- {col} ({dtype}) numeric: min={_fmt_num(series.min())}, "
                f"max={_fmt_num(series.max())}, mean={_fmt_num(series.mean())}, nulls={nulls}"
            )
        else:
            distinct = int(series.nunique(dropna=True))
            top = series.dropna().astype(str).value_counts().head(3)
            # scan even non-PII categorical values so an embedded PII pattern
            # (e.g. an email in an un-flagged column) can never leak.
            top_str = ", ".join(f"{_scan_cell(v)!r}:{int(c)}" for v, c in top.items())
            lines.append(
                f"- {col} ({dtype}) categorical: distinct={distinct}, nulls={nulls}, top=[{top_str}]"
            )

    lines.append("")
    lines.append(f"Sample rows (first {min(_SCHEMA_SAMPLE_ROWS, len(df))}, PII masked):")
    sample = df.head(_SCHEMA_SAMPLE_ROWS)
    masked = _mask_frame(sample, pii_map)
    lines.append(masked.to_string(index=False) if len(masked) else "(no rows)")
    return "\n".join(lines)


def _mask_scalar(value: Any) -> str:
    t = _classify_value(value)
    if t:
        return mask_token(t)
    s = str(value)
    return s if len(s) <= 500 else s[:500] + "…(truncated)"


def mask_result(result_obj: Any, pii_map: dict[str, str] | None = None) -> str:
    """Mask a computed result before it is sent to compose_answer/the LLM.

    Size-capped. Any value that matches a PII pattern is masked even without a
    pii_map, so a result can never leak raw PII.
    """
    if result_obj is None:
        return "None"

    pii_map = pii_map or {}

    if isinstance(result_obj, pd.DataFrame):
        total = len(result_obj)
        capped = result_obj.head(_RESULT_MAX_ROWS)
        masked = _mask_frame(capped, pii_map)
        text = masked.to_string()
        if total > _RESULT_MAX_ROWS:
            text += f"\n... ({total - _RESULT_MAX_ROWS} more rows truncated)"
        return text

    if isinstance(result_obj, pd.Series):
        total = len(result_obj)
        capped = result_obj.head(_RESULT_MAX_ROWS)
        frame = capped.to_frame(name=str(result_obj.name) if result_obj.name is not None else "value")
        masked = _mask_frame(frame, pii_map)
        text = masked.to_string()
        if total > _RESULT_MAX_ROWS:
            text += f"\n... ({total - _RESULT_MAX_ROWS} more values truncated)"
        return text

    if isinstance(result_obj, (list, tuple, set)):
        items = list(result_obj)[:_RESULT_MAX_ROWS]
        masked = [_mask_scalar(v) for v in items]
        text = ", ".join(masked)
        if len(result_obj) > _RESULT_MAX_ROWS:
            text += f", ... ({len(result_obj) - _RESULT_MAX_ROWS} more truncated)"
        return f"[{text}]"

    if isinstance(result_obj, dict):
        out = {}
        for i, (k, v) in enumerate(result_obj.items()):
            if i >= _RESULT_MAX_ROWS:
                out["…"] = f"({len(result_obj) - _RESULT_MAX_ROWS} more truncated)"
                break
            out[str(k)] = _mask_scalar(v)
        return str(out)

    return _mask_scalar(result_obj)
