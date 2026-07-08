from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from ..agents.programmer import ProgrammerAgent
from ..state import CodeGenState
from .common import set_solo_mode


def build_solo_programmer_graph(
    model_name: str,
    temperature: float = 0.0,
    api_key: str | None = None,
    base_url: str | None = None,
):
    """START -> set_solo_mode -> programmer -> END"""
    builder = StateGraph(CodeGenState)

    programmer = ProgrammerAgent(
        agent_name="programmer",
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
    )

    builder.add_node("set_solo_mode", set_solo_mode)
    builder.add_node("programmer", programmer)

    builder.add_edge(START, "set_solo_mode")
    builder.add_edge("set_solo_mode", "programmer")
    builder.add_edge("programmer", END)

    return builder.compile()
