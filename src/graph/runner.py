"""Runner — creates the run row, invokes the graph, returns the API result dict."""

from __future__ import annotations

import time
from typing import Iterator

from db.models import RunRow
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")

MAX_ATTEMPTS = 3  # Phase 1
HISTORY_TURNS = 5  # Phase 2 — recent completed runs hydrated into conversation memory


def _hydrate_messages(workspace_id: str, exclude_run_id: str, limit: int = HISTORY_TURNS) -> list[dict]:
    """Build ``[{role, content}]`` conversation history from recent completed runs.

    Scoped to the workspace, bounded to the most recent ``limit`` completed runs,
    ordered oldest→newest, excluding the run currently executing. Degrades to an
    empty list (single-turn) on any DB error — memory is best-effort, never fatal.
    """
    try:
        with create_db_session() as session:
            rows = (
                session.query(RunRow)
                .filter(
                    RunRow.workspace_id == workspace_id,
                    RunRow.status == "completed",
                    RunRow.id != exclude_run_id,
                )
                .order_by(RunRow.created_at.desc())
                .limit(limit)
                .all()
            )
            ordered = list(reversed(rows))  # oldest → newest
            messages: list[dict] = []
            for r in ordered:
                question = r.question or r.input_text
                answer = r.answer or r.output_text
                if question:
                    messages.append({"role": "user", "content": str(question)})
                if answer:
                    messages.append({"role": "assistant", "content": str(answer)})
            return messages
    except Exception as exc:  # noqa: BLE001 — memory is best-effort
        _log.error("hydrate_messages_error", workspace_id=workspace_id, error=str(exc))
        return []


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

    messages = _hydrate_messages(workspace_id, run_id)
    _log.info("run_start_memory", run_id=run_id, history_messages=len(messages))

    initial: AgentState = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "question": question,
        "messages": messages,
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
        "chart_spec": final.get("chart_spec"),
        "data_quality_flags": final.get("data_quality_flags") or [],
        "followups": final.get("followups") or [],
        "cost": final.get("cost"),
        "error": None,
    }


def _chunk_answer(answer: str, words_per_chunk: int = 6) -> list[str]:
    """Split a composed answer into progressive text deltas (word-grouped)."""
    text = answer or ""
    if not text.strip():
        return []
    words = text.split(" ")
    chunks: list[str] = []
    for i in range(0, len(words), words_per_chunk):
        group = " ".join(words[i : i + words_per_chunk])
        # Preserve the inter-chunk space so concatenation reconstructs the answer.
        chunks.append(group if i == 0 else " " + group)
    return chunks


def run_agent_stream(
    workspace_id: str, question: str, dataset_id: str | None = None
) -> Iterator[dict]:
    """Streaming run path for the SSE ``/ask/stream`` endpoint.

    Runs the graph to completion (robust — the same real pipeline as ``run_agent``),
    then emits the composed answer progressively as ``delta`` events followed by one
    ``final`` event carrying the full enriched payload. The contract is: zero-or-more
    progressive text deltas, THEN exactly one final full payload. A failed run is still
    a valid ``final`` (status ``failed``); only an unexpected crash yields ``error``.
    """
    try:
        result = run_agent(workspace_id, question, dataset_id)
    except Exception as exc:  # noqa: BLE001 — never crash the request
        _log.error("run_agent_stream_error", workspace_id=workspace_id, error=str(exc))
        yield {"type": "error", "message": f"The analysis failed: {exc}"}
        return

    for chunk in _chunk_answer(result.get("answer") or ""):
        yield {"type": "delta", "text": chunk}
    yield {"type": "final", "payload": result}
