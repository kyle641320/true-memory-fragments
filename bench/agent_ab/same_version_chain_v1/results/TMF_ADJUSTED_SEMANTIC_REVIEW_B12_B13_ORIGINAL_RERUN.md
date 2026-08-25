# TMF Adjusted Semantic Review — B12/B13 Original Rerun


## Executive conclusion

The TMF_CLAIMS raw failures in the original B12/B13 rerun are **not TMF semantic failures**. They are agent/edit protocol or source-shape failures. The adjusted semantic-known score for TMF_CLAIMS is `7 pass / 0 fail`; SOURCE_ONLY and DOC_CONTROL each have one genuine B12 semantic boundary failure.

Scope: original B12/B13 task and TMF claim wording, 5 repeats × 3 arms × 2 tasks.

Purpose: answer whether TMF failures in the original rerun are TMF semantic failures or execution/protocol failures.

## SOURCE_ONLY

- Raw pass: 9/10
- Protocol-clean raw pass: 8/9 (protocol-clean denominator excludes edit/compile/no-effect/no-final/parse/tool noise)
- Semantic-known pass/fail: 9 pass / 1 fail; protocol-unclean/unknown: 0

## TMF_CLAIMS

- Raw pass: 7/10
- Protocol-clean raw pass: 6/6 (protocol-clean denominator excludes edit/compile/no-effect/no-final/parse/tool noise)
- Semantic-known pass/fail: 7 pass / 0 fail; protocol-unclean/unknown: 3

## DOC_CONTROL

- Raw pass: 8/10
- Protocol-clean raw pass: 5/6 (protocol-clean denominator excludes edit/compile/no-effect/no-final/parse/tool noise)
- Semantic-known pass/fail: 8 pass / 1 fail; protocol-unclean/unknown: 1

## TMF_CLAIMS failure review

### rep 1 B12 — primary=edit_protocol_fail, adjusted_semantic=None, reason=protocol_unclean

- raw_path: `results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json`
- audit: valid=False, compile=False, trap=True
- categories: `['edit_protocol_fail', 'compile_fail']`
- Semantic review: TMF produced the correct B12 boundary shape (`checkNotNull` hoisted before hook, then `Method.invoke`), but helper definition insertion failed, so this is not a TMF boundary failure.

```diff
--- a/Subscriber.java
+++ b/Subscriber.java
@@ -81,7 +81,9 @@
   @VisibleForTesting
   void invokeSubscriberMethod(Object event) throws InvocationTargetException {
     try {
-      method.invoke(target, checkNotNull(event));
+      Object nonNullEvent = checkNotNull(event);
+      beforeSubscriberMethodInvoke();
+      method.invoke(target, nonNullEvent);
     } catch (IllegalArgumentException e) {
       throw new Error("Method rejected target/argument: " + event, e);
     } catch (IllegalAccessException e) {
```

Tool/compile errors:
- `{'action': 'edit', 'path': 'Subscriber.java', 'old': '  @VisibleForTesting\n  void invokeSubscriberMethod(Object event) {', 'new': '  private static void beforeSubscriberMethodInvoke() {}\n\n  @VisibleForTesting\n  void invokeSubscriberMethod(Object event) {'}` -> `{'error': 'old text match count 0, expected 1'}`
- `{'action': 'compile'}` -> `{'ok': False, 'exit': 1, 'stderr': '/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/same_version_chain_v1/results/work/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS/Subscriber.java:85: error: cannot find symbol\n      beforeSubscriberMethodInvoke();\n      ^\n  symbol:   method beforeSubscriberMethodInvoke()\n  location: class Subscriber\n1 error\n', 'stdout': ''}`

### rep 3 B12 — primary=edit_protocol_fail, adjusted_semantic=None, reason=protocol_unclean

- raw_path: `results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json`
- audit: valid=False, compile=False, trap=True
- categories: `['edit_protocol_fail', 'compile_fail']`
- Semantic review: TMF produced the correct B12 boundary shape (`checkNotNull` hoisted before hook, then `Method.invoke`), but helper definition insertion failed, so this is not a TMF boundary failure.

```diff
--- a/Subscriber.java
+++ b/Subscriber.java
@@ -81,7 +81,9 @@
   @VisibleForTesting
   void invokeSubscriberMethod(Object event) throws InvocationTargetException {
     try {
-      method.invoke(target, checkNotNull(event));
+      Object checkedEvent = checkNotNull(event);
+      beforeReflectiveSubscriberMethodCall();
+      method.invoke(target, checkedEvent);
     } catch (IllegalArgumentException e) {
       throw new Error("Method rejected target/argument: " + event, e);
     } catch (IllegalAccessException e) {
```

Tool/compile errors:
- `{'action': 'edit', 'path': 'Subscriber.java', 'old': '  void invokeSubscriberMethod(Object event) throws InvocationTargetException {', 'new': '  private static void beforeReflectiveSubscriberMethodCall() {}\n\n  void invokeSubscriberMethod(Object event) throws InvocationTargetException {'}` -> `{'error': 'old text match count 2, expected 1'}`
- `{'action': 'compile'}` -> `{'ok': False, 'exit': 1, 'stderr': '/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/same_version_chain_v1/results/work/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS/Subscriber.java:85: error: cannot find symbol\n      beforeReflectiveSubscriberMethodCall();\n      ^\n  symbol:   method beforeReflectiveSubscriberMethodCall()\n  location: class Subscriber\n1 error\n', 'stdout': ''}`
- `{'action': 'edit', 'path': 'Subscriber.java', 'old': '  @VisibleForTesting\n  private static void beforeReflectiveSubscriberMethodCall() {}\n\n  void invokeSubscriberMethod(Object event) throws InvocationTargetException {', 'new': '  private static void beforeReflectiveSubscriberMethodCall() {}\n\n  @VisibleForTesting\n  void invokeSubscriberMethod(Object event) throws InvocationTargetException {'}` -> `{'error': 'old text match count 0, expected 1'}`
- `{'action': 'compile'}` -> `{'ok': False, 'exit': 1, 'stderr': '/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/same_version_chain_v1/results/work/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS/Subscriber.java:85: error: cannot find symbol\n      beforeReflectiveSubscriberMethodCall();\n      ^\n  symbol:   method beforeReflectiveSubscriberMethodCall()\n  location: class Subscriber\n1 error\n', 'stdout': ''}`

### rep 3 B13 — primary=edit_protocol_fail, adjusted_semantic=None, reason=protocol_unclean

- raw_path: `results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json`
- audit: valid=False, compile=True, trap=False
- categories: `['edit_protocol_fail', 'no_effect_false_completion']`
- Semantic review: no source diff was produced because edits targeted the wrong current source shape (`return method.invoke(...)` / `private Object invokeSubscriberMethod`) and failed exact matching; this is source-shape/edit protocol failure, not evidence of wrong TMF boundary.

Tool/compile errors:
- `{'action': 'edit', 'path': 'Subscriber.java', 'old': '      return method.invoke(target, checkNotNull(event));', 'new': '      Object result = method.invoke(target, checkNotNull(event));\n      recordSubscriberMethodNormalReturn();\n      return result;'}` -> `{'error': 'old text match count 0, expected 1'}`
- `{'action': 'edit', 'path': 'Subscriber.java', 'old': '  private Object invokeSubscriberMethod(Object event) throws InvocationTargetException {', 'new': '  private static void recordSubscriberMethodNormalReturn() {}\n\n  private Object invokeSubscriberMethod(Object event) throws InvocationTargetException {'}` -> `{'error': 'old text match count 0, expected 1'}`

## Conclusion

- TMF_CLAIMS has 3 raw failures in this original rerun, but all are protocol/edit/source-shape failures.
- B12 rep1 and rep3 reached the correct semantic boundary; compile failed only because helper definitions were not inserted after exact-text anchor failures.
- B13 rep3 made no effective source edit because it assumed a return-expression source shape that was not present in the current fixture.
- Therefore these failures should not be counted against TMF semantic correctness. They should be counted against the agent/edit harness and excluded or separately reported when evaluating TMF.
- The report should distinguish raw pass rate from protocol-clean and semantic-adjusted scores.
