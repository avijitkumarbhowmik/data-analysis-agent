"""Restricted pandas execution sandbox — the ``run_pandas`` tool.

Executes LLM-generated pandas **in-process** against the real DataFrame(s), but
constrained: an AST pre-check rejects imports, dunder access, and dangerous
names; execution runs in a namespace whose ``__builtins__`` is a curated
whitelist (no ``open``/``eval``/``exec``/``__import__``/``os``/``sys``/...); and
the whole thing runs under a wall-clock timeout enforced by a worker thread
(``signal.alarm`` is unavailable on Windows).

The generated code must assign its answer to a variable named ``result``.

Public API (imported by the graph/API slice):
- ``run_pandas(code, frames, pii_map=None, timeout=None) -> ExecutionResult``
- ``ExecutionResult`` dataclass: ``success``, ``result``, ``preview``, ``error``
- ``validate_code(code) -> str | None``  (the AST check; None means OK)
"""

from __future__ import annotations

import ast
import builtins
import threading
import traceback
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analysis.pii import mask_result

DEFAULT_TIMEOUT_SECONDS = 15.0

# Names that must never appear in generated code (module handles, escapes).
_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "__import__", "eval", "exec", "compile", "open", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "hasattr", "memoryview", "breakpoint", "exit", "quit", "help",
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib",
    "builtins", "__builtins__", "object", "type", "super",
    "classmethod", "staticmethod", "property", "vars", "id",
})

# The only builtins available to executed code.
_ALLOWED_BUILTINS: tuple[str, ...] = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "int", "len", "list", "map", "max", "min",
    "pow", "print", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "zip",
)
_SAFE_BUILTINS: dict[str, Any] = {n: getattr(builtins, n) for n in _ALLOWED_BUILTINS}
_SAFE_BUILTINS.update({"True": True, "False": False, "None": None})


@dataclass
class ExecutionResult:
    success: bool
    result: Any = None
    preview: str | None = None
    error: str | None = None
    stdout: str = ""


def _default_timeout() -> float:
    try:
        from config.settings import get_settings

        return float(getattr(get_settings(), "sandbox_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
                     or DEFAULT_TIMEOUT_SECONDS)
    except Exception:
        return DEFAULT_TIMEOUT_SECONDS


def validate_code(code: str) -> str | None:
    """AST-validate generated code. Returns an error string, or None if allowed."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return f"SyntaxError: {exc.msg} (line {exc.lineno})"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "Imports are not allowed in generated code."
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return f"Access to dunder/private attribute '{node.attr}' is not allowed."
        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES:
                return f"Use of '{node.id}' is not allowed in generated code."
        # block `with open(...)`, lambdas calling forbidden names are caught by Name check
    return None


def _format_exception(exc: BaseException) -> str:
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    # Keep the exception type/message plus the last frame — never a data dump.
    tail = "".join(tb[-2:]).strip() if len(tb) >= 2 else "".join(tb).strip()
    return tail or f"{type(exc).__name__}: {exc}"


def run_pandas(
    code: str,
    frames: dict[str, pd.DataFrame],
    pii_map: dict[str, str] | None = None,
    timeout: float | None = None,
) -> ExecutionResult:
    """Execute generated pandas against the real ``frames`` in a restricted namespace.

    Returns an :class:`ExecutionResult` carrying the real ``result`` object, a
    masked ``preview`` (safe for the LLM), or a captured ``error`` string. Never
    raises for user-code failures — the error is captured so the agent's retry
    loop can fix the code.
    """
    validation_error = validate_code(code)
    if validation_error is not None:
        return ExecutionResult(success=False, error=validation_error)

    # Single namespace so comprehensions/lambdas resolve names correctly.
    namespace: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS, "pd": pd, "np": np}
    namespace.update(frames or {})

    container: dict[str, Any] = {}

    def _worker() -> None:
        try:
            compiled = compile(code, "<generated>", "exec")
            exec(compiled, namespace)  # noqa: S102 — sandboxed builtins + AST gate
            container["done"] = True
        except BaseException as exc:  # noqa: BLE001 — capture everything for retry
            container["error"] = _format_exception(exc)

    limit = timeout if timeout is not None else _default_timeout()
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(limit)

    if thread.is_alive():
        return ExecutionResult(
            success=False,
            error=f"Execution timed out after {limit:g}s (possible infinite loop or too-heavy computation).",
        )
    if "error" in container:
        return ExecutionResult(success=False, error=container["error"])
    if "result" not in namespace:
        return ExecutionResult(
            success=False,
            error="Code did not define a 'result' variable. Assign the answer to `result`.",
        )

    result = namespace["result"]
    try:
        preview = mask_result(result, pii_map)
    except Exception as exc:  # masking must never crash the run
        preview = f"(could not build preview: {type(exc).__name__})"
    return ExecutionResult(success=True, result=result, preview=preview)
