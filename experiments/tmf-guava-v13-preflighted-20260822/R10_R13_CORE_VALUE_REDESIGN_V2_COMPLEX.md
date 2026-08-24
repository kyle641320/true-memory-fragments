# TMF Core-Value Validation Redesign v2 — More Complex r10-r13

Date: 2026-08-23

## Why v2

The first redesign was still too easy because the target helper could be solved by direct reading of the obvious callee. v2 tightens the causal test:

- do not name the exact answer path in the prompt;
- introduce competing stale candidates;
- cap read budget so broad search is costly;
- make the treatment arm’s TMF evidence point to the stale dependency without fully revealing the answer;
- score causal trace separately from final correctness.

The goal is to test whether TMF actually helps an agent recover from stale reasoning under ambiguity, not whether the agent can read the current file eventually.

---

## Common protocol for r10-r13

### Pre-registration
Before any run, freeze:
- task prompt
- stale artifact
- mutation plan
- treatment TMF evidence
- hidden scorer
- pass/fail rubric
- file read budget

### Allowed evidence types
Use TMF evidence only as one of:
- `readers`
- `writers`
- `callers`
- `subtypes`
- `retrieve`
- `context`

Do not expose the final line of code or the exact hidden expected value in the treatment prompt.

### Scoring dimensions
For every arm, score separately:
1. final code correctness
2. stale dependency identified
3. correct source file re-read
4. unnecessary search avoided
5. report explicitly says whether Phase A assumption was reused or invalidated

A run is only a TMF win if treatment beats control on at least 2 of 5 dimensions while still passing correctness.

---

## r10-v2 — Post-read drift with competing stale hypotheses

### Hypothesis
TMF helps when the agent has two plausible stale assumptions and only one of them is still true after source drift.

### Setup

Phase A:
- Both arms read only enough to form an assumption about resize policy.
- Prompt asks them to choose between two candidate explanations:
  - `candidate A`: resize helper follows `CompactHashing.newCapacity(mask)`
  - `candidate B`: resize helper depends on a local `CompactHashMap` table-sizing formula
- They must write which candidate they currently believe and why.

Phase B drift:
- After Phase A, parent mutates `CompactHashing.newCapacity` in both repos.
- Additionally, one nearby comment or helper signature is changed so the old assumption is no longer obviously safe.

Control:
- Gets only its own Phase A note and the task.
- No explicit freshness signal.

Treatment:
- Gets the same note plus TMF evidence showing the stale claim around `CompactHashing.newCapacity` and a re-read hint to the exact file/claim boundary.

Task:
- Add the UI helper in `CompactHashMap`.
- The prompt must not mention the callee name.
- The only obvious task requirement is “reflect current source-defined resize behavior.”

Hidden scorer:
- `currentMask=63` must yield `256`.
- If agent hard-codes candidate B or a stale threshold, it fails.
- Treatment should explicitly mention that candidate A became stale and was revalidated from source.

Why this is harder:
- Both arms begin with two plausible hypotheses.
- The treatment must invalidate one hypothesis instead of simply being told the answer location.

---

## r11-v2 — Indirect cross-file dependency with decoy files

### Hypothesis
TMF helps when the target file depends on one of several adjacent utility files and only one is actually relevant.

### Setup

Task target:
- Modify a helper in `CompactHashMap` that depends on a resize policy.

Budget:
- control may read at most 2 files beyond the prompt file
- treatment may read at most 2 files beyond the prompt file, but one TMF evidence bundle is available

Decoys:
- seed stale notes mentioning both `CompactHashing.tableSize` and `CompactHashing.newCapacity`
- only one of them is relevant to the task
- the other is a tempting but wrong adjacency

Control:
- must choose where to spend its 2-file budget
- no locator evidence

Treatment:
- receives TMF context that identifies which claim is stale and which file/edge should be re-read first

Hidden scorer:
- did the agent inspect the true dependency chain first?
- did it waste budget on the decoy?
- did it preserve behavior?

Why this is harder:
- It is not enough to know “read CompactHashing”; the agent must know which piece of CompactHashing matters.

---

## r12-v2 — Caller impact under partial stale graph

### Hypothesis
TMF helps when stale caller data is incomplete and the useful caller set is larger than the stale note claims.

### Setup

Choose a helper or constant with multiple current callers.

Phase A:
- both arms read a stale caller summary that intentionally omits one current caller
- they must write their expected impact set

Phase B:
- a small source change makes one omitted caller relevant to correctness
- task asks for a helper/test update that must account for all current callers

Control:
- receives stale caller summary only

Treatment:
- receives TMF caller evidence indicating the omitted caller is current and relevant

Hidden scorer:
- code/tests cover all affected callers
- report names the omitted caller
- no missed regression in the omitted caller path

Why this is harder:
- stale caller knowledge is now actively misleading, not merely incomplete.

---

## r13-v2 — State invariant and read/write freshness with two-phase mutation

### Hypothesis
TMF helps when correctness depends on a state invariant that is preserved across a sequence of writes, not a single constant.

### Setup

Pick a class with internal state and a derived field/invariant.

Phase A:
- both arms read a stale invariant statement
- they must predict which method writes the state and which method reads the derived value

Phase B:
- parent changes one writer path and one read path in a subtle way
- task asks for a small helper or test that must remain consistent with the current invariant

Control:
- receives only the stale invariant note

Treatment:
- receives TMF readers/writers evidence showing the invariant’s actual current writer set

Hidden scorer:
- final patch preserves invariant across both writes
- report identifies the actual writer path
- code does not rely on the stale invariant statement

Why this is harder:
- it tests not just one stale claim, but a read/write relationship across methods.

---

## Recommended execution order

1. r10-v2 — best direct freshness test
2. r11-v2 — best file-selection test
3. r12-v2 — best caller-scope test
4. r13-v2 — best invariant/trace test

If a run still produces no differential lift, the result is informative: TMF may be helping only as a search hint, not as a genuine causal advantage under tight budgets.

---

## Acceptance threshold for this redesign

A run is only worth keeping if all of the following are true:
- control and treatment are both able to solve the task in principle;
- treatment gets a strictly better stale-dependency trace than control;
- control’s success is not simply because the task remained trivial;
- hidden scoring can distinguish the two arms even when final code passes for both.

If these conditions are not satisfied, the prompt is still too easy.
