# SMOKE_REPORT

Mode: smoke
Runs: 6
Valid answers: 5/6
Compile OK: 6/6
Trap passes: 4/6
Differentiation by task: `{"B01": true, "B02": false}`

## Rows

- B01 / SOURCE_ONLY: valid=True compile=True trap=False coverage=0.0 files=['Subscriber.java'] bytes_read=9093 calls=9 wall=138.772s raw=results/raw/smoke/B01__SOURCE_ONLY.raw.json
  - trap_reason={"has_subscriber_scope": true, "not_post_only": true, "async_aware": false}
- B01 / TMF_CLAIMS: valid=False compile=True trap=False coverage=0.0 files=[] bytes_read=0 calls=1 wall=140.09s raw=results/raw/smoke/B01__TMF_CLAIMS.raw.json
  - trap_reason={"has_subscriber_scope": false, "not_post_only": false, "async_aware": false}
- B01 / DOC_CONTROL: valid=True compile=True trap=True coverage=0.143 files=['Subscriber.java'] bytes_read=6083 calls=5 wall=239.986s raw=results/raw/smoke/B01__DOC_CONTROL.raw.json
  - trap_reason={"has_subscriber_scope": true, "not_post_only": true, "async_aware": true}
- B02 / SOURCE_ONLY: valid=True compile=True trap=True coverage=0.5 files=['Subscriber.java'] bytes_read=616 calls=5 wall=101.843s raw=results/raw/smoke/B02__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "retry_loop": true, "final_handler_preserved": true, "not_eventbus_only": true}
- B02 / TMF_CLAIMS: valid=True compile=True trap=True coverage=0.5 files=['Subscriber.java'] bytes_read=616 calls=4 wall=51.696s raw=results/raw/smoke/B02__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "retry_loop": true, "final_handler_preserved": true, "not_eventbus_only": true}
- B02 / DOC_CONTROL: valid=True compile=True trap=True coverage=0.333 files=['Subscriber.java'] bytes_read=2623 calls=5 wall=61.828s raw=results/raw/smoke/B02__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "retry_loop": true, "final_handler_preserved": true, "not_eventbus_only": true}

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
