# SMOKE_REPORT

Mode: smoke
Runs: 1
Valid answers: 1/1
Compile OK: 1/1
Trap passes: 1/1
Differentiation by task: `{"B13": false}`

## Rows

- B13 / DOC_CONTROL: valid=True compile=True trap=True coverage=0.667 files=['Subscriber.java'] bytes_read=6289 calls=9 wall=33.497s raw=results/raw/boundary_precision_repeat_r3_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}

## Gate

```json
{
  "at_least_2_of_3_valid_per_task": false,
  "trap_tests_distinguish_some_task": false,
  "zero_harness_runtime_errors": true
}
```

## Caveats

Machine audit is intentionally syntactic/behavioral-light: it checks compilation plus whether edits touch the expected layer and mention/modify key chain nodes. It does not execute a full Guava test suite or prove runtime rate-limit/retry/log behavior exhaustively.
