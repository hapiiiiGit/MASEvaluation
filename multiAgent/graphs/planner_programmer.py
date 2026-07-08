from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.planner import PlannerAgent
from ..agents.programmer import ProgrammerAgent
from ..state import CodeGenState
from .common import set_plan_mode


def build_planner_programmer_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """START -> planner -> set_plan_mode -> programmer -> END"""
    builder = StateGraph(CodeGenState)

    planner = PlannerAgent(
        agent_name="planner",
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
    )
    programmer = ProgrammerAgent(
        agent_name="programmer",
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
    )

    builder.add_node("planner",       planner)
    builder.add_node("set_plan_mode", set_plan_mode)
    builder.add_node("programmer",    programmer)

    builder.add_edge(START,          "planner")
    builder.add_edge("planner",      "set_plan_mode")
    builder.add_edge("set_plan_mode","programmer")
    builder.add_edge("programmer",   END)

    return builder.compile()
