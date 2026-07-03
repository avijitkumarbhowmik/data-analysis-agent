from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset, RunRow, Workspace
from db.session import get_session
from domain.workspace import WorkspaceCreateRequest

router = APIRouter()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


@router.post("/workspaces")
def create_workspace(req: WorkspaceCreateRequest, session: Session = Depends(get_session)) -> dict:
    name = req.name.strip()
    if not name:
        raise api_error("INVALID_NAME", "Workspace name cannot be blank.", 400)

    existing = session.scalar(select(Workspace).where(Workspace.name == name))
    if existing is not None:
        raise api_error("DUPLICATE_NAME", f"A workspace named {name!r} already exists.", 400)

    ws = Workspace(name=name)
    session.add(ws)
    session.flush()
    return ok({"id": ws.id, "name": ws.name, "created_at": _iso(ws.created_at)})


@router.get("/workspaces")
def list_workspaces(session: Session = Depends(get_session)) -> dict:
    counts = dict(
        session.execute(
            select(Dataset.workspace_id, func.count(Dataset.id)).group_by(Dataset.workspace_id)
        ).all()
    )
    workspaces = session.scalars(select(Workspace).order_by(Workspace.updated_at.desc())).all()
    data = [
        {
            "id": ws.id,
            "name": ws.name,
            "dataset_count": int(counts.get(ws.id, 0)),
            "updated_at": _iso(ws.updated_at),
        }
        for ws in workspaces
    ]
    return ok(data)


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, session: Session = Depends(get_session)) -> dict:
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise api_error("NOT_FOUND", f"Workspace {workspace_id} not found.", 404)

    datasets = session.scalars(
        select(Dataset).where(Dataset.workspace_id == workspace_id).order_by(Dataset.created_at)
    ).all()
    runs = session.scalars(
        select(RunRow)
        .where(RunRow.workspace_id == workspace_id)
        .order_by(RunRow.created_at.desc())
        .limit(20)
    ).all()

    return ok(
        {
            "id": ws.id,
            "name": ws.name,
            "datasets": [
                {
                    "id": ds.id,
                    "name": ds.name,
                    "filename": ds.filename,
                    "row_count": ds.row_count,
                    "column_count": ds.column_count,
                    "schema": ds.schema_json or [],
                }
                for ds in datasets
            ],
            "recent_runs": [
                {
                    "id": r.id,
                    "question": r.question or r.input_text,
                    "status": r.status,
                    "created_at": _iso(r.created_at),
                }
                for r in runs
            ],
        }
    )
