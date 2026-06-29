# Day 08 Lab Report

## 1. Team / student

- Name: Vũ Văn Huy
- Student ID: 2A202600750
- Repo/commit: local workspace
- Date: 2026-06-29

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
| Total scenarios | 7 |
| Success rate | 100.00% |
| Avg nodes visited | 6.43 |
| Total retries | 3 |
| Total interrupts/approvals | 2 |
| Resume success | False |

Test evidence:

- `.venv\Scripts\python.exe -m pytest`: 30 passed, 6 skipped.
- `.venv\Scripts\python.exe -m ruff check .`: all checks passed.

Per scenario:

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | yes | 0 | 0 |
| S02_tool | tool | tool | yes | 0 | 0 |
| S03_missing | missing_info | missing_info | yes | 0 | 0 |
| S04_risky | risky | risky | yes | 0 | 1 |
| S05_error | error | error | yes | 2 | 0 |
| S06_delete | risky | risky | yes | 0 | 1 |
| S07_dead_letter | error | error | yes | 1 | 0 |

## 5. Failure analysis

1. Retry or tool failure: transient tool failures are detected by `evaluate_node` and routed through `retry_or_fallback_node`. The retry path is bounded by `max_attempts`; exhausted requests go to `dead_letter_node`.
2. Risky action without approval: refund, delete, cancellation, and email actions route to `risky_action_node` and must pass through `approval_node` before any tool execution.

## 6. Persistence / recovery evidence

The graph accepts a checkpointer at compile time. The default lab config uses `MemorySaver`; the SQLite extension is implemented through `SqliteSaver` with WAL mode and can be enabled by setting `checkpointer: sqlite` in config.

## 7. Extension work

- SQLite checkpointer support implemented in `persistence.py`.
- AI usage log generated as `reports/ai_log.md` after scenario runs.
- Grading question set added in `grading_questions.json` with 10 retrieval-oriented checks across refund policy, P1 SLA, IT helpdesk, HR leave, and access-control SOP documents.
- Additional offline test coverage added for routing-adjacent node behavior, retry/dead-letter flow, HITL approval, report rendering, and grading question schema validation.

## 8. Improvement plan

With one more day, the first production improvements would be a real approval UI, stronger tool contracts, state-history replay tests, and provider-specific prompt regression tests for hidden scenarios.
