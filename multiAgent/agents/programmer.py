from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..state import AgentMetric, CodeGenState
from ..prompt.withPlan import withPlanPrompt
from ..prompt.withReview import withReviewPrompt
from ..prompt.withTest import withTestPrompt
from ..prompt.withProgrammerSolo import withProgrammerSoloPrompt
from ..prompt.withArchitect import withArchitecturePrompt


class ProgrammerAgent(BaseAgent):

    def _select_prompt_mode(self, state: CodeGenState) -> str:
        explicit_mode = str(state.get("programmer_mode", "")).strip().lower()
        if explicit_mode in {"solo", "plan", "architect", "review", "test"}:
            return explicit_mode

        if self._latest(state.get("reviews")):
            return "review"
        if self._latest(state.get("test_cases")):
            return "test"
        if self._latest(state.get("architectures")):
            return "architect"
        if self._latest(state.get("plans")):
            return "plan"
        return "solo"

    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        mode = self._select_prompt_mode(state)

        latest_plan       = self._latest(state.get("plans"))
        latest_review     = self._latest(state.get("reviews"))
        latest_test_cases = self._latest(state.get("test_cases"))
        previous_code     = self._latest(state.get("codes"))

        if mode == "review":
            prompt = withReviewPrompt.format(
                previous_code=previous_code,
                review=latest_review,
            )
            return [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Please return the revised code as JSON."},
            ]

        if mode == "test":
            prompt = withTestPrompt.format(
                previous_code=previous_code,
                test_cases=latest_test_cases,
            )
            return [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Please return the revised code as JSON."},
            ]

        if mode == "architect":
            latest_architecture = self._latest(state.get("architectures"))
            prompt = withArchitecturePrompt.format(
                task=state["task"],
                plan=latest_plan,
                architecture=latest_architecture,
            )
            return [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Please implement the code and return it as JSON."},
            ]

        if mode == "plan":
            prompt = withPlanPrompt.format(
                plan=latest_plan,
                task=state["task"],
            )
            return [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Please implement the plan and return the code as JSON."},
            ]

        # solo
        return [
            {"role": "system", "content": withProgrammerSoloPrompt},
            {"role": "user",   "content": state["task"]},
        ]

    # _strip_code_fence and _latest are inherited from BaseAgent

    def _try_extract_nested_code(self, text: str) -> str | None:
        text = text.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            if isinstance(data.get("code"), str):
                return data["code"]
            if isinstance(data.get("output"), str):
                nested = self._try_extract_nested_code(data["output"])
                if nested is not None:
                    return nested
        return None

    def _extract_code(self, text: str) -> str:
        cleaned = self._strip_code_fence(text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Programmer output is not valid JSON (will retry): {e}\n"
                f"Raw output (first 200 chars): {cleaned[:200]!r}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError("Programmer output must be a JSON object.")

        if isinstance(data.get("code"), str):
            code = data["code"].strip()
            nested = self._try_extract_nested_code(code)
            return nested.strip() if nested is not None else code

        if isinstance(data.get("output"), str):
            nested = self._try_extract_nested_code(data["output"])
            if nested is not None:
                return nested.strip()
            return data["output"].strip()

        raise ValueError("Programmer output does not contain a valid 'code' field.")

    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        code = self._extract_code(response_text)
        mode = self._select_prompt_mode(state)

        next_iteration = state.get("iteration", 0) + 1

        update: dict[str, Any] = {
            "codes":     state.get("codes", []) + [code],
            "iteration": next_iteration,
            "final_code": code,
            "metrics":   [metric],
            "success":   True,
            "error":     "",
        }

        if mode == "review":
            update["reviewer_iteration"] = state.get("reviewer_iteration", 0) + 1
        elif mode == "test":
            update["tester_iteration"] = state.get("tester_iteration", 0) + 1

        return update
