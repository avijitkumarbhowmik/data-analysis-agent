from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import RunRow

router = APIRouter()


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    return ok(
        {
            "run_id": run.id,
            "status": run.status,
            "question": run.question or run.input_text,
            "answer": run.answer or run.output_text,
            "generated_code": run.generated_code,
            "result_preview": run.result_preview,
        }
    )
