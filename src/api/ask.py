from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analysis import store
from api._common import ok, api_error
from db.models import Dataset, Workspace
from db.session import get_session
from domain.workspace import AskRequest
from graph.runner import run_agent

router = APIRouter()


@router.post("/workspaces/{workspace_id}/ask")
def ask(workspace_id: str, req: AskRequest, session: Session = Depends(get_session)) -> dict:
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

    result = run_agent(workspace_id, question, req.dataset_id)

    ws.updated_at = datetime.now(timezone.utc)

    return ok(
        {
            "run_id": result["run_id"],
            "answer": result["answer"],
            "generated_code": result["generated_code"],
            "result_table": result["result_table"],
            "status": result["status"],
            "attempts": result["attempts"],
        }
    )
