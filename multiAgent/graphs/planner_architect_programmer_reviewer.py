from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.planner import PlannerAgent
from ..agents.Architect import ArchitectAgent
from ..agents.programmer import ProgrammerAgent
from ..agents.Reviewer import ReviewerAgent
from ..state import CodeGenState
from .common import set_architect_mode, set_review_mode, reviewer_over_budget


def _route_after_reviewer(state: CodeGenState) -> str:
    if not state.get("need_revision", False):
        return "end"
    if reviewer_over_budget(state):
        return "end"
    return "set_review_mode"


def build_planner_architect_programmer_reviewer_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """
    START -> planner -> architect -> set_architect_mode -> programmer -> reviewer
    reviewer -> _route_after_reviewer -> (end | set_review_mode -> programmer)
    """
    builder = StateGraph(CodeGenState)

    planner    = PlannerAgent(   agent_name="planner",    model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    architect  = ArchitectAgent( agent_name="architect",  model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    programmer = ProgrammerAgent(agent_name="programmer", model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    reviewer   = ReviewerAgent(  agent_name="reviewer",   model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)

    builder.add_node("planner",            planner)
    builder.add_node("architect",          architect)
    builder.add_node("set_architect_mode", set_architect_mode)
    builder.add_node("set_review_mode",    set_review_mode)
    builder.add_node("programmer",         programmer)
    builder.add_node("reviewer",           reviewer)

    builder.add_edge(START,                "planner")
    builder.add_edge("planner",            "architect")
    builder.add_edge("architect",          "set_architect_mode")
    builder.add_edge("set_architect_mode", "programmer")
    builder.add_edge("programmer",         "reviewer")

    builder.add_conditional_edges(
        "reviewer",
        _route_after_reviewer,
        {"end": END, "set_review_mode": "set_review_mode"},
    )
    builder.add_edge("set_review_mode", "programmer")

    return builder.compile()
