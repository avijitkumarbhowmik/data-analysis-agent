"""In-memory dataset store."""

import pandas as pd
import pytest

from analysis import store

CSV = (
    "customer_name,pan,principal,dpd\n"
    "Ravi Kumar,ABCDE1234F,100000,0\n"
    "Sunita Rao,PQRSX6789Z,250000,95\n"
    "Amit Shah,LMNOP4321Q,75000,30\n"
)


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


# --- load from bytes ------------------------------------------------------

def test_load_csv_from_bytes_builds_frame_and_schema():
    schema = store.load_csv("ws1", CSV.encode("utf-8"), "df")
    assert schema["row_count"] == 3
    assert schema["column_count"] == 4
    col_names = [c["name"] for c in schema["columns"]]
    assert col_names == ["customer_name", "pan", "principal", "dpd"]
    assert schema["pii_columns"]["customer_name"] == "name"
    assert schema["pii_columns"]["pan"] == "pan"


def test_get_frames_returns_df():
    store.load_csv("ws1", CSV.encode("utf-8"))
    frames = store.get_frames("ws1")
    assert set(frames.keys()) == {"df"}
    assert isinstance(frames["df"], pd.DataFrame)
    assert len(frames["df"]) == 3
    # execution frame holds REAL, un-masked values
    assert "Ravi Kumar" in frames["df"]["customer_name"].tolist()


def test_has_workspace():
    assert store.has_workspace("ws1") is False
    store.load_csv("ws1", CSV.encode("utf-8"))
    assert store.has_workspace("ws1") is True


def test_schema_of():
    store.load_csv("ws1", CSV.encode("utf-8"))
    schema = store.schema_of("ws1")
    assert schema["row_count"] == 3
    assert "frames" in schema
    assert "df" in schema["frames"]


def test_schema_of_missing_raises():
    with pytest.raises(KeyError):
        store.schema_of("nope")


# --- load from path -------------------------------------------------------

def test_load_csv_from_path(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text(CSV, encoding="utf-8")
    schema = store.load_csv("ws2", str(p))
    assert schema["row_count"] == 3
    assert store.get_frames("ws2")["df"].shape == (3, 4)


# --- lazy reload from disk (cold process) ---------------------------------

def test_lazy_reload_from_disk():
    # Simulate a restart: file on disk + a registered manifest, but nothing cached.
    p = tmp_path = None
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(CSV)
        store.register_persisted("ws3", path, "df")
        # nothing cached yet
        assert "ws3" not in store._STORE
        assert store.has_workspace("ws3") is True
        # get_frames triggers lazy load from disk
        frames = store.get_frames("ws3")
        assert "df" in frames
        assert len(frames["df"]) == 3
    finally:
        os.remove(path)


def test_pii_map_of():
    store.load_csv("ws1", CSV.encode("utf-8"))
    pmap = store.pii_map_of("ws1")
    assert pmap["customer_name"] == "name"
    assert pmap["pan"] == "pan"


def test_empty_csv_raises():
    with pytest.raises(Exception):
        store.load_csv("wsX", b"")
