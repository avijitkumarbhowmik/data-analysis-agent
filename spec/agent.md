# Agent

---

## Agent Architecture Pattern

**Chosen:** **Graph (LangGraph)** implementing a **ReAct-style code-execution loop** — reason (generate pandas) → act (execute locally) → observe (inspect result/error) → repeat until correct or the step limit is hit. Composed patterns from `harness/patterns/agentic-ai.md`: **#22 LLM-Generated Code Execution** (the core — the LLM writes pandas, the system runs it with the data in scope; never a hardcoded op-list), **#17 Reasoning (ReAct)** for the run→inspect→fix loop, **#18 Guardrails** (PII masking + sandbox validation) and **#12 Exception Handling** always on. Phase 3 adds **#6 Planning** (plan-then-execute for complex questions), **#13 Human-in-the-Loop** (a clarifying question when uncertain), and **#8 Memory** (conversation history across turns). This is a graph, not a single loop, because the flow branches (retry-on-error, clarify-vs-run, complex-vs-simple).

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `generate_code` | Google Gemini | `gemini-2.5-flash` | Fast, cheap code generation; the loop tolerates an occasional miss via retry. |
| `compose_answer` | Google Gemini | `gemini-2.5-flash` | Turning a small masked result into prose is light work. |
| `clarify` / `plan` (Phase 3) | Google Gemini | `gemini-2.5-flash` | Single model tier keeps cost/latency low; complexity handled by prompt + loop depth, not a bigger model. |

Model is pinned via `AGENT_LLM_MODEL=gemini-2.5-flash` in `.env`. **Never** hardcode `gemini-3.1-pro` (the boilerplate's invalid default).

**Fallback behaviour:** On a Gemini error/timeout the calling node catches the exception, sets `state["error"]`, and routes to `handle_error` (run marked `failed`, clear UI message). Retry/backoff on transient API errors is added in the resilience work; tests always call the real API with keys from `.env`.

**Prompt strategy:** System/user split. `generate_code` system prompt (`src/prompts/generate_code.md`) instructs: emit only pandas over the provided DataFrame name(s), assign the answer to `result`, no imports, no file/network access; it receives the masked schema + column stats + a few masked sample rows + the question (+ the prior error on retry). Structured expectation: a single fenced Python block, extracted by the node. `compose_answer` (`src/prompts/compose_answer.md`) receives the question + masked result preview and returns plain-language prose.

---

## Tools & Tool Calling

The agent does not use LLM-native function-calling; the "tool" is the **local sandbox** invoked deterministically by the `execute_code` node on the model's emitted code (safer and auditable for the privacy constraint).

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `run_pandas` (`src/analysis/sandbox.py`) | Executes generated pandas against the real DataFrame in a restricted namespace | `code: str`, `frames: dict[str, DataFrame]` | real result + masked preview, or captured error | None (in-memory compute; no disk/network) |
| `mask_for_llm` (`src/analysis/pii.py`) | Masks a schema/sample/result for LLM consumption | DataFrame/preview + PII map | masked text | None |
| `save_derived` (Phase 3) | Persists a derived DataFrame back to the workspace | DataFrame, name | new dataset row + file | DB write + file write |

**Tool selection strategy:** Deterministic — `generate_code` always produces code, `execute_code` always runs it. No LLM tool-routing.

**Tool failure handling:** Sandbox exceptions become `execution_error` and feed the retry loop (bounded by `max_attempts`). A timeout aborts with an error routed to `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                      # set by runner at init
    workspace_id: str                # set by runner from the request

    # Input
    question: str                    # user's plain-language question
    messages: list                   # [{role, content}] conversation history (Phase 2); [] in Phase 1

    # Context (built by prepare_context; MASKED — safe for the LLM)
    schema_summary: str              # masked schema + column stats + few masked sample rows
    frame_names: list                # DataFrame names in scope, e.g. ["df"] or ["df_loans","df_repay"]

    # Reasoning (Phase 3 real; pass-through stubs in Phase 1)
    needs_clarification: bool        # clarify node — question too ambiguous to run
    clarifying_question: str | None  # what to ask the user
    plan: str | None                 # plan node — numbered steps for complex questions

    # Code loop
    generated_code: str              # pandas emitted by generate_code
    execution_result: str | None     # MASKED result preview (for compose_answer/LLM)
    result_table: dict | None        # REAL result serialized for the user (never sent to LLM)
    execution_error: str | None      # captured error to feed the retry
    attempts: int                    # incremented each generate→execute cycle
    max_attempts: int                # 3 (Phase 1) / higher for complex (Phase 3)

    # Output
    answer: str                      # plain-language answer
    chart_spec: dict | None          # Phase 2
    data_quality_flags: list         # Phase 2
    followups: list                  # Phase 2
    cost: dict | None                # Phase 2 — {input_tokens, output_tokens, usd}

    # Control
    error: str | None                # set by any node on fatal failure
    status: str                      # completed | failed | needs_clarification
```

---

## Nodes / Steps

### `node_prepare_context` — REAL in Phase 1
**Reads:** `workspace_id`, `question`. **Writes:** `schema_summary`, `frame_names`, `error`.
**LLM call:** No. **External:** in-memory store (lazy-load from disk on cold process → on miss set `error`).
**Behaviour:** Loads the workspace DataFrame(s), computes schema + per-column stats, applies PII masking, and builds the masked context string the LLM will see. This is the privacy chokepoint — nothing un-masked leaves here.

### `node_clarify` — STUB in Phase 1 (pass-through) → REAL in Phase 3
**Reads:** `question`, `schema_summary`, `messages`. **Writes:** `needs_clarification`, `clarifying_question`.
**LLM call:** Phase 3 yes (is this answerable, or ambiguous?). **Behaviour:** Phase 1 always sets `needs_clarification=False` and proceeds. Phase 3 asks Gemini whether the question is answerable against the schema; if not, sets the clarifying question and routes to finalize (Human-in-the-Loop).

### `node_plan` — STUB in Phase 1 (pass-through) → REAL in Phase 3
**Reads:** `question`, `schema_summary`. **Writes:** `plan`, `max_attempts`.
**LLM call:** Phase 3 yes. **Behaviour:** Phase 1 no-op. Phase 3: for complex questions, produce a numbered analysis plan and raise `max_attempts` for a deeper iterate loop; simple questions skip planning.

### `node_generate_code` — REAL in Phase 1
**Reads:** `question`, `schema_summary`, `frame_names`, `plan`, `execution_error`, `attempts`. **Writes:** `generated_code`, `attempts`, `error`.
**LLM call:** Yes — Gemini, returns a fenced pandas block assigning `result`. On a retry the prior `execution_error` is included so the model fixes its code.

### `node_execute_code` — REAL in Phase 1
**Reads:** `generated_code`, `frame_names`. **Writes:** `execution_result` (masked), `result_table` (real), `execution_error`.
**LLM call:** No. **External:** the sandbox (`run_pandas`). **Behaviour:** AST-validates then executes the code against the real frames in the restricted namespace with a timeout; captures the real result and a masked preview, or the error.

### `node_inspect` — REAL in Phase 1 (routing node)
**Reads:** `execution_error`, `attempts`, `max_attempts`. **Writes:** nothing (pure routing via conditional edge).
**Behaviour:** If `execution_error` and `attempts < max_attempts` → back to `generate_code`. Else → `compose_answer`.

### `node_compose_answer` — REAL in Phase 1
**Reads:** `question`, `execution_result` (masked), `messages`. **Writes:** `answer`, `error`.
**LLM call:** Yes — Gemini turns the masked result into plain-language prose.

### `node_enrich` — STUB in Phase 1 (pass-through) → REAL in Phase 2
**Reads:** `question`, `result_table`, `generated_code`. **Writes:** `chart_spec`, `data_quality_flags`, `followups`, `cost`.
**Behaviour:** Phase 1 no-op. Phase 2: builds a chart spec when the result is chartable, profiles data-quality flags, suggests follow-ups, and computes token cost.

### `node_finalize` — REAL in Phase 1
**Reads:** most output fields. **Writes:** `status`. **External:** DB (persist the run). **Behaviour:** Writes the `runs` row (question, code, result preview, answer, timestamps, cost) and sets `status`.

### `node_handle_error` — REAL in Phase 1
**Reads:** `error`, `run_id`. **External:** DB. **Behaviour:** Marks the run `failed` with `error_message`, logs with `run_id`, terminates.

---

## Graph / Flow Topology

```
START
  │
  ▼
prepare_context ──(error)──► handle_error ──► END
  │
  ▼
clarify ──(needs_clarification)──► finalize ──► END   [Phase 3; Phase 1 always proceeds]
  │
  ▼
plan  ──(error)──► handle_error
  │
  ▼
generate_code ──(error)──► handle_error
  │
  ▼
execute_code ──(error)──► handle_error
  │
  ▼
inspect ──(execution_error AND attempts < max_attempts)──► generate_code   [retry loop]
  │
  └──(ok OR attempts exhausted)──► compose_answer ──(error)──► handle_error
                                        │
                                        ▼
                                     enrich ──► finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `prepare_context` | `state["error"]` set | `handle_error` |
| `prepare_context` | else | `clarify` |
| `clarify` | `needs_clarification` (Phase 3) | `finalize` |
| `clarify` | else | `plan` |
| `generate_code` / `execute_code` / `compose_answer` | `state["error"]` set | `handle_error` |
| `inspect` | `execution_error` and `attempts < max_attempts` | `generate_code` |
| `inspect` | otherwise | `compose_answer` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | Schema, code, results, attempts |
| **Across runs** | SQLite (`runs`, `datasets`, `column_notes`) | Full run history per workspace; datasets; business rules |
| **Conversation** | `messages` in state, hydrated by the runner from the workspace's recent `runs` (Phase 2) | Prior turns so follow-ups resolve pronouns/context |

**Context window management:** Only masked schema + column stats + a handful of masked sample rows + a size-capped masked result go to the LLM — never the full dataset. Conversation history is bounded to the most recent N turns.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | Shown to user | Expected action | Default |
|------------|---------------|-----------------|---------|
| Clarifying question (Phase 3) | The agent's question when the request is ambiguous | User answers → new ask with context | No timeout (local single-user); user re-asks |

---

## Error Handling & Recovery

**Node-level:** Each node wraps its work in try/except; fatal errors set `state["error"]` and route to `handle_error`. `execute_code` distinguishes a recoverable `execution_error` (feeds the retry loop) from a fatal `error`.

**Graph-level (`handle_error`):** Reads `error`, `run_id`; updates the run to `failed` with `error_message` and `completed_at`; logs with `run_id`; terminates.

**Resume / retry:** The code loop retries generation on execution errors up to `max_attempts`. A failed run is not auto-resumed; the user re-asks.

**Partial failure:** If Phase 2 `enrich` sub-steps fail (e.g. chart spec), the answer is still returned; the missing enrichment is logged and omitted (degrade, not abort).

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One structured log context per run, keyed by `run_id`/`workspace_id` | structlog → stdout |
| **LLM calls** | Model, prompt size, latency; tokens + cost (Phase 2) | Structured log + `runs.cost` |
| **Code loop** | Generated code, attempt number, execution success/error | Structured log |
| **Run outcome** | Status, duration, error | DB + structured log |

(LangSmith is not used — Gemini, not LangChain-hosted; the observability floor is structured request/response logging wired in Phase 1.)

---

## Concurrency Model

- **Run isolation:** One run per request, scoped by `run_id`; the in-memory store is keyed by `workspace_id`. Single-user local tool — no cross-run contention expected.
- **Parallel nodes within a run:** None; the loop is sequential (code depends on prior error).
- **Checkpointing:** None required (no long pauses; the Phase 3 clarify checkpoint ends the run and the user re-asks). The sandbox timeout runs each `exec` in a worker thread.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

for name, fn in [
    ("prepare_context", prepare_context),
    ("clarify", clarify),              # Phase 1: pass-through stub
    ("plan", plan),                    # Phase 1: pass-through stub
    ("generate_code", generate_code),
    ("execute_code", execute_code),
    ("compose_answer", compose_answer),
    ("enrich", enrich),                # Phase 1: pass-through stub
    ("finalize", finalize),
    ("handle_error", handle_error),
]:
    graph.add_node(name, fn)

graph.set_entry_point("prepare_context")

graph.add_conditional_edges("prepare_context",
    lambda s: "handle_error" if s.get("error") else "clarify")
graph.add_conditional_edges("clarify",
    lambda s: "finalize" if s.get("needs_clarification") else "plan")
graph.add_conditional_edges("plan",
    lambda s: "handle_error" if s.get("error") else "generate_code")
graph.add_conditional_edges("generate_code",
    lambda s: "handle_error" if s.get("error") else "execute_code")
graph.add_conditional_edges("execute_code",
    lambda s: "handle_error" if s.get("error") else "inspect_route")
# inspect is expressed as a conditional edge (no node body needed):
graph.add_conditional_edges("execute_code", inspect_route,
    {"generate_code": "generate_code", "compose_answer": "compose_answer",
     "handle_error": "handle_error"})
graph.add_conditional_edges("compose_answer",
    lambda s: "handle_error" if s.get("error") else "enrich")
graph.add_edge("enrich", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```

> `inspect` is implemented as the routing function `inspect_route(state)` on `execute_code`'s conditional edge (returns `generate_code` to retry, `compose_answer` when done, `handle_error` on fatal). The boilerplate variable name `agentic_ai` is kept as the compiled export.
