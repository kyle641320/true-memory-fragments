# TMF Core-Value Validation Redesign: r10-r13

Date: 2026-08-23

## Design principle

The experiment must prove a causal TMF contribution, not merely that an agent can read current source. Each run therefore needs:

1. A stale assumption seeded before the task.
2. A real source change after the stale artifact/first pass, or a fresh source state that invalidates the stale artifact.
3. A control arm that has the stale artifact but no TMF freshness/locator signal.
4. A treatment arm that has the same stale artifact plus TMF evidence pointing to the stale claim/edge/file.
5. A hidden scorer that checks both final correctness and whether the agent identified/re-read the stale dependency.
6. Frozen prompts and preflighted repos before agents run.

Success is not “treatment passes once.” Success is differential lift under controlled information asymmetry.

---

## r10 — Post-read source drift / freshness detection

### Core hypothesis

TMF helps when source changes after an agent has already formed a stale assumption from earlier source reading.

### Setup

- Repo: Guava clone per arm.
- Phase A for both arms: agent reads target file and writes a short assumption note, e.g. about `CompactHashing.newCapacity(mask)` using threshold `mask < 32`.
- After Phase A completes, parent mutates `CompactHashing.newCapacity` to `mask < 64` in both repos.
- Phase B task asks agent to implement a helper in `CompactHashMap.java` that depends on the resize policy.

### Control arm

Receives:
- Its Phase A assumption note.
- The Phase B task.
- No indication that dependent source changed.

### Treatment arm

Receives:
- Same Phase A assumption note.
- Same Phase B task.
- TMF freshness evidence: the prior claim/edge for `CompactHashing.newCapacity` is stale, with locator to `CompactHashing.java:newCapacity`.

### Prompt constraint

Do not name the hidden expected value. Do not explicitly say “the threshold changed to 64.” Only the TMF arm may receive a freshness/locator signal.

### Hidden scorer

Checks:
- Final helper returns `256` for `currentMask=63`.
- Implementation uses/re-reads current `CompactHashing.newCapacity` or equivalent current source.
- Report mentions stale assumption invalidation in treatment.
- Control failure mode expected: stale `128`, hard-coded stale threshold, or no re-read.

### Validates TMF core value if

Treatment reliably invalidates stale Phase A knowledge and re-reads the right dependency while control does not.

---

## r11 — Cross-file indirect dependency locator

### Core hypothesis

TMF helps locate non-obvious cross-file dependencies when the target file alone is insufficient.

### Setup

- Target task edits `CompactHashMap.java` only.
- Correct answer depends on a chain not obvious from the prompt, e.g.:
  `CompactHashMap.init -> allocArrays -> CompactHashing.tableSize -> MIN_HASH_TABLE_SIZE`.
- Seed stale notes saying min table size is `4`.
- Current source has min table size `8` or another changed value.

### Control arm

Receives:
- Target file path.
- Stale design note.
- Strong read budget: target file plus at most one self-chosen extra file, or a time budget that makes broad search costly.
- No TMF locator.

### Treatment arm

Receives:
- Same target path, stale note, and budget.
- TMF locator evidence that the stale claim is tied to `CompactHashing.MIN_HASH_TABLE_SIZE` and relevant callers/readers include `tableSize` and `CompactHashMap.allocArrays`.

### Hidden scorer

Checks:
- Correct current min table size behavior.
- Whether agent reads the field declaration / caller chain.
- Whether final patch preserves existing behavior.
- Number and relevance of files read.

### Validates TMF core value if

Treatment reaches the exact dependency chain faster/more reliably under the same budget, while control either stays in target file or reads the wrong adjacent file.

---

## r12 — Stale reverse-call / caller impact analysis

### Core hypothesis

TMF helps when a local change requires identifying affected callers, not just reading the changed declaration.

### Setup

- Mutate a helper declaration or semantics in one Guava utility class.
- Task asks agent to update/add behavior in a different caller-facing class without directly naming the helper.
- Stale artifact says only one caller matters.
- Current source has two or more relevant callers, one newly added or semantically changed.

Example shape:
- Source declaration: `CompactHashing.maskCombine` or a compact-hash helper.
- Affected callers: multiple map/set implementations.
- Task: expose/testing helper or preserve behavior across both map and set.

### Control arm

Receives:
- Stale caller list.
- Task phrased from product behavior.
- Normal source access but no explicit caller map.

### Treatment arm

Receives:
- Same stale caller list.
- TMF reverse-caller evidence marking the stale caller list incomplete/stale and listing current callers.

### Hidden scorer

Checks:
- Agent updates/considers all current relevant callers.
- No regression in the caller omitted by stale notes.
- Report identifies stale caller list.

### Validates TMF core value if

Treatment avoids a missed-caller bug that control plausibly makes from stale caller notes.

---

## r13 — Reads/writes/state invariant freshness

### Core hypothesis

TMF helps when correctness depends on state read/write invariants scattered across methods, not on a single obvious constant.

### Setup

- Choose a Guava class with internal metadata/state invariants, e.g. `CompactHashMap.metadata`, `size`, `entries`, `table`.
- Seed stale invariant note: e.g. “resizing updates only table metadata” or “mod count increments only on insert.”
- Current source has changed write behavior or an additional method that writes/reads the invariant.
- Task asks agent to add a testing helper or small behavior preserving iterator/concurrent-modification semantics.

### Control arm

Receives:
- Stale invariant note.
- Task.
- No TMF reads/writes graph.

### Treatment arm

Receives:
- Same stale note and task.
- TMF readers/writers evidence for the affected field(s), marking stale writer/reader claims and pointing to current write sites.

### Hidden scorer

Checks:
- Correct preservation of state invariant.
- No missed `incrementModCount`, metadata update, or field write.
- Report cites current writer/reader set.

### Validates TMF core value if

Treatment identifies the changed state invariant and avoids a subtle mutation/iterator bug that control misses.

---

## Required protocol guardrails for all four

- Pre-register task, mutation, stale artifact, treatment TMF evidence, hidden scorer, and pass/fail rubric before agent launch.
- Freeze prompts and hashes.
- Separate Phase A stale-assumption capture from Phase B implementation where freshness is being tested.
- Do not give control broad unrestricted source search if the claimed TMF value is locator efficiency under stale context.
- Do not leak hidden expected values in prompts.
- Score final answer and causal trace separately:
  - answer correctness
  - stale dependency identified
  - correct file/claim re-read
  - unnecessary broad search avoided
- Declare neutral if both arms succeed by ordinary source reading.
- Declare invalid if treatment does not actually receive usable TMF evidence or control accidentally receives equivalent locator information.

## Recommendation

Run r10 first. It is the cleanest direct test of TMF freshness: both arms first form the same stale assumption, source then changes, and only treatment receives the stale-claim locator. This directly targets the core value that r9 failed to test.
