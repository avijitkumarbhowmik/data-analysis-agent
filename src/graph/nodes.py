"""LangGraph nodes for the privacy-safe code-execution loop.

Privacy invariant: only the MASKED schema/stats/sample (built by ``prepare_context``)
and the MASKED result preview ever reach Gemini. The real DataFrame and the real
result table never leave the machine and are never placed in an LLM payload.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis import pii, sandbox, store
from db.models import Dataset, RunRow
from db.session import create_db_session
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")

_MAX_RESULT_ROWS = 500  # cap the REAL result table returned to the user (never to the LLM)


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- result serialization (REAL data → user; never sent to the LLM) --------

def _clean_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def serialize_result(result: Any) -> dict | None:
    """Turn a computed pandas/scalar result into ``{columns, rows}`` for the UI."""
    if result is None:
        return None

    if isinstance(result, pd.DataFrame):
        capped = result.head(_MAX_RESULT_ROWS)
        columns = [str(c) for c in capped.columns]
        rows = [[_clean_cell(v) for v in row] for row in capped.itertuples(index=False, name=None)]
        return {"columns": columns, "rows": rows}

    if isinstance(result, pd.Series):
        capped = result.head(_MAX_RESULT_ROWS)
        label = str(result.name) if result.name is not None else "value"
        index_label = str(result.index.name) if result.index.name is not None else "index"
        columns = [index_label, label]
        rows = [[_clean_cell(idx), _clean_cell(val)] for idx, val in capped.items()]
        return {"columns": columns, "rows": rows}

    # scalar (int/float/str) or other single value
    return {"columns": ["result"], "rows": [[_clean_cell(result)]]}


def _extract_code(text: str) -> str | None:
    """Pull the pandas out of a fenced ```python block; fall back to raw text."""
    if not text:
        return None
    fenced = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[0].strip()
    stripped = text.strip()
    # Model sometimes returns bare code with stray backticks.
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
    return stripped or None


# --- store hydration (lazy reload after a cold process) --------------------

def _ensure_loaded(workspace_id: str) -> dict[str, pd.DataFrame]:
    frames = store.get_frames(workspace_id)
    if frames:
        return frames
    # Re-register persisted datasets from the DB manifest, then lazy-load.
    with create_db_session() as session:
        rows = session.query(Dataset).filter(Dataset.workspace_id == workspace_id).all()
        for row in rows:
            store.register_persisted(workspace_id, row.file_path, row.name)
    return store.get_frames(workspace_id)


# --- nodes -----------------------------------------------------------------

def prepare_context(state: AgentState) -> AgentState:
    """REAL. Load the workspace frames and build the MASKED context for the LLM."""
    ws = state.get("workspace_id", "")
    try:
        frames = _ensure_loaded(ws)
        if not frames:
            return {**state, "error": "No dataset loaded for this workspace. Upload a CSV first."}

        primary = "df" if "df" in frames else next(iter(frames))
        df = frames[primary]
        pii_map = store.pii_map_of(ws, primary)
        schema_summary = pii.mask_schema(df, pii_map)

        _log.info(
            "prepare_context",
            run_id=state.get("run_id"),
            workspace_id=ws,
            frame_names=list(frames.keys()),
            rows=int(len(df)),
            pii_columns=list(pii_map.keys()),
        )
        return {
            **state,
            "schema_summary": schema_summary,
            "frame_names": list(frames.keys()),
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("prepare_context_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Could not load workspace data: {exc}"}


def clarify(state: AgentState) -> AgentState:
    """STUB in Phase 1 — always proceed. REAL in Phase 3."""
    return {**state, "needs_clarification": False, "clarifying_question": None}


def plan(state: AgentState) -> AgentState:
    """STUB in Phase 1 — no planning. REAL in Phase 3."""
    return {**state, "plan": state.get("plan")}


def generate_code(state: AgentState) -> AgentState:
    """REAL. Ask Gemini for a fenced pandas block that assigns ``result``."""
    try:
        system = _load_prompt("generate_code.md")
        frame_names = state.get("frame_names") or ["df"]
        parts = [
            f"Available DataFrame(s): {', '.join(frame_names)} (primary: `df`).",
            "",
            "Masked schema, statistics, and sample rows:",
            state.get("schema_summary", ""),
            "",
            f"Question: {state['question']}",
        ]
        prior_error = state.get("execution_error")
        if prior_error:
            parts += [
                "",
                "Your previous code failed with this error. Fix it and try again:",
                prior_error,
            ]
        user_prompt = "\n".join(parts)

        raw = LLMClient().call_model(user_prompt, system=system)
        code = _extract_code(raw)
        attempts = int(state.get("attempts", 0)) + 1

        if not code:
            return {
                **state,
                "attempts": attempts,
                "error": "The model did not return any code.",
            }

        _log.info(
            "generate_code",
            run_id=state.get("run_id"),
            workspace_id=state.get("workspace_id"),
            attempt=attempts,
            code_chars=len(code),
        )
        # A fresh generation clears the prior recoverable error.
        return {**state, "generated_code": code, "attempts": attempts, "execution_error": None}
    except Exception as exc:  # noqa: BLE001
        _log.error("generate_code_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Code generation failed: {exc}"}


def execute_code(state: AgentState) -> AgentState:
    """REAL. Run the generated pandas locally in the restricted sandbox."""
    ws = state.get("workspace_id", "")
    try:
        frames = _ensure_loaded(ws)
        if not frames:
            return {**state, "error": "Workspace data disappeared before execution."}
        pii_map = store.pii_map_of(ws)
        outcome = sandbox.run_pandas(state.get("generated_code", ""), frames, pii_map=pii_map)

        if not outcome.success:
            _log.info(
                "execute_code_failed",
                run_id=state.get("run_id"),
                attempt=state.get("attempts"),
                error=outcome.error,
            )
            # Recoverable — feeds the retry loop (NOT a fatal error).
            return {**state, "execution_error": outcome.error, "result_table": None}

        result_table = serialize_result(outcome.result)
        _log.info(
            "execute_code_ok",
            run_id=state.get("run_id"),
            attempt=state.get("attempts"),
            result_rows=len(result_table["rows"]) if result_table else 0,
        )
        return {
            **state,
            "execution_result": outcome.preview,   # MASKED — safe for the LLM
            "result_table": result_table,          # REAL — never sent to the LLM
            "execution_error": None,
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("execute_code_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Execution failed fatally: {exc}"}


def compose_answer(state: AgentState) -> AgentState:
    """REAL. Turn the MASKED result preview into plain-language prose via Gemini."""
    try:
        system = _load_prompt("compose_answer.md")
        user_prompt = (
            f"Question: {state['question']}\n\n"
            f"Computed result (masked preview):\n{state.get('execution_result', '(no result)')}"
        )
        answer = LLMClient().call_model(user_prompt, system=system)
        _log.info("compose_answer", run_id=state.get("run_id"), answer_chars=len(answer or ""))
        return {**state, "answer": (answer or "").strip()}
    except Exception as exc:  # noqa: BLE001
        _log.error("compose_answer_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Answer composition failed: {exc}"}


def enrich(state: AgentState) -> AgentState:
    """STUB in Phase 1 — no-op. REAL in Phase 2 (charts, quality, followups, cost)."""
    return state


def finalize(state: AgentState) -> AgentState:
    """REAL. Persist the completed run and set status."""
    run_id = state.get("run_id")
    answer = state.get("answer")
    try:
        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.question = state.get("question")
                run.input_text = state.get("question")
                run.generated_code = state.get("generated_code")
                run.result_preview = state.get("execution_result")
                run.answer = answer
                run.output_text = answer
                run.attempts = int(state.get("attempts", 1) or 1)
                run.status = "completed"
                run.completed_at = _now()
        _log.info("finalize", run_id=run_id, status="completed", attempts=state.get("attempts"))
        return {**state, "status": "completed"}
    except Exception as exc:  # noqa: BLE001
        _log.error("finalize_error", run_id=run_id, error=str(exc))
        return {**state, "error": f"Could not persist run: {exc}", "status": "failed"}


def handle_error(state: AgentState) -> AgentState:
    """REAL. Mark the run failed with a clear message and terminate."""
    run_id = state.get("run_id")
    message = state.get("error") or state.get("execution_error") or "The analysis failed."
    try:
        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = message
                run.question = state.get("question")
                run.input_text = state.get("question")
                run.generated_code = state.get("generated_code")
                run.attempts = int(state.get("attempts", 1) or 1)
                run.completed_at = _now()
    except Exception as exc:  # noqa: BLE001
        _log.error("handle_error_persist_failed", run_id=run_id, error=str(exc))
    _log.error("run_failed", run_id=run_id, workspace_id=state.get("workspace_id"), error=message)
    return {**state, "status": "failed", "error": message}
