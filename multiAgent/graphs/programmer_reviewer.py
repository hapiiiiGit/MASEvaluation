from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.programmer import ProgrammerAgent
from ..agents.Reviewer import ReviewerAgent
from ..state import CodeGenState
from .common import set_solo_mode, set_review_mode, reviewer_over_budget


def _route_after_reviewer(state: CodeGenState) -> str:
    """
    - need_revision=False         → end (approved)
    - need_revision=True, budget  → set_review_mode (keep fixing)
    - need_revision=True, overrun → end (budget exhausted)
    """
    if not state.get("need_revision", False):
        return "end"
    if reviewer_over_budget(state):
        return "end"
    return "set_review_mode"


def build_programmer_reviewer_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """
    START -> set_solo_mode -> programmer -> reviewer
    reviewer -> _route_after_reviewer -> (end | set_review_mode -> programmer)
    """
    builder = StateGraph(CodeGenState)

    programmer = ProgrammerAgent(agent_name="programmer", model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    reviewer   = ReviewerAgent(  agent_name="reviewer",   model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)

    builder.add_node("set_solo_mode",   set_solo_mode)
    builder.add_node("set_review_mode", set_review_mode)
    builder.add_node("programmer",      programmer)
    builder.add_node("reviewer",        reviewer)

    builder.add_edge(START,             "set_solo_mode")
    builder.add_edge("set_solo_mode",   "programmer")
    builder.add_edge("programmer",      "reviewer")      # always review every draft

    builder.add_conditional_edges(
        "reviewer",
        _route_after_reviewer,
        {"set_review_mode": "set_review_mode", "end": END},
    )
    builder.add_edge("set_review_mode", "programmer")

    return builder.compile()
