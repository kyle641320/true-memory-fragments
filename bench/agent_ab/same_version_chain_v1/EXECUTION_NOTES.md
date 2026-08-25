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

## Run b02-expanded-step1-retry2-20260824T164155

Wrote `results/b02-expanded-step1-retry2-20260824T164155.json` and `results/FULL_REPORT.md`. Summary: {"mode": "full", "runs": 9, "valid_answers": 2, "compile_ok": 7, "trap_passes": 3, "differentiation_by_task": {"B01": true, "B02": true, "B03": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": false, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}

## Run debug-b02-tmf-multiaction-20260824T171054

Wrote `results/debug-b02-tmf-multiaction-20260824T171054.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 1, "valid_answers": 1, "compile_ok": 1, "trap_passes": 1, "differentiation_by_task": {"B02": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": false, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run b02-expanded-step1-fixed2-20260824T172731

Wrote `results/b02-expanded-step1-fixed2-20260824T172731.json` and `results/FULL_REPORT.md`. Summary: {"mode": "full", "runs": 9, "valid_answers": 3, "compile_ok": 9, "trap_passes": 3, "differentiation_by_task": {"B01": true, "B02": false, "B03": true}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": false, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}

## Run debug-b02-tmf-fuzzy-20260824T175115

Wrote `results/debug-b02-tmf-fuzzy-20260824T175115.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 1, "valid_answers": 1, "compile_ok": 1, "trap_passes": 1, "differentiation_by_task": {"B02": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": false, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run b02-rerun-after-fix-20260824T182117

Wrote `results/b02-rerun-after-fix-20260824T182117.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 2, "compile_ok": 3, "trap_passes": 2, "differentiation_by_task": {"B02": true}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}

## Run b04-step1-controlled-20260824T203508

Wrote `results/b04-step1-controlled-20260824T203508.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 2, "compile_ok": 2, "trap_passes": 3, "differentiation_by_task": {"B04": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run b05-step1-controlled-20260824T203955

Wrote `results/b05-step1-controlled-20260824T203955.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 2, "compile_ok": 2, "trap_passes": 3, "differentiation_by_task": {"B05": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run b06-step1-controlled-20260825T003740

Wrote `results/b06-step1-controlled-20260825T003740.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 3, "compile_ok": 3, "trap_passes": 0, "differentiation_by_task": {"B06": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run b07-execution-start-boundary-20260825T011125

Wrote `results/b07-execution-start-boundary-20260825T011125.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 2, "compile_ok": 2, "trap_passes": 0, "differentiation_by_task": {"B07": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run smoke

Wrote `results/smoke.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 3, "compile_ok": 3, "trap_passes": 0, "differentiation_by_task": {"B07": false}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": false, "zero_harness_runtime_errors": true}}

## Run smoke

Wrote `results/smoke.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 2, "compile_ok": 2, "trap_passes": 1, "differentiation_by_task": {"B07": true}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}

## Run smoke

Wrote `results/smoke.json` and `results/SMOKE_REPORT.md`. Summary: {"mode": "smoke", "runs": 3, "valid_answers": 3, "compile_ok": 3, "trap_passes": 2, "differentiation_by_task": {"B07": true}, "zero_harness_errors": true, "smoke_gate": {"at_least_2_of_3_valid_per_task": true, "trap_tests_distinguish_some_task": true, "zero_harness_runtime_errors": true}}
