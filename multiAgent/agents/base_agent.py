from __future__ import annotations

import time
from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from openai import OpenAI

from ..state import AgentMetric, CodeGenState
from ..config.setting import settings

_MAX_AGENT_RETRIES = 5       # per-node retry budget
_AGENT_RETRY_WAIT  = 2.0    # seconds between retries


class BaseAgent(ABC):
    def __init__(
        self,
        agent_name: str,
        model_name: str,
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.model_name = model_name
        self.temperature = temperature

        self.client = OpenAI(
            api_key=api_key if api_key is not None else settings.api_key,
            base_url=base_url if base_url is not None else settings.base_url,
        )

    # ── shared utilities (subclasses inherit; no more copy-paste) ──────────

    def _latest(self, items: list[str] | None) -> str:
        """Return the last element stripped, or '' if the list is empty."""
        if not items:
            return ""
        return items[-1].strip()

    def _strip_code_fence(self, text: str) -> str:
        """Remove leading/trailing ``` fences that LLMs sometimes add."""
        text = text.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    # ── abstract interface ──────────────────────────────────────────────────

    @abstractmethod
    def build_messages(self, state: CodeGenState) -> list[dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def build_state_update(
        self,
        state: CodeGenState,
        response_text: str,
        metric: AgentMetric,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # ── internal helpers ────────────────────────────────────────────────────

    def _next_call_index(self, state: CodeGenState) -> int:
        metrics = state.get("metrics", [])
        return 1 + sum(1 for m in metrics if m.get("agent") == self.agent_name)

    def _usage_to_metric(
        self,
        state: CodeGenState,
        usage_metadata: dict[str, int],
        wall_time_s: float,
        success: bool,
        error: str = "",
    ) -> AgentMetric:
        return {
            "agent": self.agent_name,
            "model": self.model_name,
            "run_name": self.agent_name,
            "call_index": self._next_call_index(state),
            "input_tokens": int(usage_metadata.get("input_tokens", 0)),
            "output_tokens": int(usage_metadata.get("output_tokens", 0)),
            "total_tokens": int(usage_metadata.get("total_tokens", 0)),
            "wall_time_s": wall_time_s,
            "success": success,
            "error": error,
        }

    # ── LangGraph node entry-point (with retry) ────────────────────────────

    def __call__(self, state: CodeGenState) -> dict[str, Any]:
        last_error: Exception | None = None
        total_start = perf_counter()

        for attempt in range(1, _MAX_AGENT_RETRIES + 1):
            start = perf_counter()
            try:
                messages = self.build_messages(state)
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )

                elapsed = perf_counter() - start
                usage = response.usage
                metric = self._usage_to_metric(
                    state=state,
                    usage_metadata={
                        "input_tokens":  getattr(usage, "prompt_tokens",     0) if usage else 0,
                        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                        "total_tokens":  getattr(usage, "total_tokens",      0) if usage else 0,
                    },
                    wall_time_s=elapsed,
                    success=True,
                )

                response_text = (response.choices[0].message.content or "").strip()
                return self.build_state_update(state, response_text, metric)

            except Exception as e:
                last_error = e
                if attempt < _MAX_AGENT_RETRIES:
                    time.sleep(_AGENT_RETRY_WAIT)

        # All retries exhausted — return a failure record so the graph
        # can continue routing (routers check success/error fields).
        total_elapsed = perf_counter() - total_start
        metric = self._usage_to_metric(
            state=state,
            usage_metadata={},
            wall_time_s=total_elapsed,
            success=False,
            error=str(last_error),
        )
        # Bug 1 fix: still increment the iteration counter so reviewer/tester
        # loops can exit even when this agent fails every retry.
        state_mode = state.get("programmer_mode", "")
        failure_update: dict[str, Any] = {
            "metrics": [metric],
            "success": False,
            "error": str(last_error),
            "need_revision": False,  # prevent stale True from looping on dead agent
        }
        if state_mode == "review":
            failure_update["reviewer_iteration"] = state.get("reviewer_iteration", 0) + 1
        elif state_mode == "test":
            failure_update["tester_iteration"] = state.get("tester_iteration", 0) + 1
        return failure_update
