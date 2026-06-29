"""Report generation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    rows = "\n".join(
        "| {scenario_id} | {expected_route} | {actual_route} | {success} | {retry_count} | {interrupt_count} |".format(
            scenario_id=item.scenario_id,
            expected_route=item.expected_route,
            actual_route=item.actual_route or "",
            success="yes" if item.success else "no",
            retry_count=item.retry_count,
            interrupt_count=item.interrupt_count,
        )
        for item in metrics.scenario_metrics
    )
    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: Vũ Văn Huy
- Student ID: 2A202600750
- Repo/commit: local workspace
- Date: {datetime.now(UTC).date().isoformat()}

## 2. Architecture

The graph is a LangGraph `StateGraph` with this flow:

`START -> intake -> classify -> conditional route`

Routes:
- `simple -> answer -> finalize -> END`
- `tool -> tool -> evaluate -> answer/retry -> finalize -> END`
- `missing_info -> clarify -> finalize -> END`
- `risky -> risky_action -> approval -> tool/clarify -> evaluate -> answer -> finalize -> END`
- `error -> retry -> tool/dead_letter -> evaluate -> retry/answer -> finalize -> END`

`classify_node` uses LLM structured output for route selection. `answer_node` uses an LLM to generate a grounded response from the query, tool results, approval decision, and proposed action.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `query` | overwrite | normalized user request |
| `route` | overwrite | current selected route |
| `risk_level` | overwrite | current risk classification |
| `attempt` | overwrite | bounded retry counter |
| `evaluation_result` | overwrite | retry-loop gate |
| `final_answer` | overwrite | final user-facing response |
| `pending_question` | overwrite | clarification flow output |
| `proposed_action` | overwrite | risky action awaiting approval |
| `approval` | overwrite | HITL approval decision |
| `messages` | append | compact workflow trace |
| `tool_results` | append | audit trail for tool calls |
| `errors` | append | retry and failure evidence |
| `events` | append | structured node audit events |
| `ai_log` | append | LLM usage evidence |

## 4. Scenario results

Summary:

| Metric | Value |
|---|---:|
| Total scenarios | {metrics.total_scenarios} |
| Success rate | {metrics.success_rate:.2%} |
| Avg nodes visited | {metrics.avg_nodes_visited:.2f} |
| Total retries | {metrics.total_retries} |
| Total interrupts/approvals | {metrics.total_interrupts} |
| Resume success | {metrics.resume_success} |

Per scenario:

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{rows}

## 5. Failure analysis

1. Retry or tool failure: transient tool failures are detected by `evaluate_node` and routed through `retry_or_fallback_node`. The retry path is bounded by `max_attempts`; exhausted requests go to `dead_letter_node`.
2. Risky action without approval: refund, delete, cancellation, and email actions route to `risky_action_node` and must pass through `approval_node` before any tool execution.

## 6. Persistence / recovery evidence

The graph accepts a checkpointer at compile time. The default lab config uses `MemorySaver`; the SQLite extension is implemented through `SqliteSaver` with WAL mode and can be enabled by setting `checkpointer: sqlite` in config.

## 7. Extension work

- SQLite checkpointer support implemented in `persistence.py`.
- AI usage log generated as `reports/ai_log.md` after scenario runs.
- Grading question set added in `grading_questions.json` with 10 retrieval-oriented checks.
- Offline unit tests cover routing, node behavior, report rendering, persistence options, and grading question schema.

## 8. Improvement plan

With one more day, the first production improvements would be a real approval UI, stronger tool contracts, state-history replay tests, and provider-specific prompt regression tests for hidden scenarios.
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")


def render_ai_log(records: list[dict[str, Any]]) -> str:
    """Render a compact AI call log for demo evidence."""
    if not records:
        return "# AI Log\n\nNo AI calls were recorded.\n"
    rows = "\n".join(
        "| {scenario} | {node} | {model} | {route} | {message} |".format(
            scenario=str(item.get("scenario_id", "")),
            node=str(item.get("node", "")),
            model=str(item.get("model", "")),
            route=str(item.get("route", "")),
            message=str(item.get("message", "")).replace("|", "\\|"),
        )
        for item in records
    )
    return f"""# AI Log

Generated: {datetime.now(UTC).isoformat()}

| Scenario | Node | Model | Route | Message |
|---|---|---|---|---|
{rows}
"""


def write_ai_log(records: list[dict[str, Any]], output_path: str | Path) -> None:
    """Write AI usage evidence to markdown."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ai_log(records), encoding="utf-8")
