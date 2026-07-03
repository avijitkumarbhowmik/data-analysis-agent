import json
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from analysis import store
from api._common import ok, api_error
from db.models import Dataset, Workspace
from db.session import get_session
from domain.workspace import AskRequest
from graph.runner import run_agent, run_agent_stream
from observability.events import get_logger

router = APIRouter()

_log = get_logger("api.ask")


def _response_data(result: dict) -> dict:
    """Shape a runner result into the `/ask` `data` object.

    Identical for the non-streaming response and the SSE `final` event, so the
    frontend's streaming and fallback paths receive the same fully-enriched payload.
    """
    return {
        "run_id": result["run_id"],
        "answer": result["answer"],
        "generated_code": result["generated_code"],
        "result_table": result["result_table"],
        "status": result["status"],
        "attempts": result["attempts"],
        "chart_spec": result.get("chart_spec"),
        "data_quality_flags": result.get("data_quality_flags") or [],
        "followups": result.get("followups") or [],
        "cost": result.get("cost"),
    }


def _validate_ask(workspace_id: str, req: AskRequest, session: Session) -> str:
    """Shared guard for `/ask` + `/ask/stream`. Returns the cleaned question."""
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise api_error("NOT_FOUND", f"Workspace {workspace_id} not found.", 404)

    question = req.question.strip()
    if not question:
        raise api_error("EMPTY_QUESTION", "Please enter a question.", 400)

    # Ensure the workspace has data (re-register from the DB manifest on a cold process).
    if not store.get_frames(workspace_id):
        rows = session.query(Dataset).filter(Dataset.workspace_id == workspace_id).all()
        for row in rows:
            store.register_persisted(workspace_id, row.file_path, row.name)
    if not store.get_frames(workspace_id):
        raise api_error("NO_DATASET", "Upload a dataset before asking a question.", 400)

    ws.updated_at = datetime.now(timezone.utc)
    return question


@router.post("/workspaces/{workspace_id}/ask")
def ask(workspace_id: str, req: AskRequest, session: Session = Depends(get_session)) -> dict:
    question = _validate_ask(workspace_id, req, session)
    result = run_agent(workspace_id, question, req.dataset_id)
    return ok(_response_data(result))


def _sse_frame(event: str, data: dict) -> str:
    """Serialize one raw Server-Sent-Events frame (event + JSON data + blank line)."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/workspaces/{workspace_id}/ask/stream")
def ask_stream(
    workspace_id: str, req: AskRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Stream the answer via SSE: progressive `delta` frames then one `final` frame.

    Validation errors (404 / 400) surface as normal HTTP errors before the stream
    opens. Any error once streaming has begun emits `event: error` and closes, so the
    frontend can fall back to the non-streaming `/ask` (same enriched payload).
    """
    question = _validate_ask(workspace_id, req, session)
    dataset_id = req.dataset_id

    def _events() -> Iterator[str]:
        try:
            for item in run_agent_stream(workspace_id, question, dataset_id):
                kind = item.get("type")
                if kind == "delta":
                    yield _sse_frame("delta", {"text": item.get("text", "")})
                elif kind == "final":
                    yield _sse_frame("final", _response_data(item["payload"]))
                elif kind == "error":
                    yield _sse_frame("error", {"message": item.get("message", "stream failed")})
                    return
        except Exception as exc:  # noqa: BLE001 — degrade cleanly to /ask on the client
            _log.error("ask_stream_error", workspace_id=workspace_id, error=str(exc))
            yield _sse_frame("error", {"message": f"Streaming failed: {exc}"})

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
