# r14 — Final TMF Pain-Reflex Experiment

Date: 2026-08-23

## Goal

If TMF has real value, it should not merely help an agent answer correctly after reading source. It should trigger a **pain-reflex-like stop** when the agent is about to act on stale code knowledge.

This final experiment tests exactly that:
- the agent forms an initial local belief;
- the source changes afterward;
- the agent then attempts an action that would rely on the stale belief;
- only the TMF arm gets an automatic freshness/reflex signal before the action completes.

If this still shows no measurable advantage, we can reasonably conclude TMF is not adding enough value for this workflow.

---

## Core hypothesis

TMF is valuable only if it can:
1. detect that a specific local belief is stale,
2. intercept the next dependent action,
3. force a narrow re-read of the exact stale dependency,
4. then let the agent continue with corrected context.

This is the actual “pain reflex”.

---

## Experimental shape

### Shared setup

Use the Guava repo again, but do **not** make the target trivial.

Choose a task where:
- one local helper is the obvious first answer,
- a nearby decoy helper exists,
- the correct implementation depends on a current source detail that can change after the initial read,
- a stale assumption would cause a plausible wrong edit.

Good target shapes:
- resize policy helper
- caller impact helper
- writer/read invariant helper

### Two phases

#### Phase A — belief capture
Both arms:
- read only enough source to form a local belief,
- write a short note: what they currently think the policy/relationship is,
- do not edit anything yet.

#### Phase B — action with possible reflex
After Phase A:
- the parent mutates the source in a small but meaningful way,
- the agent is asked to make the dependent edit.

The key difference:
- **control** receives only the stale Phase A note,
- **treatment** receives the stale note **plus a TMF reflex signal** that the specific dependency it is about to use is stale.

The TMF signal must be narrow and local:
- not a full explanation,
- not the final answer,
- only enough to trigger a re-read of the exact stale dependency.

---

## What makes this different from the earlier runs

The earlier runs mostly tested: “can the agent still solve the task from current source?”

This final run tests: “can TMF stop the agent at the moment stale knowledge would be used?”

That means the evaluation is not just final correctness. It must also score:
- whether the agent initially relied on stale context,
- whether the reflex signal caused a local re-read,
- whether the first dangerous action was avoided or corrected,
- whether the final patch reflects the current source rather than the stale belief.

---

## Recommended concrete instance

### Candidate target
Use a helper whose behavior depends on a current source rule that can drift easily, such as a resize or caller-impact rule.

### Phase A belief example
The agent believes:
- “policy X is still controlled by helper Y”
- “the threshold is still N”
- “only caller set A matters”

### Source drift
Mutate the underlying helper or rule after Phase A.

### Phase B task
Ask the agent to implement a UI/helper/reporting method that depends on that rule.

### TMF reflex signal
The treatment arm receives:
- stale claim id / function boundary,
- a short freshness warning,
- a pointer to the exact dependency file to re-read.

The control arm receives nothing extra.

---

## Success criteria

TMF shows value only if treatment beats control on at least one of these reflex dimensions:
- it re-reads the stale dependency earlier,
- it avoids making an edit based on the stale belief,
- it explicitly reports the assumption was invalidated,
- it reaches the correct patch with less blind search.

Final correctness alone is not enough if both arms can reach it equally.

---

## Failure criteria

This experiment fails as evidence for TMF if:
- both arms still solve the task the same way,
- the treatment signal acts only as a hint, not a reflex trigger,
- there is no observable difference in stale-belief correction,
- the agent never actually has to stop and re-read before acting.

If this happens, TMF is not functioning as a pain reflex in practice.

---

## Hard rule for the last experiment

Do not keep iterating after r14.

If r14 still does not show a reflex advantage, stop and treat TMF as not proven useful for this workflow.
