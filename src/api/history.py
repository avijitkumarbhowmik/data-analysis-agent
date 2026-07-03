"""Run-history list API (Phase 2).

`GET /workspaces/{id}/runs` — newest-first run list for the workspace's history panel.
The full, revisitable single-run detail (`GET /runs/{run_id}`) is extended in
`src/api/runs.py` to avoid a duplicate route registration; both belong to the
`backend-history-conversation` slice.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok
from db.models import RunRow
from db.session import get_session

router = APIRouter()


@router.get("/workspaces/{workspace_id}/runs")
def list_runs(workspace_id: str, session: Session = Depends(get_session)) -> dict:
    """List a workspace's runs, newest-first, for the run-history panel."""
    rows = (
        session.query(RunRow)
        .filter(RunRow.workspace_id == workspace_id)
        .order_by(RunRow.created_at.desc())
        .all()
    )
    return ok(
        [
            {
                "id": r.id,
                "question": r.question or r.input_text,
                "status": r.status,
                "created_at": r.created_at,
                "has_chart": r.chart_spec_json is not None,
            }
            for r in rows
        ]
    )
