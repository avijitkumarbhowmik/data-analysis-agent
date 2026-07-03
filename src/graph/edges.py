"""Conditional-edge routing functions for the agent graph."""

from graph.state import AgentState


def route_after_prepare(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "clarify"


def route_after_clarify(state: AgentState) -> str:
    return "finalize" if state.get("needs_clarification") else "plan"


def route_on_error(state: AgentState) -> str:
    """Generic: any node that set a fatal ``error`` routes to handle_error."""
    return "handle_error" if state.get("error") else "_ok"


def route_after_plan(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "generate_code"


def route_after_generate(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_code"


def route_after_compose(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "enrich"


def inspect_route(state: AgentState) -> str:
    """The ReAct observe step (expressed as a routing function on execute_code).

    - fatal error            → handle_error
    - recoverable error and attempts remain → generate_code (retry)
    - recoverable error and attempts exhausted → handle_error (fail gracefully)
    - success                → compose_answer
    """
    if state.get("error"):
        return "handle_error"
    if state.get("execution_error"):
        if int(state.get("attempts", 0)) < int(state.get("max_attempts", 3)):
            return "generate_code"
        return "handle_error"
    return "compose_answer"
