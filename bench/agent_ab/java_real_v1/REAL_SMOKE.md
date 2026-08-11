# Java real-v1 real smoke record

Recorded: 2026-08-11 (Asia/Shanghai). This file preserves the completed run's observed telemetry; it does not rerun or alter the frozen protocol.

## Valid samples

| arm | status | source files | source lines | tool calls | note |
|---|---:|---:|---:|---:|---|
| SOURCE_ONLY | valid | 8 | 396 | 12 | Correct answer; real source-only run. |
| TMF_MAP | valid | 8 | 724 | 4 | Correct answer; repo-routed Petclinic TMF run. Retrieval used the repository-pinned wrapper. |

## Invalid sample

The first TMF attempt was routed to the globally registered **Zhihu** store rather than Petclinic. It is **void / excluded**, must not be treated as a TMF_MAP observation, and must not enter accuracy, cost, line-read, call-count, or comparative aggregates. Its only valid use is routing-failure evidence.

## Interpretation guardrails

- These are two completed smoke observations, not a powered benchmark result.
- Correctness is preserved in both valid arms. The valid TMF_MAP observation reduced tool calls (12 → 4) but read more source lines (396 → 724); do not claim an across-the-board efficiency win.
- `routing_smoke.json` verifies the pinned Petclinic store at commit `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`; it does not repair the invalid first sample.
- No frozen task, golden, metric, engine, parser, or build adapter was changed.
