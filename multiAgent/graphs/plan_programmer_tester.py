from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.planner import PlannerAgent
from ..agents.programmer import ProgrammerAgent
from ..agents.Tester import TesterAgent
from ..state import CodeGenState
from .common import set_plan_mode, set_test_mode, tester_over_budget


def _route_after_tester(state: CodeGenState) -> str:
    if not state.get("need_revision", False):
        return "end"
    if tester_over_budget(state):
        return "end"
    return "set_test_mode"


def build_plan_programmer_tester_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """
    START -> planner -> set_plan_mode -> programmer -> tester
    tester -> _route_after_tester -> (end | set_test_mode -> programmer)
    """
    builder = StateGraph(CodeGenState)

    planner    = PlannerAgent(   agent_name="planner",    model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    programmer = ProgrammerAgent(agent_name="programmer", model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)
    tester     = TesterAgent(    agent_name="tester",     model_name=model_name, temperature=temperature, api_key=api_key, base_url=base_url)

    builder.add_node("planner",       planner)
    builder.add_node("set_plan_mode", set_plan_mode)
    builder.add_node("set_test_mode", set_test_mode)
    builder.add_node("programmer",    programmer)
    builder.add_node("tester",        tester)

    builder.add_edge(START,           "planner")
    builder.add_edge("planner",       "set_plan_mode")
    builder.add_edge("set_plan_mode", "programmer")
    builder.add_edge("programmer",    "tester")

    builder.add_conditional_edges(
        "tester",
        _route_after_tester,
        {"end": END, "set_test_mode": "set_test_mode"},
    )
    builder.add_edge("set_test_mode", "programmer")

    return builder.compile()
