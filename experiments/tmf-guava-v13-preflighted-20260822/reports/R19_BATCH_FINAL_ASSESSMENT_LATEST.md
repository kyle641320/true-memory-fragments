# r19 batch final assessment

## Verdict

The four-item batch validates the runner-gated TMF mechanism, but still does not fully prove broad TMF core value.

## Item status

1. task1 / r18b — PASS
   - actual-model corrected intent
   - stale-boundary gate, reread, hidden scorer, git diff check, Guava compile all passed

2. task2 / MAX_HASH_BUCKET_LENGTH — PASS
   - actual-model intent
   - first stale-boundary attempt blocked
   - reread + fresh delegating helper applied
   - hidden scorer, git diff check, Guava compile all passed

3. task3 / MIN_HASH_TABLE_SIZE — PASS after validator fix
   - original failure was scorer/helper-name mismatch, not model intent semantics
   - fixed validation inserted `minHashTableSizeForSmallTables()` and passed hidden scorer + compile

4. task4 / CompactHashMap constructor use-site — PASS after task redefinition and insertion fix
   - original task definition incorrectly treated DEFAULT_SIZE as owned by CompactHashMap.java
   - corrected to use-site `CompactHashMap() -> init(CompactHashing.DEFAULT_SIZE)`
   - original compile failure came from inserting helper inside constructor body
   - fixed insertion after constructor block passed hidden scorer + compile

## What this proves

- Real model-produced intent JSON can be kept separate from source edits.
- A runner can enforce apply/block rather than relying on prompt-only reminders.
- Stale-boundary mismatches can trigger block/reread before apply.
- Fresh delegating patches can preserve current source boundaries and pass compile.
- The protocol replicated across multiple Guava compact-collection boundaries.

## What this does not yet prove

- It does not fully prove broad TMF product/core value in arbitrary real coding tasks.
- The sample is still small and helper/constant-heavy.
- Several failures were harness/design issues, showing the evaluation runner is still immature.
- A stronger proof needs bug-prevention tasks where control would plausibly introduce a real behavioral bug and treatment avoids it because of TMF.

## Bottom line

Mechanism: validated.
Core value: strongly indicated, but not finally proven.
