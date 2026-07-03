"""Deterministic ``chart_spec`` builder.

Every number in the spec is computed **locally** from the already-computed, real
``result_table`` (the aggregate the user already sees). The LLM's ONLY role is a
best-effort hint for the chart ``kind`` + which column is the category — it never
supplies a numeric value. If the LLM hint is missing/invalid, a pure deterministic
heuristic decides everything, so the chart is always best-effort and never blocks
the answer.

Privacy: the LLM sees only the masked result *shape* (column names + inferred
dtypes + row count) — never a cell value.

Contract: see spec/capabilities/chart-generation.md and spec/api.md.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"

_PANEL_SPLIT_THRESHOLD = 8  # >this many categories → split into Top/Bottom panels
_DATE_HINTS = ("date", "time", "month", "year", "day", "period", "week", "quarter", "timestamp", "dt")
_NONDIGITAL_HINTS = ("cheque", "check", "cash", "draft", "_dd", "dd_")
_UPPER_TOKENS = {"qr", "dd", "id", "pan", "upi", "imps", "neft", "rtgs", "kpi", "usd"}


# --- helpers ---------------------------------------------------------------

def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_date_name(name: str) -> bool:
    low = str(name).lower()
    return any(h in low for h in _DATE_HINTS)


def _is_nondigital(key: str) -> bool:
    low = str(key).lower()
    if low in ("dd", "cheque_dd", "cheque"):
        return True
    return any(h in low for h in _NONDIGITAL_HINTS)


def _nice_label(key: str) -> str:
    tokens = re.split(r"[\s_\-]+", str(key).strip())
    out = []
    for t in tokens:
        if not t:
            continue
        out.append(t.upper() if t.lower() in _UPPER_TOKENS else t.capitalize())
    return " ".join(out) or str(key)


def _num(v: Any) -> float:
    return float(v) if _is_number(v) else 0.0


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _extract_json(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else None


# --- column inference ------------------------------------------------------

def _infer(result_table: dict) -> tuple[list[str], list[list[Any]], list[dict]]:
    cols = [str(c) for c in result_table.get("columns", [])]
    rows = result_table.get("rows", []) or []
    info = []
    for i, c in enumerate(cols):
        vals = [r[i] for r in rows if i < len(r)]
        nonnull = [v for v in vals if v is not None]
        numeric = bool(nonnull) and all(_is_number(v) for v in nonnull)
        info.append({"name": c, "idx": i, "numeric": numeric, "date": _is_date_name(c)})
    return cols, rows, info


def _llm_roles(cols: list[str], info: list[dict], row_count: int, question: str, llm: Any) -> tuple[dict, dict]:
    """Best-effort LLM hint for kind + category column. Returns (hint, usage)."""
    usage = {"input_tokens": 0, "output_tokens": 0}
    if llm is None:
        return {}, usage
    try:
        shape = "\n".join(
            f"- {c['name']} ({'numeric' if c['numeric'] else 'categorical'})" for c in info
        )
        user = (
            f"Question: {question}\n\n"
            f"Result table shape ({row_count} rows):\n{shape}\n\n"
            "Choose the chart kind and column roles."
        )
        text, usage = llm.call_with_usage(user, system=_load_prompt("chart_role.md"))
        raw = _extract_json(text)
        return (json.loads(raw) if raw else {}), usage
    except Exception:  # noqa: BLE001 — best-effort only
        return {}, usage


# --- kind decision (deterministic; authoritative for gate stability) -------

def _decide_kind(info: list[dict], row_count: int) -> str | None:
    if row_count == 0:
        return None
    numeric = [c for c in info if c["numeric"]]
    text = [c for c in info if not c["numeric"]]
    non_date_text = [c for c in text if not c["date"]]
    has_date = any(c["date"] for c in info)
    ncells = len(info) * row_count

    if ncells == 1:
        return None
    if has_date and len(non_date_text) == 0 and len(numeric) >= 1:
        return "line"
    if len(numeric) >= 2 and (len(non_date_text) >= 1 or row_count > 1):
        return "dashboard"
    if len(non_date_text) >= 2 and len(numeric) == 1:
        return "dashboard"  # long → pivot to wide
    if len(non_date_text) >= 1 and len(numeric) == 1:
        return "bar"
    return None


# --- builders --------------------------------------------------------------

def _panels(categories: list[dict], category_label: str) -> list[dict]:
    categories = sorted(categories, key=lambda c: c["total"], reverse=True)
    axis = "% of total"
    if len(categories) > _PANEL_SPLIT_THRESHOLD:
        top = categories[:_PANEL_SPLIT_THRESHOLD]
        bottom = categories[_PANEL_SPLIT_THRESHOLD:]
        return [
            {"heading": f"Top {len(top)} {category_label} (by volume)", "axisLabel": axis, "categories": top},
            {"heading": f"Bottom {len(bottom)} {category_label}", "axisLabel": axis, "categories": bottom},
        ]
    return [{"heading": f"By {category_label} (share of total)", "axisLabel": axis, "categories": categories}]


def _build_dashboard(cols, rows, info, question, hint) -> dict | None:
    numeric = [c for c in info if c["numeric"]]
    non_date_text = [c for c in info if not c["numeric"] and not c["date"]]

    # Determine category column + series columns, materialising a wide table:
    #   agg[label] = {series_key: value}
    agg: dict[str, dict[str, float]] = {}
    series_keys: list[str] = []
    category_name = "category"

    if len(numeric) >= 2 and non_date_text:
        # wide: one category column + numeric series columns
        cat_idx = _pick_category(non_date_text, hint)
        category_name = cols[cat_idx]
        series_keys = [c["name"] for c in numeric]
        for r in rows:
            label = str(r[cat_idx])
            bucket = agg.setdefault(label, {})
            for c in numeric:
                bucket[c["name"]] = bucket.get(c["name"], 0.0) + _num(r[c["idx"]])
    elif len(numeric) == 1 and len(non_date_text) >= 2:
        # long → pivot: first text = category, second text = series
        cat_idx = non_date_text[0]["idx"]
        ser_idx = non_date_text[1]["idx"]
        val_idx = numeric[0]["idx"]
        category_name = cols[cat_idx]
        seen: list[str] = []
        for r in rows:
            label = str(r[cat_idx])
            skey = str(r[ser_idx])
            if skey not in seen:
                seen.append(skey)
            agg.setdefault(label, {})[skey] = agg.get(label, {}).get(skey, 0.0) + _num(r[val_idx])
        series_keys = seen
    elif len(numeric) >= 2:
        # no category column (e.g. groupby index was dropped) → rows are categories
        series_keys = [c["name"] for c in numeric]
        category_name = "row"
        for ridx, r in enumerate(rows):
            label = f"Row {ridx + 1}"
            agg[label] = {c["name"]: _num(r[c["idx"]]) for c in numeric}
    else:
        return None

    grand = sum(sum(b.values()) for b in agg.values())
    if grand <= 0:
        return None

    series = [{"key": k, "label": _nice_label(k)} for k in series_keys]
    categories = []
    for label, bucket in agg.items():
        segments = {k: round(bucket.get(k, 0.0) / grand, 6) for k in series_keys}
        total = round(sum(segments.values()), 6)
        categories.append({"label": label, "total": total, "segments": segments})

    charts = _panels(categories, category_name)

    # KPIs: per-series share + emphasized green digital total.
    kpis = []
    series_totals = {k: sum(b.get(k, 0.0) for b in agg.values()) for k in series_keys}
    for k in series_keys:
        kpis.append(
            {
                "label": _nice_label(k),
                "value": round(series_totals[k] / grand, 6),
                "format": "percent",
                "seriesKey": k,
                "emphasis": False,
            }
        )
    digital_keys = [k for k in series_keys if not _is_nondigital(k)]
    if digital_keys and len(digital_keys) < len(series_keys):
        digital_share = sum(series_totals[k] for k in digital_keys) / grand
        kpis.insert(
            0,
            {
                "label": "Digital total",
                "value": round(digital_share, 6),
                "format": "percent",
                "seriesKey": None,
                "emphasis": True,
            },
        )

    return {
        "kind": "dashboard",
        "title": f"{_nice_label(category_name)} breakdown",
        "subtitle": f"{len(categories)} {category_name} · share of total",
        "series": series,
        "kpis": kpis,
        "charts": charts,
    }


def _pick_category(non_date_text: list[dict], hint: dict) -> int:
    want = str(hint.get("category", "")).strip().lower() if hint else ""
    if want:
        for c in non_date_text:
            if c["name"].lower() == want:
                return c["idx"]
    return non_date_text[0]["idx"]


def _build_line(cols, rows, info) -> dict | None:
    numeric = [c for c in info if c["numeric"]]
    date_cols = [c for c in info if c["date"]]
    if not numeric:
        return None
    x_col = date_cols[0] if date_cols else next((c for c in info if not c["numeric"]), info[0])
    x_idx = x_col["idx"]
    series = [c for c in numeric if c["idx"] != x_idx]
    if not series:
        return None

    points = []
    multi = len(series) > 1
    for c in series:
        for r in rows:
            xv = r[x_idx]
            x = xv if _is_number(xv) else str(xv)
            pt = {"x": x, "y": _num(r[c["idx"]])}
            if multi:
                pt["series"] = _nice_label(c["name"])
            points.append(pt)
    if not points:
        return None

    return {
        "kind": "line",
        "title": f"{_nice_label(series[0]['name'])} over {_nice_label(cols[x_idx])}",
        "subtitle": f"{len(rows)} points",
        "series": [{"key": c["name"], "label": _nice_label(c["name"])} for c in series],
        "kpis": [],
        "points": points,
    }


def _build_bar(cols, rows, info) -> dict | None:
    numeric = [c for c in info if c["numeric"]]
    non_date_text = [c for c in info if not c["numeric"] and not c["date"]]
    if not numeric or not non_date_text:
        return None
    cat_idx = non_date_text[0]["idx"]
    m = numeric[0]
    category_name = cols[cat_idx]
    agg: dict[str, float] = {}
    for r in rows:
        label = str(r[cat_idx])
        agg[label] = agg.get(label, 0.0) + _num(r[m["idx"]])
    grand = sum(agg.values())
    if grand <= 0:
        return None
    key = m["name"]
    categories = [
        {"label": lbl, "total": round(v / grand, 6), "segments": {key: round(v / grand, 6)}}
        for lbl, v in agg.items()
    ]
    return {
        "kind": "bar",
        "title": f"{_nice_label(key)} by {_nice_label(category_name)}",
        "subtitle": f"{len(categories)} {category_name} · share of total",
        "series": [{"key": key, "label": _nice_label(key)}],
        "kpis": [
            {"label": _nice_label(key), "value": 1.0, "format": "percent", "seriesKey": key, "emphasis": True}
        ],
        "charts": _panels(categories, category_name),
    }


# --- entry point -----------------------------------------------------------

def build_chart_spec(result_table: dict | None, question: str, *, llm: Any = None) -> tuple[dict | None, dict]:
    """Build a ``chart_spec`` from the real ``result_table``.

    Returns ``(spec_or_None, usage)`` where ``usage`` is the LLM token usage from
    the (optional) role hint call, so the caller can fold it into the run cost.
    """
    usage = {"input_tokens": 0, "output_tokens": 0}
    if not result_table:
        return None, usage
    cols, rows, info = _infer(result_table)
    if not cols or not rows:
        return None, usage

    kind = _decide_kind(info, len(rows))
    if kind is None:
        return None, usage

    # Best-effort LLM hint (also surfaces token cost); heuristic stays authoritative.
    hint, usage = _llm_roles(cols, info, len(rows), question, llm)

    if kind == "line":
        return _build_line(cols, rows, info), usage
    if kind == "bar":
        return _build_bar(cols, rows, info), usage
    return _build_dashboard(cols, rows, info, question, hint), usage
