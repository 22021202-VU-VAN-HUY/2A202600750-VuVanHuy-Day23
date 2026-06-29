"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do not mutate input state; return new values only.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, ApprovalDecision, Route, make_event


class ClassificationResult(BaseModel):
    """Structured LLM output for route selection."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="The safest workflow route for the support request."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="High only for side-effecting or destructive actions."
    )
    reason: str = Field(description="Brief reason for the selected route.")


def _llm_name(llm: object) -> str:
    return str(
        getattr(llm, "model_name", None)
        or getattr(llm, "model", None)
        or getattr(llm, "model_id", None)
        or llm.__class__.__name__
    )


def _message_content(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content)


def _offline_fallback_enabled() -> bool:
    return os.getenv("LLM_OFFLINE_FALLBACK", "").lower() in {"1", "true", "yes"}


def _ai_log(state: AgentState, node: str, message: str, **metadata: object) -> dict:
    payload: dict[str, object] = {
        "scenario_id": state.get("scenario_id", "unknown"),
        "thread_id": state.get("thread_id", "unknown"),
        "node": node,
        "message": message,
    }
    payload.update(metadata)
    return payload


def _fallback_classification(query: str) -> ClassificationResult:
    """Conservative backup used only when the LLM provider is unavailable."""
    lowered = query.lower()
    risky_terms = ("refund", "delete", "send confirmation", "send email", "cancel", "remove")
    tool_terms = ("lookup", "look up", "order status", "tracking", "order", "search", "find")
    error_terms = ("timeout", "failure", "failed", "crash", "cannot recover", "system error")
    vague_terms = ("fix it", "help", "issue", "problem", "can you fix")
    if any(term in lowered for term in risky_terms):
        return ClassificationResult(route="risky", risk_level="high", reason="Fallback detected side effects.")
    if any(term in lowered for term in tool_terms):
        return ClassificationResult(route="tool", risk_level="medium", reason="Fallback detected lookup intent.")
    if any(term in lowered for term in vague_terms) or len(lowered.split()) <= 3:
        return ClassificationResult(
            route="missing_info",
            risk_level="low",
            reason="Fallback detected insufficient details.",
        )
    if any(term in lowered for term in error_terms):
        return ClassificationResult(route="error", risk_level="medium", reason="Fallback detected system failure.")
    return ClassificationResult(route="simple", risk_level="low", reason="Fallback defaulted to simple support.")


def intake_node(state: AgentState) -> dict:
    """Normalize raw query."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using a real LLM structured output call."""
    query = state.get("query", "")
    llm = None
    classifier = None
    prompt = f"""
You are routing a support-ticket workflow. Classify the request into exactly one route.

Routes:
- risky: side effects or irreversible actions, including refunds, deletes, cancellations,
  sending email, account changes, or customer-impacting operations.
- tool: information lookup or search, including order status, tracking, customer lookup,
  account lookup, or knowledge-base retrieval.
- missing_info: vague or incomplete requests that lack enough detail to act safely.
- error: system failure, timeout, crash, service unavailable, processing failure.
- simple: general support questions answerable without tools or side effects.

Priority when multiple routes apply: risky > tool > missing_info > error > simple.

Important examples:
- "How do I reset my password?" is simple because it asks for instructions only.
- "Reset this customer's password" is risky because it asks the agent to change an account.
- "Refund this customer and send confirmation email" is risky.
- "Please lookup order status for order 12345" is tool.

Request: {query}
"""
    ai_log_message = "LLM structured classification completed"
    if _offline_fallback_enabled():
        result = _fallback_classification(query)
        llm_available = False
        ai_log_message = "LLM offline fallback requested; policy fallback used"
        error_message = "classify LLM skipped: offline fallback requested"
    else:
        llm = get_llm(temperature=0.0)
        classifier = llm.with_structured_output(ClassificationResult)
        try:
            result = classifier.invoke(prompt)
            llm_available = True
        except Exception as exc:  # pragma: no cover - exercised only on provider/network failure
            result = _fallback_classification(query)
            llm_available = False
            ai_log_message = "LLM classification failed; policy fallback used"
            error_message = f"classify LLM unavailable: {exc.__class__.__name__}"
    route = result.route
    lowered_query = query.lower()
    if (
        route == Route.RISKY.value
        and "password" in lowered_query
        and lowered_query.startswith(("how do i", "how can i", "how to"))
    ):
        result = ClassificationResult(
            route="simple",
            risk_level="low",
            reason="Password reset how-to requests are instructional and require no side effect.",
        )
        route = result.route
    risk_level = "high" if route == Route.RISKY.value else result.risk_level
    if route != Route.RISKY.value and risk_level == "high":
        risk_level = "medium" if route in {Route.TOOL.value, Route.ERROR.value} else "low"
    return {
        "route": route,
        "risk_level": risk_level,
        "messages": [f"classify:{route}"],
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified as {route}",
                risk_level=risk_level,
                reason=result.reason,
            )
        ],
        "ai_log": [
            _ai_log(
                state,
                "classify",
                ai_log_message,
                model=_llm_name(llm) if llm is not None else os.getenv("LLM_MODEL", "offline-fallback"),
                route=route,
                risk_level=risk_level,
                reason=result.reason,
                llm_available=llm_available,
            )
        ],
        **({"errors": [error_message]} if not llm_available else {}),
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call with deterministic transient failures."""
    route = state.get("route", Route.SIMPLE.value)
    attempt = int(state.get("attempt", 0))
    query = state.get("query", "")
    if route == Route.ERROR.value and attempt < 2:
        result = f"ERROR transient timeout while processing attempt {attempt}"
        event_type = "failed"
    elif route == Route.RISKY.value:
        action = state.get("proposed_action") or query
        result = f"SUCCESS approved risky action prepared for execution: {action}"
        event_type = "completed"
    elif route == Route.TOOL.value:
        result = f"SUCCESS lookup result for request: {query}. Mock status: request found and current."
        event_type = "completed"
    else:
        result = f"SUCCESS tool processed request: {query}"
        event_type = "completed"
    return {
        "tool_results": [result],
        "messages": [f"tool:{event_type}"],
        "events": [make_event("tool", event_type, result, attempt=attempt)],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate the latest tool result and decide whether retry is needed."""
    latest = (state.get("tool_results") or [""])[-1]
    evaluation_result = "needs_retry" if "ERROR" in latest.upper() else "success"
    return {
        "evaluation_result": evaluation_result,
        "messages": [f"evaluate:{evaluation_result}"],
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"tool result evaluation: {evaluation_result}",
                latest_result=latest,
            )
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using a real LLM grounded in workflow context."""
    query = state.get("query", "")
    route = state.get("route", Route.SIMPLE.value)
    llm = None
    context = {
        "route": route,
        "risk_level": state.get("risk_level", "unknown"),
        "tool_results": state.get("tool_results", []),
        "approval": state.get("approval"),
        "proposed_action": state.get("proposed_action"),
    }
    prompt = f"""
You are a concise support agent. Answer the user using only the provided workflow context.
Do not invent order details or claim an action was completed beyond the context.
If a risky action was approved, say it was approved and prepared, not permanently executed.

User request:
{query}

Workflow context:
{context}
"""
    ai_log_message = "LLM grounded response generated"
    if _offline_fallback_enabled():
        llm_available = False
        ai_log_message = "LLM offline fallback requested; grounded fallback used"
        error_message = "answer LLM skipped: offline fallback requested"
        if route == Route.RISKY.value:
            answer = (
                "The requested action is risky and was routed through approval. "
                "It has been approved and prepared according to the mock lab workflow."
            )
        elif state.get("tool_results"):
            answer = f"I found this grounded tool result: {state['tool_results'][-1]}"
        else:
            answer = "I can help with that request using the available support workflow context."
    else:
        llm = get_llm(temperature=0.2)
        try:
            response = llm.invoke(prompt)
            answer = _message_content(response).strip()
            llm_available = True
        except Exception as exc:  # pragma: no cover - exercised only on provider/network failure
            llm_available = False
            ai_log_message = "LLM answer failed; grounded fallback used"
            error_message = f"answer LLM unavailable: {exc.__class__.__name__}"
            if route == Route.RISKY.value:
                answer = (
                    "The requested action is risky and was routed through approval. "
                    "It has been approved and prepared according to the mock lab workflow."
                )
            elif state.get("tool_results"):
                answer = f"I found this grounded tool result: {state['tool_results'][-1]}"
            else:
                answer = "I can help with that request using the available support workflow context."
    return {
        "final_answer": answer,
        "messages": ["answer:completed"],
        "events": [make_event("answer", "completed", "final answer generated", route=route)],
        "ai_log": [
            _ai_log(
                state,
                "answer",
                ai_log_message,
                model=_llm_name(llm) if llm is not None else os.getenv("LLM_MODEL", "offline-fallback"),
                route=route,
                context_items=len(state.get("tool_results", [])),
                llm_available=llm_available,
            )
        ],
        **({"errors": [error_message]} if not llm_available else {}),
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    question = (
        "Could you share the specific account, order, or issue details you want help with?"
        if len(query.split()) <= 4
        else f"Could you provide the missing details needed to handle this request: {query}?"
    )
    return {
        "pending_question": question,
        "final_answer": question,
        "messages": ["clarify:pending"],
        "events": [make_event("clarify", "completed", "clarification requested")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    proposed_action = f"Review and approve this side-effecting support action: {query}"
    return {
        "proposed_action": proposed_action,
        "messages": ["risky_action:prepared"],
        "events": [
            make_event(
                "risky_action",
                "completed",
                "risky action prepared for approval",
                proposed_action=proposed_action,
            )
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Record a human-in-the-loop approval decision, mocked by default."""
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        resume_value = interrupt(
            {
                "action": state.get("proposed_action", ""),
                "query": state.get("query", ""),
                "instruction": "Approve or reject the proposed risky support action.",
            }
        )
        if isinstance(resume_value, dict):
            approved = bool(resume_value.get("approved", False))
            comment = str(resume_value.get("comment", "human review completed"))
            reviewer = str(resume_value.get("reviewer", "human-reviewer"))
        else:
            approved = bool(resume_value)
            comment = "human review completed"
            reviewer = "human-reviewer"
    else:
        approved = True
        reviewer = "mock-reviewer"
        comment = "Auto-approved for lab execution; real deployments should require human review."
    approval = ApprovalDecision(approved=approved, reviewer=reviewer, comment=comment).model_dump()
    return {
        "approval": approval,
        "messages": [f"approval:{'approved' if approved else 'rejected'}"],
        "events": [
            make_event(
                "approval",
                "completed",
                "approval decision recorded",
                approved=approved,
                reviewer=reviewer,
            )
        ],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Increment the retry attempt counter and record the failure path."""
    next_attempt = int(state.get("attempt", 0)) + 1
    message = f"retry attempt {next_attempt} after transient or error route"
    return {
        "attempt": next_attempt,
        "errors": [message],
        "messages": [f"retry:{next_attempt}"],
        "events": [make_event("retry", "completed", message, attempt=next_attempt)],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries are exhausted."""
    answer = (
        "I could not complete this request after the allowed retry attempts. "
        "The issue has been moved to dead letter handling for manual investigation."
    )
    return {
        "final_answer": answer,
        "messages": ["dead_letter:completed"],
        "events": [
            make_event(
                "dead_letter",
                "completed",
                "max retry attempts exhausted",
                attempt=state.get("attempt", 0),
                max_attempts=state.get("max_attempts", 0),
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event before END."""
    return {
        "messages": ["finalize:completed"],
        "events": [make_event("finalize", "completed", "workflow finished")],
    }
