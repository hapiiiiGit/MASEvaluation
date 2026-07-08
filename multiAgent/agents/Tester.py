from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..state import AgentMetric, CodeGenState
from ..prompt.Tester import testerPrompt
from ..utils.code_executor import run_tests


class TesterAgent(BaseAgent):

    # _latest and _strip_code_fence are inherited from BaseAgent

    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        latest_code = self._latest(state.get("codes"))
        if not latest_code:
            raise ValueError("TesterAgent requires at least one code in state['codes'].")

        prompt = testerPrompt.format(
            task=state["task"],
            code=latest_code,
        )
        return [
            {"role": "system", "content": prompt},
            {"role": "user",   "content": "Please write test cases for the code and return as JSON."},
        ]

    def _extract_test_cases(self, text: str) -> str:

        cleaned = self._strip_code_fence(text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Tester output is not valid JSON: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Tester output must be a JSON object.")
        if "test_cases" not in data:
            raise ValueError("Tester output must contain 'test_cases'.")
        if not isinstance(data["test_cases"], str):
            raise ValueError("'test_cases' must be a string.")

        return data["test_cases"].strip()

    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        test_code   = self._extract_test_cases(response_text)
        latest_code = self._latest(state.get("codes"))

        exec_result = run_tests(latest_code, test_code)

        # Combine stderr + stdout so no output is silently lost
        execution_output = "\n".join(
            s for s in [exec_result.stderr, exec_result.stdout] if s
        ).strip()

        if exec_result.success:
            need_revision = False
            report = f"[PASSED]\n{execution_output}"
        elif exec_result.timed_out:
            need_revision = True
            report = f"[TIMEOUT] Execution timed out.\n{execution_output}"
        else:
            need_revision = True
            report = f"[FAILED]\n{execution_output}"


        test_cases_record = (
            f"### Test Code\n{test_code}\n\n"
            f"### Execution Result\n{report}"
        )

        update: dict[str, Any] = {
            "test_cases":    state.get("test_cases", []) + [test_cases_record],
            "need_revision": need_revision,
            "metrics":       [metric],
            "success":       True,
            "error":         "",
        }


        if not need_revision and latest_code:
            update["final_code"] = latest_code

        return update
