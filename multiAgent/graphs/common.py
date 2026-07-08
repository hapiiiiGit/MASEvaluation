"""
graphs/common.py
────────────────
Shared mode-setter nodes and budget-check helpers used by all graph files.

Mode-setters
  set_solo_mode / set_plan_mode / set_architect_mode /
  set_review_mode / set_test_mode

Budget helpers
  reviewer_over_budget(state) -> bool
  tester_over_budget(state)   -> bool

Routing uses `>=` so that with max_reviewer_iterations=5 the programmer
gets exactly 5 review-driven fix cycles before the budget is considered
exhausted:
  reviewer_iteration  1..4  →  4 >= 5  is False  →  allow another cycle
  reviewer_iteration  5     →  5 >= 5  is True   →  exit loop  (Bug 5 fix)
"""
from __future__ import annotations

from ..state import CodeGenState

# ── mode-setter nodes ────────────────────────────────────────────────────────

def set_solo_mode(_: CodeGenState) -> dict:
    return {"programmer_mode": "solo"}


def set_plan_mode(_: CodeGenState) -> dict:
    return {"programmer_mode": "plan"}


def set_architect_mode(_: CodeGenState) -> dict:
    return {"programmer_mode": "architect"}


def set_review_mode(_: CodeGenState) -> dict:
    return {"programmer_mode": "review"}


def set_test_mode(_: CodeGenState) -> dict:
    return {"programmer_mode": "test"}


# ── budget helpers ───────────────────────────────────────────────────────────

def reviewer_over_budget(state: CodeGenState) -> bool:
    """True when the reviewer loop has exhausted its fix budget."""
    return (
        state.get("reviewer_iteration", 0)
        >= state.get("max_reviewer_iterations", 5)  # Bug 5 fix: >= not >
    )


def tester_over_budget(state: CodeGenState) -> bool:
    """True when the tester loop has exhausted its fix budget."""
    return (
        state.get("tester_iteration", 0)
        >= state.get("max_tester_iterations", 5)  # Bug 5 fix: >= not >
    )
