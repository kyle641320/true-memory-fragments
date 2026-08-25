# SMOKE_REPORT

Mode: smoke
Runs: 3
Valid answers: 3/3
Compile OK: 3/3
Trap passes: 2/3
Differentiation by task: `{"B07": true}`

## Rows

- B07 / SOURCE_ONLY: valid=True compile=True trap=False coverage=0.167 files=['Subscriber.java'] bytes_read=6766 calls=10 wall=24.59s raw=results/raw/smoke/B07__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": false, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / TMF_CLAIMS: valid=True compile=True trap=True coverage=0.167 files=['Subscriber.java'] bytes_read=13092 calls=15 wall=52.226s raw=results/raw/smoke/B07__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / DOC_CONTROL: valid=True compile=True trap=True coverage=0.167 files=['Subscriber.java'] bytes_read=9097 calls=14 wall=61.482s raw=results/raw/smoke/B07__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}

## Gate

```json
{
  "at_least_2_of_3_valid_per_task": true,
  "trap_tests_distinguish_some_task": true,
  "zero_harness_runtime_errors": true
}
```

## Caveats

Machine audit is intentionally syntactic/behavioral-light: it checks compilation plus whether edits touch the expected layer and mention/modify key chain nodes. It does not execute a full Guava test suite or prove runtime rate-limit/retry/log behavior exhaustively.
