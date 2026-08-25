# SMOKE_REPORT

Mode: smoke
Runs: 1
Valid answers: 1/1
Compile OK: 1/1
Trap passes: 1/1
Differentiation by task: `{"B11": false}`

## Rows

- B11 / TMF_CLAIMS: valid=True compile=True trap=True coverage=0.143 files=['Dispatcher.java'] bytes_read=12406 calls=12 wall=26.215s raw=results/raw/boundary_precision_B11_TMF_CLAIMS_v2/B11__TMF_CLAIMS.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 3, "not_subscriber_only": true, "not_eventbus_only": true}

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
