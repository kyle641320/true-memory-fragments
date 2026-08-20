# same_version_chain_v1 EXECUTION_NOTES

Experiment created 2026-08-20.

Design: same Guava EventBus source for all arms. Phase A materialises structured call-chain claims into `.tmf/same_version_chain_claims.json`; Phase B sends identical coding task to all arms. SOURCE_ONLY receives no chain injection, TMF_CLAIMS receives structured source-anchored claims, DOC_CONTROL receives equivalent plain-text chain documentation.

Implementation notes will be appended by runner.

## Run smoke-n2

Wrote `results/smoke-n2.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 6, "valid_answers": 4, "compile_ok": 6, "trap_passes": 1, "differentiation_by_task": {"B01": false, "B02": true}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": false, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}

## Smoke failure decision

Smoke `smoke-n2` completed with zero runtime/harness crashes but failed the valid-answer gate: B02 produced only 1/3 valid coding edits. Full run was not started. See `STOP_DECISION.md` and `results/SMOKE_REPORT.md`.

## Run smoke

Wrote `results/smoke.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 6, "valid_answers": 5, "compile_ok": 6, "trap_passes": 4, "differentiation_by_task": {"B01": true, "B02": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}
