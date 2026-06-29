# AI Log

Generated: 2026-06-29T03:22:16.032276+00:00

| Scenario | Node | Model | Route | Message |
|---|---|---|---|---|
| S01_simple | classify | gemini-2.5-flash | simple | LLM classification failed; policy fallback used |
| S01_simple | answer | gemini-2.5-flash | simple | LLM answer failed; grounded fallback used |
| S02_tool | classify | gemini-2.5-flash | tool | LLM classification failed; policy fallback used |
| S02_tool | answer | gemini-2.5-flash | tool | LLM answer failed; grounded fallback used |
| S03_missing | classify | gemini-2.5-flash | missing_info | LLM classification failed; policy fallback used |
| S04_risky | classify | gemini-2.5-flash | risky | LLM classification failed; policy fallback used |
| S04_risky | answer | gemini-2.5-flash | risky | LLM answer failed; grounded fallback used |
| S05_error | classify | gemini-2.5-flash | error | LLM classification failed; policy fallback used |
| S05_error | answer | gemini-2.5-flash | error | LLM answer failed; grounded fallback used |
| S06_delete | classify | gemini-2.5-flash | risky | LLM classification failed; policy fallback used |
| S06_delete | answer | gemini-2.5-flash | risky | LLM answer failed; grounded fallback used |
| S07_dead_letter | classify | gemini-2.5-flash | error | LLM classification failed; policy fallback used |
