"""Graph assembly — the ReAct-style code-execution loop (see spec/agent.md)."""

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    prepare_context,
    clarify,
    plan,
    generate_code,
    execute_code,
    compose_answer,
    enrich,
    finalize,
    handle_error,
)
from graph.edges import (
    route_after_prepare,
    route_after_clarify,
    route_after_plan,
    route_after_generate,
    route_after_compose,
    inspect_route,
)


def _build_graph():
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

    graph.add_conditional_edges("prepare_context", route_after_prepare,
        {"handle_error": "handle_error", "clarify": "clarify"})
    graph.add_conditional_edges("clarify", route_after_clarify,
        {"finalize": "finalize", "plan": "plan"})
    graph.add_conditional_edges("plan", route_after_plan,
        {"handle_error": "handle_error", "generate_code": "generate_code"})
    graph.add_conditional_edges("generate_code", route_after_generate,
        {"handle_error": "handle_error", "execute_code": "execute_code"})
    # execute_code → inspect (retry loop / done / fail) expressed as one conditional edge.
    graph.add_conditional_edges("execute_code", inspect_route,
        {"generate_code": "generate_code", "compose_answer": "compose_answer",
         "handle_error": "handle_error"})
    graph.add_conditional_edges("compose_answer", route_after_compose,
        {"handle_error": "handle_error", "enrich": "enrich"})
    graph.add_edge("enrich", "finalize")
    graph.add_edge("finalize", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


# Boilerplate export name kept.
agentic_ai = _build_graph()
