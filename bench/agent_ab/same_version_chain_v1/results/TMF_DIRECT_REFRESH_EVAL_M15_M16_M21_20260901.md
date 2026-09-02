# TMF Direct Refresh Evaluation — M15/M16/M21 R4 retained evidence

This report separates TMF mechanism signals from downstream agent task success. It excludes quarantined off-track M22–M25 artifacts.

## Summary

```json
{
  "rows": 12,
  "withheld_expected": 12,
  "withheld_ok": 12,
  "post_ok": 9,
  "semantic_pass": 9
}
```

## Rows
- OUTBOX_M15 r1 TMF_STALE_GATED: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/EventPublisher.java', 'src/main/java/com/example/order/OrderService.java', 'src/test/java/com/example/order/OrderServiceContractTest.java']
- OUTBOX_M15 r2 TMF_STALE_GATED: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/EventPublisher.java', 'src/main/java/com/example/order/OrderService.java', 'src/test/java/com/example/order/OrderServiceContractTest.java']
- OUTBOX_M15 r3 TMF_STALE_GATED: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/EventPublisher.java', 'src/main/java/com/example/order/OrderService.java', 'src/test/java/com/example/order/OrderServiceContractTest.java']
- OUTBOX_M15 r4 TMF_STALE_GATED: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/EventPublisher.java', 'src/main/java/com/example/order/OrderService.java', 'src/test/java/com/example/order/OrderServiceContractTest.java']
- ORDER_M16 r1 TMF_REFRESHED_MAP: withheld=True post_ok=False semantic=False failure=hidden_oracle_fail files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M16 r2 TMF_REFRESHED_MAP: withheld=True post_ok=False semantic=False failure=hidden_oracle_fail files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntent.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M16 r3 TMF_REFRESHED_MAP: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntent.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M16 r4 TMF_REFRESHED_MAP: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntent.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M21 r1 TMF_REFRESHED_MAP: withheld=True post_ok=False semantic=False failure=hidden_oracle_fail files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M21 r2 TMF_REFRESHED_MAP: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M21 r3 TMF_REFRESHED_MAP: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntent.java', 'src/main/java/com/example/order/PaymentIntentService.java']
- ORDER_M21 r4 TMF_REFRESHED_MAP: withheld=True post_ok=True semantic=True failure=pass files=['src/main/java/com/example/order/Order.java', 'src/main/java/com/example/order/OrderService.java', 'src/main/java/com/example/order/PaymentIntentService.java']

## Interpretation

- Freshness/containment: stale TMF claims were withheld whenever expected in these retained runs.
- Downstream task success is mixed and must not be treated as pure TMF semantic-map quality.
- Next true core test should construct a deterministic oracle for locator/map quality: expected stale binding, expected affected symbols, and expected fresh neighbor set, with precision/recall scored before any agent edit loop.
