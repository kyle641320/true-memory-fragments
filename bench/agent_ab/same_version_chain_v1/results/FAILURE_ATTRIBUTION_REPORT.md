# Failure Attribution Report — Boundary Precision Repeats

Generated: 2026-08-25 13:34 Asia/Shanghai

## Scope

This report attributes failures in `boundary_precision_repeats.json` for the same-version-chain boundary precision experiment.

Input files:

- `results/boundary_precision_repeats.json`
- `results/BOUNDARY_PRECISION_REPEATS_REPORT.md`
- raw run transcripts referenced by `raw_path`
- `tasks.json`
- `runner.py`

## Headline

The observed result should **not** be read as simply "TMF claims failed".

A substantial share of failures are execution/harness noise:

- failed `edit` operations were not repaired;
- final answers were accepted even after compile failure;
- some runs claimed completion despite no effective source change;
- validator pass/fail conflated semantic boundary failure with protocol/tool failure.

The clearest real TMF weakness is narrower: current claim text does not provide enough structured transformation guidance for expression-level Java boundaries, especially B12/B13.

## Aggregate result

| Arm | Total | Pass | Valid | Compile | Trap |
|---|---:|---:|---:|---:|---:|
| TMF_CLAIMS | 21 | 15 | 17 | 19 | 15 |
| DOC_CONTROL | 21 | 17 | 18 | 19 | 19 |
| SOURCE_ONLY | 21 | 14 | 16 | 19 | 15 |

DOC_CONTROL won this repeat set, but it is not a weak baseline: it contains task-specific natural-language guidance close to the TMF claims. TMF currently behaves more like an alternate document than a structurally stronger locator/constraint layer.

## Failure bucket summary

### TMF_CLAIMS

- `unrecovered_edit_error`: 4 (`B07 r1`, `B12 r1`, `B13 r1`, `B13 r2`)
- `compile_final_fail`: 2 (`B07 r1`, `B11 r3`)
- `no_effect_due_edit_error`: 2 (`B12 r1`, `B13 r1`)
- `semantic_boundary_fail`: 2 (`B12 r3`, `B13 r2`)

### DOC_CONTROL

- `unrecovered_edit_error`: 3 (`B07 r3`, `B12 r2`, `B13 r2`)
- `compile_final_fail`: 2 (`B07 r3`, `B13 r2`)
- `semantic_boundary_fail`: 1 (`B11 r1`)
- `harness_valid_false_despite_good_diff_or_no_final`: 1 (`B12 r2`)

### SOURCE_ONLY

- `unrecovered_edit_error`: 4 (`B09 r1`, `B09 r3`, `B11 r3`, `B12 r1`)
- `compile_final_fail`: 2 (`B09 r3`, `B12 r1`)
- `no_effect_due_edit_error`: 2 (`B09 r1`, `B11 r1`)
- `semantic_boundary_fail`: 2 (`B11 r2`, `B12 r3`)

## TMF failure details

### B07 r1 — protocol/tool failure, then compile failure

Observed:

- edit failed: `old text match count 0, expected 1`
- compile failed in final state
- agent still produced final answer

Attribution:

- Not a clean TMF semantic failure.
- Harness should classify this as `edit_protocol_fail` plus `compile_fail`, not as boundary reasoning failure.

### B11 r3 — compile failure

Observed:

- `compile=false`, `valid=false`, `trap=false`
- no unrecovered edit error in the summary bucket, but final code failed compile

Attribution:

- Primarily execution/protocol failure.
- Compile failure should block final acceptance.

### B12 r1 — no effective source change after edit failure

Observed:

- edit failed: `old text match count 0, expected 1`
- `subscriber_changed=false`
- compile passed only because the file was effectively unchanged
- agent still produced final answer

Attribution:

- Not semantic evidence against TMF.
- This is a false completion after failed edit.

### B12 r3 — real expression-boundary failure

Diff pattern:

```java
beforeSubscriberMethodInvoke();
method.invoke(target, checkNotNull(event));
```

Expected boundary:

- after `checkNotNull(event)` has executed;
- before `Method.invoke` receives the checked event.

Correct transformation pattern:

```java
Object checkedEvent = checkNotNull(event);
beforeSubscriberMethodInvoke();
method.invoke(target, checkedEvent);
```

Attribution:

- Genuine TMF claim granularity problem.
- Claim described the location in natural language but did not force the necessary Java expression hoist.

### B13 r1 — no effective source change after edit failures

Observed:

- two edit failures: `old text match count 0, expected 1`
- `subscriber_changed=false`
- compile passed because the target file was unchanged

Attribution:

- Protocol failure / false completion.

### B13 r2 — partial edit and semantic failure

Observed:

- helper definition was inserted;
- core replacement after `method.invoke(...)` failed due to edit-anchor mismatch;
- final diff only added a helper, not the normal-return hook placement.

Attribution:

- Mixed failure: unrecovered edit error plus semantic non-completion.
- If counted semantically, it shows the same weakness as B13: the claim does not provide enough executable pattern guidance for normal-return insertion.

Expected transformation patterns:

Statement form:

```java
method.invoke(target, checkNotNull(event));
recordSubscriberMethodNormalReturn();
```

Return-expression form:

```java
Object result = method.invoke(target, checkNotNull(event));
recordSubscriberMethodNormalReturn();
return result;
```

## Why DOC_CONTROL won this set

DOC_CONTROL did not win because it discovered deeper structure. It likely won because:

1. The task is small and the natural-language instructions are already strong.
2. TMF claims are not materially more operational than DOC_CONTROL text.
3. The harness allows noisy edit/compile failures to count against all arms, obscuring the distinction between knowledge failure and execution failure.
4. B12/B13 need transformation recipes, not only boundary descriptions.

## Interpretation by task

- `B08` / `B10`: all arms pass; tasks are too leading/easy to separate arms.
- `B09`: TMF appears strong (`3/3`) and SOURCE_ONLY weak; this supports TMF value for catch-path disambiguation.
- `B11`: TMF improves over SOURCE_ONLY but still has compile/protocol noise.
- `B12` / `B13`: weakest TMF area; expression evaluation / normal-return insertion requires structured recipes.

## Recommended benchmark fixes before drawing stronger conclusions

### 1. Split failure classes in the report

Report separate counts for:

- `semantic_boundary_fail`
- `edit_protocol_fail`
- `compile_fail`
- `no_effect_false_completion`
- `validator_or_finalization_inconsistency`

Do not collapse them into one `pass=false` score when diagnosing TMF knowledge quality.

### 2. Gate final acceptance on tool health

A run should be invalid as an agent/protocol run if:

- any edit operation fails and is not followed by a successful corrective edit/read cycle;
- final compile fails;
- final answer is emitted with no source diff when a source change is required.

### 3. Strengthen TMF claim format for boundary tasks

For each boundary claim, include:

- canonical file + method anchor;
- positive placement examples;
- negative placement examples;
- transformation recipe for statement vs expression forms;
- AST-ish precondition/postcondition where possible.

### 4. Add targeted B12/B13 rerun

Before scaling to more repositories, rerun only:

- `B12`, `B13`
- all three arms
- 5 repeats each
- with protocol failures separated from semantic failures

This will show whether TMF still underperforms DOC_CONTROL once harness noise is removed.

## Bottom line

Current evidence says:

> TMF is useful for some dispatch/catch-path boundary tasks, but the current claim format is not yet stronger than a good task-specific document for expression-level insertion boundaries. The benchmark harness also needs stricter protocol gates before pass-rate differences can be interpreted as pure reasoning differences.
