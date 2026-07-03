"""API contract tests — no LLM key required, the agent graph is not invoked."""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_get_run_not_found(api_client):
    r = api_client.get("/runs/nonexistent-id")
    assert r.status_code == 404


def test_create_and_list_workspace(api_client):
    r = api_client.post("/workspaces", json={"name": "Test WS"})
    assert r.status_code == 200
    created = r.json()["data"]
    assert created["id"]
    assert created["name"] == "Test WS"

    r2 = api_client.get("/workspaces")
    assert r2.status_code == 200
    names = [w["name"] for w in r2.json()["data"]]
    assert "Test WS" in names


def test_create_workspace_blank_name_rejected(api_client):
    r = api_client.post("/workspaces", json={"name": "   "})
    assert r.status_code == 400


def test_create_workspace_duplicate_name_rejected(api_client):
    api_client.post("/workspaces", json={"name": "Dup"})
    r = api_client.post("/workspaces", json={"name": "Dup"})
    assert r.status_code == 400


def test_get_unknown_workspace_404(api_client):
    r = api_client.get("/workspaces/does-not-exist")
    assert r.status_code == 404


def test_ask_unknown_workspace_404(api_client):
    r = api_client.post("/workspaces/nope/ask", json={"question": "hi", "dataset_id": None})
    assert r.status_code == 404
