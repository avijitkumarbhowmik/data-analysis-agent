"""Phase 2 `backend-enrich` gate — real Gemini via .env, SQLite.

Exercises the REAL `enrich` node directly over the regional payment-mode fixture:
chart_spec (dashboard / line / null), data-quality flags (local, hard assert),
follow-ups (>=2), and per-query cost (usd > 0, hard assert). Chart numbers are all
derived locally from the real result_table; the LLM only hints kind/roles.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "regional_payment_modes.csv"
MODES = ["dynamic_qr", "initiate_link", "static_qr", "cheque_dd"]


def _load(ws: str, source) -> pd.DataFrame:
    from analysis import store
    store.load_csv(ws, str(source) if isinstance(source, Path) else source, "df")
    return store.get_frames(ws)["df"]


def _state(ws: str, question: str, result, df: pd.DataFrame, code: str = "") -> dict:
    from analysis import pii
    from graph import nodes
    pii_map = {}
    return {
        "run_id": "t-run",
        "workspace_id": ws,
        "question": question,
        "result_table": nodes.serialize_result(result),
        "execution_result": pii.mask_result(result, pii_map),
        "schema_summary": pii.mask_schema(df, pii_map),
        "generated_code": code or "result = df",
        "attempts": 1,
    }


# --- mix/share → dashboard + kpis + segmented panel + cost + followups -----

@pytest.mark.usefixtures("_require_llm_key")
def test_mix_question_yields_dashboard_with_segments(tmp_path):
    from graph import nodes
    df = _load("ws-mix", FIXTURE)
    result = df.groupby("region")[MODES].sum().reset_index()

    out = nodes.enrich(_state(
        "ws-mix",
        "show the payment-mode mix by region",
        result,
        df,
        code="result = df.groupby('region')[['dynamic_qr','initiate_link','static_qr','cheque_dd']].sum().reset_index()",
    ))

    spec = out["chart_spec"]
    assert spec is not None
    assert spec["kind"] == "dashboard", spec
    assert len(spec["kpis"]) >= 1
    assert len(spec["charts"]) >= 1
    panel = spec["charts"][0]
    assert panel["categories"], "panel must carry categories"
    seg = panel["categories"][0]["segments"]
    assert seg and any(v > 0 for v in seg.values()), seg
    # fractions in [0,1], sorted desc by total
    totals = [c["total"] for c in panel["categories"]]
    assert all(0.0 <= t <= 1.0 for t in totals)
    assert totals == sorted(totals, reverse=True)
    # an emphasized (green) digital-total KPI is present
    assert any(k["emphasis"] for k in spec["kpis"])

    # cost is a HARD assertion (real token usage → usd > 0)
    assert out["cost"] is not None
    assert out["cost"]["usd"] > 0, out["cost"]
    assert out["cost"]["input_tokens"] > 0

    # >=2 grounded follow-ups
    assert len(out["followups"]) >= 2, out["followups"]


# --- time series → line ----------------------------------------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_time_series_question_yields_line():
    from graph import nodes
    df = _load("ws-line", FIXTURE)
    result = df.groupby("payment_date")["dynamic_qr"].sum()

    out = nodes.enrich(_state(
        "ws-line",
        "show total dynamic_qr volume over time by payment_date",
        result,
        df,
        code="result = df.groupby('payment_date')['dynamic_qr'].sum()",
    ))
    spec = out["chart_spec"]
    assert spec is not None
    assert spec["kind"] == "line", spec
    assert spec["points"], "line chart must have points"


# --- single scalar → null chart --------------------------------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_single_scalar_yields_null_chart():
    from graph import nodes
    df = _load("ws-scalar", FIXTURE)
    result = int(df["dynamic_qr"].sum())

    out = nodes.enrich(_state(
        "ws-scalar",
        "what is the total dynamic_qr volume across all regions?",
        result,
        df,
        code="result = df['dynamic_qr'].sum()",
    ))
    assert out["chart_spec"] is None
    # cost still accrues via the follow-up call
    assert out["cost"]["usd"] > 0


# --- nulls + duplicate rows → data-quality flags (HARD, non-LLM) -----------

@pytest.mark.usefixtures("_require_llm_key")
def test_nulls_and_dupes_raise_quality_flags(tmp_path):
    from graph import nodes
    clean = pd.read_csv(FIXTURE)
    messy = clean.copy()
    messy.loc[messy.index[:200], "dynamic_qr"] = np.nan          # injected nulls
    messy = pd.concat([messy, messy.head(50)], ignore_index=True)  # duplicate rows
    messy_path = tmp_path / "messy.csv"
    messy.to_csv(messy_path, index=False)

    df = _load("ws-messy", messy_path)
    result = df.groupby("region")["dynamic_qr"].sum()

    out = nodes.enrich(_state(
        "ws-messy",
        "total dynamic_qr by region",
        result,
        df,
        code="result = df.groupby('region')['dynamic_qr'].sum()",
    ))
    flags = out["data_quality_flags"]
    assert len(flags) >= 1, flags
    # a duplicate-row flag (whole-frame) or a dynamic_qr null flag must be present
    assert any(f["column"] is None for f in flags) or any(
        f["column"] == "dynamic_qr" for f in flags
    ), flags
