# v4 repeated subagent run plan

Do not run this blindly in the main session. Use push-based isolated subagents or a reliable broker. Suggested minimum:

- For each task `RV4F01`–`RV4F03`, run both arms once first as smoke.
- If smoke transport is valid, repeat 3 times per arm.
- Score only completed payloads with required `METRICS_JSON` and exact citations.
- Report raw pass, protocol-clean pass, semantic-adjusted pass, and cost/efficiency separately.

Target claim levels:

- `valid_tasks=3` deterministic: already established by `evaluate_deterministic.py`.
- Small stability evidence: all 3 fixtures × 3 repeats per arm.
- Do not claim TMF correctness superiority unless paired semantic-clean TMF beats SOURCE_ONLY on at least one fixture and controls do not explain it away.
