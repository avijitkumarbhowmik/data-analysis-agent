"""Phase 1 fixtures — isolate the process-global dataset store per test.

The DB isolation + `api_client` + `_require_llm_key` fixtures live in the
repo-root `tests/conftest.py` and apply here too.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_store():
    from analysis import store
    store.clear()
    yield
    store.clear()
