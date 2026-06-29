"""Routing functions for conditional edges."""

from __future__ import annotations

from .state import AgentState


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node."""
    return {
        "simple": "answer",
        "tool": "tool",
        "missing_info": "clarify",
        "risky": "risky_action",
        "error": "retry",
    }.get(str(state.get("route", "")), "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Retry if the latest tool evaluation failed; otherwise answer."""
    return "retry" if state.get("evaluation_result") == "needs_retry" else "answer"


def route_after_retry(state: AgentState) -> str:
    """Bound the retry loop by max_attempts."""
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    return "tool" if attempt < max_attempts else "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Proceed only when approval was granted."""
    approval = state.get("approval") or {}
    approved = bool(approval.get("approved", False)) if isinstance(approval, dict) else False
    return "tool" if approved else "clarify"
