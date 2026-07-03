"""Runner — creates the run row, invokes the graph, returns the API result dict."""

from __future__ import annotations

import time

from db.models import RunRow
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")

MAX_ATTEMPTS = 3  # Phase 1


def run_agent(workspace_id: str, question: str, dataset_id: str | None = None) -> dict:
    """Run one analysis question end-to-end and return the API-shaped result.

    Returns::

        {run_id, answer, generated_code, result_table, status, attempts, error}
    """
    init_db()

    with create_db_session() as session:
        run = RunRow(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            question=question,
            input_text=question,
            status="pending",
            attempts=0,
        )
        session.add(run)
        session.flush()
        run_id = run.id

    _log.info("run_start", run_id=run_id, workspace_id=workspace_id, question=question)
    started = time.monotonic()

    initial: AgentState = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "question": question,
        "messages": [],
        "attempts": 0,
        "max_attempts": MAX_ATTEMPTS,
        "error": None,
        "execution_error": None,
    }

    try:
        final: AgentState = agentic_ai.invoke(initial)
    except Exception as exc:  # noqa: BLE001 — never let the API crash on an agent fault
        _log.error("run_crashed", run_id=run_id, error=str(exc))
        with create_db_session() as session:
            row = session.get(RunRow, run_id)
            if row is not None:
                row.status = "failed"
                row.error_message = str(exc)
        return {
            "run_id": run_id,
            "answer": f"The analysis failed: {exc}",
            "generated_code": None,
            "result_table": None,
            "status": "failed",
            "attempts": 0,
            "error": str(exc),
        }

    status = final.get("status", "completed")
    latency_ms = round((time.monotonic() - started) * 1000)
    _log.info(
        "run_end",
        run_id=run_id,
        workspace_id=workspace_id,
        status=status,
        attempts=final.get("attempts"),
        latency_ms=latency_ms,
    )

    if status != "completed":
        message = final.get("error") or "The analysis failed."
        return {
            "run_id": run_id,
            "answer": message,
            "generated_code": final.get("generated_code"),
            "result_table": None,
            "status": "failed",
            "attempts": int(final.get("attempts", 0) or 0),
            "error": message,
        }

    return {
        "run_id": run_id,
        "answer": final.get("answer") or "",
        "generated_code": final.get("generated_code"),
        "result_table": final.get("result_table"),
        "status": "completed",
        "attempts": int(final.get("attempts", 1) or 1),
        "error": None,
    }
