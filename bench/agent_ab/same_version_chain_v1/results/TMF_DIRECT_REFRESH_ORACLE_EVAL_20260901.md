# TMF Direct Refresh Oracle Evaluation — 2026-09-01

This evaluates TMF freshness/stale-slice planning directly, before any agent edit loop. Off-track M22–M25 artifacts are excluded.

## Summary

```json
{
  "cases": 3,
  "pass": 3,
  "stale_withheld": 3,
  "avg_required_precision": 0.5397,
  "avg_tiered_useful_precision": 0.9444,
  "avg_required_recall": 1.0,
  "avg_side_effect_recall": 1.0
}
```

## Cases

### M15
- pass: True
- stale withheld: True
- strict required precision/recall: 0.3333 / 1.0
- tiered useful precision: 0.8333
- side-effect recall: 1.0
- missing required: []
- safe extra required: ['src/main/java/com/example/order/EventPublisher.java::EventPublisher.publish', 'src/main/java/com/example/order/OrderRepository.java::OrderRepository.save', 'src/main/java/com/example/order/OrderService.java::OrderService.persistAndPublish']
- noise extra required: []
- unclassified extra required: ['src/main/java/com/example/order/Order.java::Order.getId']

### M16
- pass: True
- stale withheld: True
- strict required precision/recall: 0.5714 / 1.0
- tiered useful precision: 1.0
- side-effect recall: 1.0
- missing required: []
- safe extra required: ['src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getOrderId', 'src/main/java/com/example/order/PaymentIntentRepository.java::PaymentIntentRepository.save', 'src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.requiresManualReview']
- noise extra required: []
- unclassified extra required: []

### M21
- pass: True
- stale withheld: True
- strict required precision/recall: 0.7143 / 1.0
- tiered useful precision: 1.0
- side-effect recall: 1.0
- missing required: []
- safe extra required: ['src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getOrderId', 'src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.requiresManualReview']
- noise extra required: []
- unclassified extra required: []

## Interpretation

This is closer to TMF's design intent than hidden-JUnit agent tasks: it checks stale invalidation, localized reread planning, and side-effect awareness directly. Strict precision counts only oracle-essential symbols; tiered useful precision also counts safety-relevant side-effect/contract reads. In this retained set, the remaining clear noise is M15's class/constructor reads, which suggests the next optimization target is ranking/filtering current-source symbol supplements rather than changing stale invalidation.
