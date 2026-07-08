from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.planner import PlannerAgent
from ..agents.Architect import ArchitectAgent
from ..agents.programmer import ProgrammerAgent
from ..agents.Reviewer import ReviewerAgent
from ..agents.Tester import TesterAgent
from ..state import CodeGenState
from .common import (
    set_architect_mode,
    set_review_mode,
    set_test_mode,
    reviewer_over_budget,
    tester_over_budget,
)


def _route_after_programmer(state: CodeGenState) -> str:
    """
    Route after programmer based on which mode triggered it:
      test mode   → skip reviewer, go straight back to tester
      other modes → go through reviewer as normal
    """
    if state.get("programmer_mode", "") == "test":
        return "tester"
    return "reviewer"


def _route_after_reviewer(state: CodeGenState) -> str:
    """
    Reviewer approves           → tester (proceed to test phase)
    Budget for review exhausted → tester (move on regardless)
    Still needs review fixes    → set_review_mode (loop back)
    """
    if not state.get("need_revision", False):
        return "tester"
    if reviewer_over_budget(state):
        return "tester"
    return "set_review_mode"


def _route_after_tester(state: CodeGenState) -> str:
    """
    All tests pass              → end
    Budget for tests exhausted  → end
    Still needs test fixes      → set_test_mode (loop back)
    """
    if not state.get("need_revision", False):
        return "end"
    if tester_over_budget(state):
        return "end"
    return "set_test_mode"


def build_planner_architect_programmer_reviewer_tester_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """
    START → planner → architect → set_architect_mode → programmer → reviewer
    reviewer → (approve/budget) → tester
             → (need fix)       → set_review_mode → programmer
    tester   → (pass/budget)    → END
             → (need fix)       → set_test_mode   → programmer
    """
    builder = StateGraph(CodeGenState)

    planner    = PlannerAgent(   agent_name="planner",    model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    architect  = ArchitectAgent( agent_name="architect",  model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    programmer = ProgrammerAgent(agent_name="programmer", model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    reviewer   = ReviewerAgent(  agent_name="reviewer",   model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    tester     = TesterAgent(    agent_name="tester",     model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)

    builder.add_node("planner",            planner)
    builder.add_node("architect",          architect)
    builder.add_node("set_architect_mode", set_architect_mode)
    builder.add_node("set_review_mode",    set_review_mode)
    builder.add_node("set_test_mode",      set_test_mode)
    builder.add_node("programmer",         programmer)
    builder.add_node("reviewer",           reviewer)
    builder.add_node("tester",             tester)

    builder.add_edge(START,                "planner")
    builder.add_edge("planner",            "architect")
    builder.add_edge("architect",          "set_architect_mode")
    builder.add_edge("set_architect_mode", "programmer")

    # test-fix path skips reviewer and goes straight back to tester;
    # all other paths (initial, review-fix) go through reviewer first.
    builder.add_conditional_edges(
        "programmer",
        _route_after_programmer,
        {"reviewer": "reviewer", "tester": "tester"},
    )

    builder.add_conditional_edges(
        "reviewer",
        _route_after_reviewer,
        {"tester": "tester", "set_review_mode": "set_review_mode"},
    )
    builder.add_edge("set_review_mode", "programmer")

    builder.add_conditional_edges(
        "tester",
        _route_after_tester,
        {"end": END, "set_test_mode": "set_test_mode"},
    )
    builder.add_edge("set_test_mode", "programmer")

    return builder.compile()
