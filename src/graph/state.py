from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                      # set by runner at init
    workspace_id: str                # set by runner from the request
    dataset_id: str | None           # primary dataset (optional)

    # Input
    question: str                    # user's plain-language question
    messages: list                   # [{role, content}] conversation history (Phase 2); [] in Phase 1

    # Context (built by prepare_context; MASKED — safe for the LLM)
    schema_summary: str              # masked schema + column stats + few masked sample rows
    frame_names: list                # DataFrame names in scope, e.g. ["df"]

    # Reasoning (Phase 3 real; pass-through stubs in Phase 1)
    needs_clarification: bool
    clarifying_question: str | None
    plan: str | None

    # Code loop
    generated_code: str              # pandas emitted by generate_code
    execution_result: str | None     # MASKED result preview (for compose_answer/LLM)
    result_table: dict | None        # REAL result serialized for the user (never sent to LLM)
    execution_error: str | None      # captured error to feed the retry
    attempts: int                    # incremented each generate→execute cycle
    max_attempts: int                # 3 (Phase 1)

    # Output
    answer: str                      # plain-language answer
    chart_spec: dict | None          # Phase 2
    data_quality_flags: list         # Phase 2
    followups: list                  # Phase 2
    cost: dict | None                # Phase 2

    # Control
    error: str | None                # set by any node on fatal failure
    status: str                      # completed | failed | needs_clarification
