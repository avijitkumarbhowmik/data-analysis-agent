"""Restricted pandas execution sandbox."""

import time

import pandas as pd
import pytest

from analysis import sandbox
from analysis.sandbox import run_pandas


def _frames():
    return {
        "df": pd.DataFrame(
            {
                "principal": [100, 200, 300, 400],
                "dpd": [0, 95, 30, 120],
                "name": ["Ravi Kumar", "Sunita Rao", "Amit Shah", "Neha Verma"],
            }
        )
    }


# --- happy path -----------------------------------------------------------

def test_valid_snippet_computes_result():
    res = run_pandas("result = df['principal'].sum()", _frames())
    assert res.success is True
    assert res.error is None
    assert res.result == 1000
    assert res.preview is not None


def test_result_over_full_data_not_sampled():
    df = pd.DataFrame({"x": list(range(5000))})
    res = run_pandas("result = int(df['x'].sum())", {"df": df})
    assert res.success is True
    assert res.result == sum(range(5000))


def test_numpy_available():
    res = run_pandas("result = int(np.array([1, 2, 3]).sum())", _frames())
    assert res.success is True
    assert res.result == 6


def test_preview_masks_pii_from_result():
    code = "result = df[['name', 'principal']]"
    res = run_pandas(code, _frames(), pii_map={"name": "name"})
    assert res.success is True
    assert "Ravi Kumar" not in res.preview
    assert "MASKED" in res.preview


# --- edge cases -----------------------------------------------------------

def test_missing_result_variable_is_error():
    res = run_pandas("x = df['principal'].sum()", _frames())
    assert res.success is False
    assert "result" in res.error.lower()


def test_empty_frame_snippet():
    df = pd.DataFrame({"x": []})
    res = run_pandas("result = df['x'].sum()", {"df": df})
    assert res.success is True
    assert res.result == 0


# --- error path (captured, not raised) ------------------------------------

def test_erroring_snippet_returns_clean_error():
    res = run_pandas("result = df['does_not_exist'].sum()", _frames())
    assert res.success is False
    assert res.error  # a clean string, not an exception
    assert isinstance(res.error, str)


def test_runtime_error_is_captured_not_raised():
    res = run_pandas("result = 1 / 0", _frames())
    assert res.success is False
    assert "ZeroDivisionError" in res.error


# --- security: AST rejection ----------------------------------------------

@pytest.mark.parametrize(
    "code",
    [
        "import os\nresult = 1",
        "from os import system\nresult = 1",
        "result = open('secret.txt').read()",
        "result = __import__('os').system('echo hi')",
        "result = df.__class__.__bases__",
        "result = eval('1+1')",
        "result = exec('x=1')",
        "result = getattr(df, 'values')",
        "result = globals()",
        "result = os.listdir('.')",
    ],
)
def test_malicious_code_is_rejected(code):
    res = run_pandas(code, _frames())
    assert res.success is False, f"should have been rejected: {code!r}"
    assert res.error


def test_dunder_attribute_access_rejected():
    assert sandbox.validate_code("result = df.__dict__") is not None


def test_valid_code_passes_validation():
    assert sandbox.validate_code("result = df.groupby('dpd').principal.mean()") is None


# --- timeout --------------------------------------------------------------

def test_infinite_loop_hits_timeout():
    start = time.monotonic()
    res = run_pandas("while True:\n    pass\nresult = 1", _frames(), timeout=1.0)
    elapsed = time.monotonic() - start
    assert res.success is False
    assert "timed out" in res.error.lower()
    assert elapsed < 5.0  # returned promptly, did not hang
