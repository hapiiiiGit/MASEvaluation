from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..state import AgentMetric, CodeGenState
from ..prompt.Architect import architectPrompt


class ArchitectAgent(BaseAgent):

    # _strip_code_fence and _latest are inherited from BaseAgent

    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        plan = self._latest(state.get("plans"))
        prompt = architectPrompt.format(task=state["task"], plan=plan)
        return [
            {"role": "system", "content": prompt},
            {"role": "user",   "content": "Please provide the architecture design as JSON."},
        ]

    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        cleaned = self._strip_code_fence(response_text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Architect output is not valid JSON: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Architect output must be a JSON object.")

        architecture = data.get("architecture")
        if not isinstance(architecture, str):
            raise ValueError(
                "Architect output must contain an 'architecture' string field."
            )

        return {
            "architectures": state.get("architectures", []) + [architecture],
            "metrics":       [metric],
            "success":       True,
            "error":         "",
        }
