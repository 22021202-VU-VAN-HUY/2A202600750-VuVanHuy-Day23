import json
from pathlib import Path

import pytest

from langgraph_agent_lab.metrics import metric_from_state, summarize_metrics
from langgraph_agent_lab.nodes import (
    answer_node,
    approval_node,
    ask_clarification_node,
    classify_node,
    dead_letter_node,
    evaluate_node,
    finalize_node,
    retry_or_fallback_node,
    risky_action_node,
    tool_node,
)
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.report import render_ai_log, render_report
from langgraph_agent_lab.state import Route, Scenario, initial_state


def test_grading_questions_json_is_complete():
    payload = json.loads(Path("grading_questions.json").read_text(encoding="utf-8"))

    assert len(payload) == 10
    assert [item["id"] for item in payload] == [f"gq_d10_{index:02d}" for index in range(1, 11)]

    required_keys = {
        "id",
        "question",
        "must_contain_any",
        "must_not_contain",
        "expect_top1_doc_id",
        "grading_criteria",
    }
    expected_docs = {
        "access_control_sop",
        "hr_leave_policy",
        "it_helpdesk_faq",
        "policy_refund_v4",
        "sla_p1_2026",
    }
    for item in payload:
        assert required_keys <= set(item)
        assert item["question"].strip()
        assert item["must_contain_any"]
        assert isinstance(item["must_not_contain"], list)
        assert item["expect_top1_doc_id"] in expected_docs
        assert item["grading_criteria"]


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("How do I reset my password?", Route.SIMPLE.value),
        ("Please lookup order status for order 123", Route.TOOL.value),
        ("Refund this customer", Route.RISKY.value),
        ("Can you fix it?", Route.MISSING_INFO.value),
        ("Timeout failure while processing request", Route.ERROR.value),
    ],
)
def test_classify_node_offline_fallback_routes(monkeypatch, query, route):
    monkeypatch.setenv("LLM_OFFLINE_FALLBACK", "true")
    scenario = Scenario(id=f"classify-{route}", query=query, expected_route=Route(route))
    state = initial_state(scenario)

    result = classify_node(state)

    assert result["route"] == route
    assert result["events"][0]["node"] == "classify"
    assert result["ai_log"][0]["llm_available"] is False


def test_tool_evaluate_retry_and_dead_letter_flow():
    scenario = Scenario(
        id="retry",
        query="Timeout failure while processing request",
        expected_route=Route.ERROR,
        max_attempts=1,
    )
    state = initial_state(scenario)
    state["route"] = Route.ERROR.value

    retry_update = retry_or_fallback_node(state)
    state.update(retry_update)
    tool_update = tool_node(state)
    state["tool_results"].extend(tool_update["tool_results"])
    evaluate_update = evaluate_node(state)
    state.update(evaluate_update)
    dead_letter_update = dead_letter_node(state)
    finalize_update = finalize_node(state)

    assert retry_update["attempt"] == 1
    assert state["evaluation_result"] == "needs_retry"
    assert "could not complete" in dead_letter_update["final_answer"]
    assert finalize_update["events"][0]["node"] == "finalize"


def test_risky_approval_and_answer_offline_fallback(monkeypatch):
    monkeypatch.setenv("LLM_OFFLINE_FALLBACK", "true")
    scenario = Scenario(
        id="risky",
        query="Refund this customer",
        expected_route=Route.RISKY,
        requires_approval=True,
    )
    state = initial_state(scenario)
    state["route"] = Route.RISKY.value

    state.update(risky_action_node(state))
    state.update(approval_node(state))
    state["tool_results"].extend(tool_node(state)["tool_results"])
    answer_update = answer_node(state)

    assert state["approval"]["approved"] is True
    assert "Review and approve" in state["proposed_action"]
    assert "approved and prepared" in answer_update["final_answer"]


def test_clarification_node_returns_pending_question():
    scenario = Scenario(id="missing", query="Fix it", expected_route=Route.MISSING_INFO)
    state = initial_state(scenario)

    result = ask_clarification_node(state)

    assert result["pending_question"] == result["final_answer"]
    assert result["events"][0]["node"] == "clarify"


def test_report_and_ai_log_include_student_and_run_evidence():
    metric = metric_from_state(
        {
            "scenario_id": "S01",
            "route": "simple",
            "final_answer": "ok",
            "events": [{"node": "answer"}],
            "errors": [],
            "approval": None,
        },
        expected_route="simple",
        approval_required=False,
    )
    report = render_report(summarize_metrics([metric]))
    ai_log = render_ai_log(
        [{"scenario_id": "S01", "node": "classify", "model": "offline", "route": "simple", "message": "ok"}]
    )

    assert "Vũ Văn Huy" in report
    assert "2A202600750" in report
    assert "| S01 | simple | simple | yes | 0 | 0 |" in report
    assert "| S01 | classify | offline | simple | ok |" in ai_log


def test_build_checkpointer_none_and_unknown_kind():
    assert build_checkpointer("none") is None
    with pytest.raises(ValueError, match="Unknown checkpointer kind"):
        build_checkpointer("invalid")
