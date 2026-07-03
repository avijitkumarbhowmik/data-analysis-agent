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
    # Phase 2: full, revisitable detail. `result_table` is NOT persisted on RunRow
    # (only the masked `result_preview`), and no migration is permitted this phase, so
    # a revisited past run returns `result_table: null` — the chart re-renders from the
    # persisted `chart_spec_json`, and the answer + code are the revisitable artifacts.
    return ok(
        {
            "run_id": run.id,
            "status": run.status,
            "question": run.question or run.input_text,
            "answer": run.answer or run.output_text,
            "generated_code": run.generated_code,
            "attempts": run.attempts,
            "result_preview": run.result_preview,
            "result_table": None,
            "chart_spec": run.chart_spec_json,
            "data_quality_flags": run.data_quality_json or [],
            "followups": run.followups_json or [],
            "cost": run.cost_json,
        }
    )
