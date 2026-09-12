"""LangGraph state machine for workflow orchestration."""

try:
    from langgraph.graph import StateGraph
except ImportError:
    from langgraph import StateGraph

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint import MemorySaver

from app.config import MAX_RETRIES
from app.schemas import PlannerState
from app.agents import parse_intent, curate_pois, plan_logistics, validate, compile_itinerary


def should_replan(state: PlannerState) -> str:
    """Conditional edge routing based on validation status."""
    if state["status"] == "invalid" and state["retry_count"] < MAX_RETRIES:
        return "replan"
    else:
        return "compile"


def build_graph():
    """Build and compile the LangGraph state machine."""
    graph = StateGraph(PlannerState)

    # Add nodes
    graph.add_node("coordinator", parse_intent)
    graph.add_node("researcher", curate_pois)
    graph.add_node("logistics", plan_logistics)
    graph.add_node("validator", validate)
    graph.add_node("compiler", compile_itinerary)

    # Set entry point
    graph.set_entry_point("coordinator")

    # Add fixed edges
    graph.add_edge("coordinator", "researcher")
    graph.add_edge("researcher", "logistics")
    graph.add_edge("logistics", "validator")

    # Conditional edge from validator
    graph.add_conditional_edges(
        "validator",
        should_replan,
        {
            "replan": "coordinator",
            "compile": "compiler",
        },
    )

    # Set finish point
    graph.set_finish_point("compiler")

    # Compile with checkpointer
    checkpointer = MemorySaver()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    return compiled_graph
