"""Analysis engine: the privacy + execution core.

Framework-agnostic modules used by the graph nodes:
- ``store``   — in-memory dataset store (workspace_id -> DataFrames)
- ``pii``     — PII detection + masking (the privacy chokepoint)
- ``sandbox`` — restricted pandas execution sandbox (``run_pandas``)
"""

from analysis.pii import (
    PII_TYPES,
    detect_pii_columns,
    mask_result,
    mask_schema,
)
from analysis.sandbox import (
    ExecutionResult,
    run_pandas,
    validate_code,
)
from analysis.store import (
    clear,
    get_frames,
    has_workspace,
    load_csv,
    pii_map_of,
    register_persisted,
    schema_of,
)

__all__ = [
    # store
    "load_csv",
    "get_frames",
    "has_workspace",
    "schema_of",
    "register_persisted",
    "pii_map_of",
    "clear",
    # pii
    "detect_pii_columns",
    "mask_schema",
    "mask_result",
    "PII_TYPES",
    # sandbox
    "run_pandas",
    "validate_code",
    "ExecutionResult",
]
