from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..state import AgentMetric, CodeGenState
from ..prompt.Planner import plannerPrompt


class PlannerAgent(BaseAgent):
    """Generate an implementation plan from the user task."""

    # _strip_code_fence and _latest are inherited from BaseAgent

    def _extract_plan(self, text: str) -> str:
        cleaned = self._strip_code_fence(text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Planner output is not valid JSON (will retry): {e}\n"
                f"Raw output (first 200 chars): {cleaned[:200]!r}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError("Planner output must be a JSON object.")

        if isinstance(data.get("plan"), str):
            return data["plan"].strip()

        raise ValueError("Planner output does not contain a valid 'plan' field.")

    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": plannerPrompt},
            {"role": "user",   "content": state["task"]},
        ]

    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        plan = self._extract_plan(response_text)

        return {
            "plans":   state.get("plans", []) + [plan],
            "metrics": [metric],
            "success": True,
            "error":   "",
        }
