# Non-TMF Failure Review — B12/B13 Original Rerun

Generated: 2026-08-25 16:40 Asia/Shanghai

Scope: SOURCE_ONLY and DOC_CONTROL failures/noisy runs in `boundary_precision_targeted_B12_B13_original_rerun_v1`.

## Primary raw failures

### DOC_CONTROL — B12 rep1 — edit protocol failure, not semantic failure

Raw status: `valid=false`, `compile=false`, `trap=true`, primary=`edit_protocol_fail`.

Diff shows DOC_CONTROL reached the correct B12 semantic boundary:

```diff
-      method.invoke(target, checkNotNull(event));
+      Object checkedEvent = checkNotNull(event);
+      beforeSubscriberMethodInvoke();
+      method.invoke(target, checkedEvent);
```

Compile failed only because the helper definition edit did not match the current source signature:

```text
old text match count 0, expected 1
```

The attempted anchor omitted `throws InvocationTargetException`:

```java
@VisibleForTesting
void invokeSubscriberMethod(Object event) {
```

Actual fixture signature is:

```java
@VisibleForTesting
void invokeSubscriberMethod(Object event) throws InvocationTargetException {
```

Attribution: execution/edit anchor failure. Do not count as DOC_CONTROL semantic boundary failure.

### SOURCE_ONLY — B12 rep3 — real semantic boundary failure

Raw status: `valid=true`, `compile=true`, `trap=false`, primary=`semantic_boundary_fail`.

Diff:

```diff
+  private Object beforeSubscriberMethodInvoke(Object event) {
+    return event;
+  }
+
   @VisibleForTesting
   void invokeSubscriberMethod(Object event) throws InvocationTargetException {
     try {
-      method.invoke(target, checkNotNull(event));
+      method.invoke(target, beforeSubscriberMethodInvoke(checkNotNull(event)));
```

This hook is embedded as a wrapper argument to `method.invoke`. It does not create the required immediate boundary after argument preparation and before reflective invocation. It also records by transforming the argument expression rather than adding a clear boundary hook.

Attribution: genuine semantic boundary failure in SOURCE_ONLY.

### DOC_CONTROL — B12 rep3 — real semantic boundary failure

Raw status: `valid=true`, `compile=true`, `trap=false`, primary=`semantic_boundary_fail`.

Diff:

```diff
+  private void beforeReflectiveSubscriberMethodCall() {}
+
   @VisibleForTesting
   void invokeSubscriberMethod(Object event) throws InvocationTargetException {
     try {
+      beforeReflectiveSubscriberMethodCall();
       method.invoke(target, checkNotNull(event));
```

This hook runs before Java evaluates `checkNotNull(event)` as the Method.invoke argument. The required boundary is after the checked argument has been prepared and before the reflective call receives it.

Attribution: genuine semantic boundary failure in DOC_CONTROL.

## Noisy but raw-passing runs

These should remain raw pass, but they show the same agent/edit harness instability:

- `DOC_CONTROL B12 rep2`: `parse_or_invalid_action_noise` but final patch passed.
- `DOC_CONTROL B13 rep4`: one helper-definition edit failed after or during recovery, but final patch passed.
- `SOURCE_ONLY B13 rep5`: `parse_or_invalid_action_noise` but final patch passed.
- `DOC_CONTROL B13 rep5`: one edit failed first, then recovery produced a passing final patch.

## Comparison with TMF_CLAIMS

TMF_CLAIMS raw failures in the same rerun were all protocol/edit/source-shape failures:

- `B12 rep1`: semantically correct B12 boundary; helper definition insertion failed.
- `B12 rep3`: semantically correct B12 boundary; helper definition insertion failed.
- `B13 rep3`: no effective source change because the agent assumed the wrong source shape.

By contrast, SOURCE_ONLY and DOC_CONTROL each had one true B12 semantic failure.

## Adjusted interpretation

- SOURCE_ONLY: raw pass `9/10`; semantic-known `9 pass / 1 fail`.
- DOC_CONTROL: raw pass `8/10`; at least one raw failure is protocol-only, and one is genuine semantic fail; raw-passing noisy runs show recovery instability.
- TMF_CLAIMS: raw pass `7/10`; semantic-known `7 pass / 0 fail`, protocol-unclean/unknown `3`.

The fair conclusion is not that TMF underperformed semantically. The fair conclusion is:

> TMF avoided the true B12 semantic boundary mistakes seen in SOURCE_ONLY and DOC_CONTROL, but the measured raw pass rate was depressed by agent/edit protocol failures.

## Harness implication

Future benchmark summaries should report three separate views:

1. Raw pass rate.
2. Protocol-clean pass rate.
3. Semantic-adjusted score / semantic failure count.

Only the third view should be used to judge whether TMF boundary knowledge failed.
