"""In-memory dataset store — process-global, keyed by workspace.

Holds the real, un-masked pandas DataFrame(s) for a workspace. Datasets are
loaded on upload and stay resident for the process lifetime (upload once, ask
many). On a cold process (after a restart) frames are lazily reloaded from disk
using paths registered via :func:`register_persisted` — the API slice persists a
``datasets`` manifest + the raw file path and registers them here.

Phase 1: one CSV per workspace, exposed under the frame name ``df``.

Public API (imported by the graph/API slice):
- ``load_csv(workspace_id, source, dataset_name="df") -> dict``  schema info
- ``get_frames(workspace_id) -> dict[str, DataFrame]``           e.g. {"df": <df>}
- ``has_workspace(workspace_id) -> bool``
- ``schema_of(workspace_id) -> dict``                            columns/dtypes/rows
- ``register_persisted(workspace_id, path, name="df")``          for lazy reload
- ``clear(workspace_id=None)``                                   drop cached frames
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from analysis.pii import detect_pii_columns

DEFAULT_FRAME_NAME = "df"


@dataclass
class LoadedDataset:
    name: str
    df: pd.DataFrame
    schema: dict[str, Any]
    pii_map: dict[str, str] = field(default_factory=dict)


# workspace_id -> { frame_name -> LoadedDataset }
_STORE: dict[str, dict[str, LoadedDataset]] = {}
# workspace_id -> { frame_name -> on-disk path }  (manifest for lazy reload)
_PERSISTED: dict[str, dict[str, str]] = {}


# --- CSV reading ----------------------------------------------------------

def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except UnicodeDecodeError as exc:  # try the next encoding
            last_err = exc
            continue
    # All encodings failed on decode — surface the last error.
    raise last_err if last_err else ValueError("Could not decode CSV")


def _read_csv(source: Any) -> pd.DataFrame:
    """Read a CSV from bytes, a filesystem path, or a file-like object."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    elif isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as fh:
            data = fh.read()
    elif hasattr(source, "read"):
        raw = source.read()
        data = raw.encode() if isinstance(raw, str) else bytes(raw)
    else:
        raise TypeError(f"Unsupported CSV source type: {type(source)!r}")
    if not data.strip():
        raise ValueError("CSV file is empty")
    return _read_csv_bytes(data)


def _build_schema(df: pd.DataFrame, name: str) -> dict[str, Any]:
    return {
        "dataset_name": name,
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "columns": [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns],
    }


# --- public API -----------------------------------------------------------

def load_csv(workspace_id: str, source: Any, dataset_name: str = DEFAULT_FRAME_NAME) -> dict[str, Any]:
    """Parse a CSV into a DataFrame, detect PII, cache it, and return schema info.

    ``source`` may be raw bytes, a filesystem path, or a file-like object. When a
    path is given it is also registered for lazy reload after a restart.
    """
    df = _read_csv(source)
    pii_map = detect_pii_columns(df)
    schema = _build_schema(df, dataset_name)
    schema["pii_columns"] = pii_map

    _STORE.setdefault(workspace_id, {})[dataset_name] = LoadedDataset(
        name=dataset_name, df=df, schema=schema, pii_map=pii_map
    )
    if isinstance(source, (str, os.PathLike)):
        register_persisted(workspace_id, str(source), dataset_name)
    return schema


def register_persisted(workspace_id: str, path: str, name: str = DEFAULT_FRAME_NAME) -> None:
    """Record an on-disk path so the frame can be lazily reloaded on a cold process."""
    _PERSISTED.setdefault(workspace_id, {})[name] = str(path)


def _lazy_load(workspace_id: str) -> None:
    """Populate the in-memory cache for a workspace from its persisted manifest."""
    manifest = _PERSISTED.get(workspace_id) or {}
    for name, path in manifest.items():
        cache = _STORE.get(workspace_id) or {}
        if name in cache:
            continue
        if os.path.exists(path):
            load_csv(workspace_id, path, name)


def get_frames(workspace_id: str) -> dict[str, pd.DataFrame]:
    """Return ``{frame_name: DataFrame}`` for a workspace (lazy-loading on a miss).

    Returns an empty dict if the workspace has neither cached nor persisted data.
    """
    if not _STORE.get(workspace_id):
        _lazy_load(workspace_id)
    return {name: ds.df for name, ds in _STORE.get(workspace_id, {}).items()}


def has_workspace(workspace_id: str) -> bool:
    """True if the workspace has data loaded or a persisted manifest to load from."""
    if _STORE.get(workspace_id):
        return True
    manifest = _PERSISTED.get(workspace_id) or {}
    return any(os.path.exists(p) for p in manifest.values())


def schema_of(workspace_id: str) -> dict[str, Any]:
    """Return schema info for a workspace (loading frames if needed).

    Phase 1: the primary ``df`` schema, with a ``frames`` map for forward-compat.
    Raises ``KeyError`` if the workspace has no data.
    """
    if not _STORE.get(workspace_id):
        _lazy_load(workspace_id)
    cache = _STORE.get(workspace_id)
    if not cache:
        raise KeyError(f"No dataset loaded for workspace {workspace_id!r}")
    primary = cache.get(DEFAULT_FRAME_NAME) or next(iter(cache.values()))
    result = dict(primary.schema)
    result["frames"] = {name: ds.schema for name, ds in cache.items()}
    return result


def pii_map_of(workspace_id: str, dataset_name: str = DEFAULT_FRAME_NAME) -> dict[str, str]:
    """Return the detected PII map for a workspace's frame (loading if needed)."""
    if not _STORE.get(workspace_id):
        _lazy_load(workspace_id)
    cache = _STORE.get(workspace_id) or {}
    ds = cache.get(dataset_name) or (next(iter(cache.values())) if cache else None)
    return dict(ds.pii_map) if ds else {}


def clear(workspace_id: str | None = None) -> None:
    """Drop cached frames (and persisted manifest). Mainly for tests/teardown."""
    if workspace_id is None:
        _STORE.clear()
        _PERSISTED.clear()
    else:
        _STORE.pop(workspace_id, None)
        _PERSISTED.pop(workspace_id, None)
