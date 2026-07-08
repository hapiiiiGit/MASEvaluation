from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..state import AgentMetric, CodeGenState
from ..prompt.Reviewer import reviewerPrompt


class ReviewerAgent(BaseAgent):


    # _latest and _strip_code_fence are inherited from BaseAgent

    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        latest_code = self._latest(state.get("codes"))
        if not latest_code:
            raise ValueError("ReviewerAgent requires at least one code in state['codes'].")

        prompt = reviewerPrompt.format(
            task=state["task"],
            code=latest_code,
        )
        return [
            {"role": "system", "content": prompt},
            {"role": "user",   "content": "Please review the code and return the result as JSON."},
        ]

    def _extract_review_result(self, text: str) -> tuple[bool, str]:
        cleaned = self._strip_code_fence(text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Reviewer output is not valid JSON: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Reviewer output must be a JSON object.")
        if "need_revision" not in data:
            raise ValueError("Reviewer output must contain 'need_revision'.")
        if "review" not in data:
            raise ValueError("Reviewer output must contain 'review'.")

        need_revision = data["need_revision"]
        review        = data["review"]

        # Coerce string booleans that some LLMs return instead of JSON booleans.
        if isinstance(need_revision, str):
            if need_revision.lower() == "true":
                need_revision = True
            elif need_revision.lower() == "false":
                need_revision = False
            else:
                raise ValueError(
                    f"'need_revision' is an unrecognised string: {need_revision!r}"
                )
        if not isinstance(need_revision, bool):
            raise ValueError(
                f"'need_revision' must be a boolean, got {type(need_revision).__name__}: {need_revision!r}"
            )
        if not isinstance(review, str):
            raise ValueError("'review' must be a string.")

        return need_revision, review.strip()

    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        need_revision, review = self._extract_review_result(response_text)

        update: dict[str, Any] = {
            "reviews":       state.get("reviews", []) + [review],
            "need_revision": need_revision,
            "metrics":       [metric],
            "success":       True,
            "error":         "",
        }

        # When reviewer approves, stamp final_code with the validated version.
        if not need_revision:
            latest_code = self._latest(state.get("codes"))
            if latest_code:
                update["final_code"] = latest_code

        return update
