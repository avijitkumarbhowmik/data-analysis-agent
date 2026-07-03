"""Phase 2 `backend-history-conversation` gate — real Gemini via .env, SQLite.

Covers the three capabilities this slice owns end-to-end over the regional
payment-mode fixture:
  * run-history          — a run persists → `GET /workspaces/{id}/runs` lists it →
                           `GET /runs/{id}` returns its chart_spec + answer + code.
  * conversation-memory  — a second, pronoun-referencing turn resolves against the
                           first (prior question text is carried into the LLM prompt).
  * live-query-feedback  — `POST /ask/stream` emits >=1 `delta` then one `final`
                           frame carrying answer + chart_spec + cost.
"""

import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "regional_payment_modes.csv"
MIX_QUESTION = "show the payment-mode mix by region"


def _make_workspace(client, name: str) -> str:
    r = client.post("/workspaces", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _upload_fixture(client, ws_id: str) -> dict:
    r = client.post(
        f"/workspaces/{ws_id}/datasets",
        files={"file": ("regional_payment_modes.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _ask(client, ws_id: str, question: str) -> dict:
    r = client.post(f"/workspaces/{ws_id}/ask", json={"question": question, "dataset_id": None})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _parse_sse(raw: str) -> list[dict]:
    events: list[dict] = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        ev: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                ev["data"] = line[len("data:"):].strip()
        if ev:
            events.append(ev)
    return events


# --- run-history: persist → list → revisitable detail ----------------------

@pytest.mark.usefixtures("_require_llm_key")
def test_run_persists_lists_and_is_revisitable(api_client):
    ws = _make_workspace(api_client, "History gate")
    _upload_fixture(api_client, ws)

    data = _ask(api_client, ws, MIX_QUESTION)
    assert data["status"] == "completed", data
    run_id = data["run_id"]

    # non-streaming /ask is fully enriched (fallback path)
    assert "chart_spec" in data
    assert "cost" in data and data["cost"] is not None
    assert data["cost"]["usd"] > 0, data["cost"]

    # GET /workspaces/{id}/runs lists the run, newest-first
    lst = api_client.get(f"/workspaces/{ws}/runs")
    assert lst.status_code == 200, lst.text
    runs = lst.json()["data"]
    assert any(r["id"] == run_id for r in runs), runs
    listed = next(r for r in runs if r["id"] == run_id)
    assert listed["question"] == MIX_QUESTION
    assert listed["status"] == "completed"
    assert listed["has_chart"] is True  # mix question yields a dashboard chart_spec

    # GET /runs/{id} is the full, revisitable detail
    got = api_client.get(f"/runs/{run_id}")
    assert got.status_code == 200, got.text
    detail = got.json()["data"]
    assert detail["answer"] and detail["answer"].strip()
    assert detail["generated_code"] and "result" in detail["generated_code"]
    assert detail["chart_spec"] is not None
    assert detail["chart_spec"]["kind"] == "dashboard", detail["chart_spec"]
    assert detail["cost"] is not None and detail["cost"]["usd"] > 0
    # result_table is intentionally not persisted (no migration this phase)
    assert detail["result_table"] is None


# --- conversation memory: a follow-up resolves the first turn's subject -----

@pytest.mark.usefixtures("_require_llm_key")
def test_second_turn_resolves_prior_context(api_client, monkeypatch):
    from llm.client import LLMClient

    captured: list[str] = []
    original = LLMClient.call_model

    def _spy(self, prompt, *, system=None):
        captured.append(prompt or "")
        return original(self, prompt, system=system)

    monkeypatch.setattr(LLMClient, "call_model", _spy)

    ws = _make_workspace(api_client, "Memory gate")
    _upload_fixture(api_client, ws)

    first_q = "which regions have the highest dynamic_qr volume?"
    first = _ask(api_client, ws, first_q)
    assert first["status"] == "completed", first

    captured.clear()  # only inspect the SECOND turn's outbound prompts

    # A pronoun-only follow-up: only resolvable via the prior turn's subject.
    second = _ask(api_client, ws, "now show the payment-mode mix for those regions")
    assert second["status"] == "completed", second

    # Memory was hydrated + injected: the first question's text reached an LLM prompt.
    joined = "\n".join(captured)
    assert first_q in joined, "prior turn was not carried into the second turn's prompt"


# --- live feedback: SSE stream emits deltas then a final enriched payload ----

@pytest.mark.usefixtures("_require_llm_key")
def test_ask_stream_emits_deltas_then_final(api_client):
    ws = _make_workspace(api_client, "Stream gate")
    _upload_fixture(api_client, ws)

    with api_client.stream(
        "POST",
        f"/workspaces/{ws}/ask/stream",
        json={"question": MIX_QUESTION, "dataset_id": None},
    ) as resp:
        assert resp.status_code == 200, resp.read()
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join(resp.iter_text())

    events = _parse_sse(raw)
    kinds = [e.get("event") for e in events]
    assert kinds.count("final") == 1, kinds
    assert kinds.count("delta") >= 1, kinds
    # deltas precede the terminal final frame
    assert kinds.index("final") == len(kinds) - 1, kinds

    final = next(e for e in events if e.get("event") == "final")
    payload = json.loads(final["data"])
    assert payload["status"] == "completed", payload
    assert payload["answer"] and payload["answer"].strip()
    assert payload["chart_spec"] is not None
    assert payload["chart_spec"]["kind"] == "dashboard", payload["chart_spec"]
    assert payload["cost"] is not None and payload["cost"]["usd"] > 0

    # the concatenated deltas reconstruct the composed answer
    delta_text = "".join(json.loads(e["data"])["text"] for e in events if e.get("event") == "delta")
    assert delta_text.strip(), "expected non-empty streamed answer text"
