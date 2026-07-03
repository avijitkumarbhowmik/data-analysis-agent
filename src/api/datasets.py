from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from analysis import store
from api._common import ok, api_error
from db.models import Dataset, Workspace
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("datasets")

# Repo root: src/api/datasets.py → 3 parents up
_UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _num(x: Any) -> float | int | None:
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return None if (np.isnan(f) or np.isinf(f)) else f
    return None


def _build_schema_with_stats(df: pd.DataFrame, pii_map: dict[str, str]) -> list[dict]:
    """Column schema + light stats for the UI (never sent to the LLM)."""
    schema: list[dict] = []
    for col in df.columns:
        name = str(col)
        series = df[col]
        dtype = str(series.dtype)
        nulls = int(series.isna().sum())
        stats: dict[str, Any]
        if name in pii_map:
            stats = {"pii": pii_map[name], "nulls": nulls, "note": "masked before any model call"}
        elif pd.api.types.is_numeric_dtype(series):
            stats = {
                "min": _num(series.min()),
                "max": _num(series.max()),
                "mean": _num(series.mean()),
                "nulls": nulls,
            }
        else:
            stats = {"distinct": int(series.nunique(dropna=True)), "nulls": nulls}
        schema.append({"name": name, "dtype": dtype, "stats": stats})
    return schema


@router.post("/workspaces/{workspace_id}/datasets")
async def upload_dataset(
    workspace_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise api_error("NOT_FOUND", f"Workspace {workspace_id} not found.", 404)

    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise api_error("UNSUPPORTED_TYPE", "Only .csv files are supported in Phase 1.", 400)

    raw = await file.read()
    if not raw or not raw.strip():
        raise api_error("EMPTY_FILE", "The uploaded file is empty.", 400)

    # Persist the raw file to disk (for lazy reload after a restart).
    dest_dir = _UPLOAD_ROOT / workspace_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    dest_path.write_bytes(raw)

    frame_name = store.DEFAULT_FRAME_NAME  # "df"
    try:
        store.load_csv(workspace_id, str(dest_path), frame_name)
    except Exception as exc:  # noqa: BLE001 — parse failure is a client error
        raise api_error("UNPARSEABLE", f"Could not parse the CSV: {exc}", 400)

    store.register_persisted(workspace_id, str(dest_path), frame_name)
    df = store.get_frames(workspace_id)[frame_name]
    pii_map = store.pii_map_of(workspace_id, frame_name)
    schema = _build_schema_with_stats(df, pii_map)
    pii_columns = list(pii_map.keys())

    dataset = Dataset(
        workspace_id=workspace_id,
        name=frame_name,
        filename=filename,
        file_path=str(dest_path),
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        schema_json=schema,
        pii_columns_json=pii_columns,
        is_derived=False,
    )
    session.add(dataset)
    ws.updated_at = datetime.now(timezone.utc)
    session.flush()

    _log.info(
        "dataset_uploaded",
        workspace_id=workspace_id,
        dataset_id=dataset.id,
        filename=filename,
        rows=dataset.row_count,
        columns=dataset.column_count,
        pii_columns=pii_columns,
    )

    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "filename": dataset.filename,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "schema": schema,
            "pii_columns": pii_columns,
        }
    )
