"""Phase 1 integration gate — real Gemini via .env, SQLite (isolated temp DB).

Covers the core loop end-to-end plus the two defining gates:
  * PRIVACY  — no raw data row / un-masked PII in ANY outbound LLM payload.
  * FULL-DATA — the agent's numeric answer over a >=5,000-row fixture equals an
    independently-computed ground truth (a value a 5-row sample would get wrong).
Plus edge/error cases: unknown workspace, and the bounded retry loop.
"""

import io

import numpy as np
import pandas as pd
import pytest

# --- fixtures / helpers ----------------------------------------------------

# Distinctive raw PII values — asserted to NEVER appear in an LLM payload.
PII_NAMES = ["Ravikumar Bhandarkar", "Meenakshi Sundaram", "Aloysius Fernandes"]
PII_PANS = ["ABCDE1234F", "ZXYWV9876K", "LMNOP4567Q"]
PII_AADHAAR = ["987612341234", "111122223333", "444455556666"]
PII_PHONES = ["9812345670", "9898989898", "9700011122"]
PII_EMAILS = [
    "ravikumar.bhandarkar@examplemail.test",
    "meenakshi.sundaram@examplemail.test",
    "aloysius.fernandes@examplemail.test",
]
PII_ACCOUNTS = ["000987654321", "000111222333", "000444555666"]

ALL_RAW_PII = PII_NAMES + PII_PANS + PII_AADHAAR + PII_PHONES + PII_EMAILS + PII_ACCOUNTS


def _pii_csv_bytes() -> bytes:
    df = pd.DataFrame(
        {
            "customer_name": PII_NAMES,
            "pan": PII_PANS,
            "aadhaar": PII_AADHAAR,
            "phone": PII_PHONES,
            "email": PII_EMAILS,
            "account_number": PII_ACCOUNTS,
            "outstanding_principal": [125000, 340000, 87500],
            "dpd": [12, 95, 0],
        }
    )
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def _large_csv_and_truth(n: int = 6000) -> tuple[bytes, int]:
    rng = np.random.default_rng(42)
    principal = rng.integers(10_000, 5_000_000, size=n).astype(np.int64)
    df = pd.DataFrame(
        {
            "loan_id": [f"L{i:06d}" for i in range(n)],
            "customer_name": rng.choice(PII_NAMES, size=n),
            "pan": rng.choice(PII_PANS, size=n),
            "outstanding_principal": principal,
            "dpd": rng.integers(0, 180, size=n),
        }
    )
    ground_truth = int(df["outstanding_principal"].sum())
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8"), ground_truth


def _make_workspace(client, name: str) -> str:
    r = client.post("/workspaces", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _upload(client, ws_id: str, csv_bytes: bytes, filename: str = "loans.csv") -> dict:
    r = client.post(
        f"/workspaces/{ws_id}/datasets",
        files={"file": (filename, csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


# --- happy path (real Gemini) ---------------------------------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_end_to_end_ask_returns_answer_and_code(api_client):
    ws = _make_workspace(api_client, "E2E happy path")
    data = _upload(api_client, ws, _pii_csv_bytes())
    assert data["row_count"] == 3
    assert data["column_count"] == 8
    assert "outstanding_principal" in [c["name"] for c in data["schema"]]
    # PII detected and surfaced (list of column names).
    assert set(data["pii_columns"]) >= {"customer_name", "pan", "email"}

    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={"question": "What is the total outstanding principal?", "dataset_id": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed", body
    assert body["answer"] and body["answer"].strip()
    # The sandbox contract: uses frame `df` and assigns `result`.
    assert "result" in (body["generated_code"] or "")
    assert body["result_table"] is not None
    # Total of the small fixture is 125000 + 340000 + 87500 = 552500.
    flat = str(body["result_table"]["rows"])
    assert "552500" in flat

    # Persisted and retrievable.
    run_id = body["run_id"]
    got = api_client.get(f"/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["data"]["status"] == "completed"


# --- PRIVACY gate (real Gemini + outbound-payload spy) ---------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_privacy_no_raw_pii_in_any_llm_payload(api_client, monkeypatch):
    """Spy EVERY outbound LLM payload and assert no raw PII / raw row leaks."""
    from llm.client import LLMClient

    captured: list[dict] = []
    original = LLMClient.call_model

    def _spy(self, prompt, *, system=None):
        captured.append({"prompt": prompt or "", "system": system or ""})
        return original(self, prompt, system=system)

    monkeypatch.setattr(LLMClient, "call_model", _spy)

    ws = _make_workspace(api_client, "Privacy gate")
    _upload(api_client, ws, _pii_csv_bytes())

    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={"question": "How many customers are past 90 days DPD?", "dataset_id": None},
    )
    assert r.status_code == 200, r.text

    assert captured, "expected at least one LLM call to have been made"

    joined = "\n".join(p["prompt"] + "\n" + p["system"] for p in captured)

    # No raw PII value may appear anywhere in any outbound payload.
    leaked = [v for v in ALL_RAW_PII if v in joined]
    assert not leaked, f"raw PII leaked into an LLM payload: {leaked}"

    # No raw data row: a full comma-joined source row must not appear verbatim.
    raw_row = "Ravikumar Bhandarkar,ABCDE1234F,987612341234"
    assert raw_row not in joined

    # Positive control: masking actually happened on the schema surface.
    assert "***MASKED" in joined


# --- FULL-DATA gate (real Gemini, >=5,000 rows) ----------------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_full_data_numeric_answer_matches_ground_truth(api_client):
    csv_bytes, ground_truth = _large_csv_and_truth(6000)
    ws = _make_workspace(api_client, "Full-data gate")
    data = _upload(api_client, ws, csv_bytes)
    assert data["row_count"] == 6000

    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={
            "question": "What is the total outstanding principal across all loans?",
            "dataset_id": None,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed", body
    table = body["result_table"]
    assert table is not None, body

    # Extract the single numeric value the agent computed over ALL rows.
    values = [v for row in table["rows"] for v in row if isinstance(v, (int, float))]
    assert values, f"no numeric value in result table: {table}"
    computed = max(values, key=lambda v: abs(v))  # the aggregate is the dominant magnitude
    assert int(round(computed)) == ground_truth, (
        f"agent computed {computed} but full-data ground truth is {ground_truth}"
    )


# --- edge / error cases ----------------------------------------------------

def test_ask_unknown_workspace_is_clean_404(api_client):
    r = api_client.post(
        "/workspaces/does-not-exist/ask",
        json={"question": "anything?", "dataset_id": None},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_ask_without_dataset_is_clean_400(api_client):
    ws = _make_workspace(api_client, "No dataset yet")
    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={"question": "total?", "dataset_id": None},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NO_DATASET"


def test_retry_loop_recovers_from_first_bad_code(api_client, monkeypatch):
    """Control-flow test: first generation is broken, second is valid → recovers.

    Uses a controlled LLM double (this tests the graph retry edge, not model
    quality); the real-Gemini path is exercised by the gates above.
    """
    from llm.client import LLMClient

    calls = {"generate": 0}

    def _fake_init(self):  # avoid constructing a real provider
        pass

    def _fake_call(self, prompt, *, system=None):
        if system and "code generator" in system:
            calls["generate"] += 1
            if calls["generate"] == 1:
                return "```python\nresult = df['nope_missing_col'].sum()\n```"
            return "```python\nresult = df['outstanding_principal'].sum()\n```"
        return "The total outstanding principal is 552500."

    monkeypatch.setattr(LLMClient, "__init__", _fake_init)
    monkeypatch.setattr(LLMClient, "call_model", _fake_call)

    ws = _make_workspace(api_client, "Retry recovers")
    _upload(api_client, ws, _pii_csv_bytes())

    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={"question": "total outstanding principal?", "dataset_id": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed", body
    assert body["attempts"] >= 2  # retried after the first failure
    assert "552500" in str(body["result_table"]["rows"])


def test_persistent_bad_code_fails_gracefully(api_client, monkeypatch):
    """When every generation is broken, the run fails cleanly (no crash)."""
    from llm.client import LLMClient

    def _fake_init(self):
        pass

    def _fake_call(self, prompt, *, system=None):
        if system and "code generator" in system:
            return "```python\nresult = df['does_not_exist'].sum()\n```"
        return "unused"

    monkeypatch.setattr(LLMClient, "__init__", _fake_init)
    monkeypatch.setattr(LLMClient, "call_model", _fake_call)

    ws = _make_workspace(api_client, "Persistent failure")
    _upload(api_client, ws, _pii_csv_bytes())

    r = api_client.post(
        f"/workspaces/{ws}/ask",
        json={"question": "total?", "dataset_id": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "failed", body
    assert body["result_table"] is None
    # bounded by max_attempts (3 in Phase 1)
    assert body["attempts"] <= 3
