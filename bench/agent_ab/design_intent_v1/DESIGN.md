# design_intent_v1 — TMF Core Hypothesis Test

**Experiment goal:** Test whether TMF enables cross-session cognitive continuity through (1) precise staleness detection and (2) design-intent transmission.

**Date created:** 2026-08-20  
**Status:** Design phase

## Core hypothesis

TMF's value is **not** in helping agents understand code faster on first read. It's in:

1. **Precise staleness detection:** When an agent retrieves understanding from memory, TMF accurately detects source changes and blocks stale memory before it causes errors
2. **Design-intent transmission:** TMF preserves and transmits the "why" behind code (design tradeoffs, architecture rationale) across sessions and changes, not just implementation facts

## Why previous experiments failed

| Experiment | Problem |
|---|---|
| `cognitive_continuity_v1` | Invalid protocol (fixture/task contradictions) |
| `cognitive_continuity_v2` | Measured reread reduction, not staleness detection or design intent |
| `guava_cognitive_v1` | Tasks asked "what breaks" not "why designed this way"; no cross-session continuity |

None measured the actual hypothesis.

## Valid test structure

### Phase A: Understanding (discarded)
- Agent reads codebase
- Completes understanding task: "Explain the design rationale for X. Why was it designed this way instead of alternative Y?"
- **Answer is discarded** — only derived claims persist
- Claims must include design-intent annotations (not just call edges)

### Phase B: Continuity test (measured)
- **Time separation:** Treat as different session (fresh agent, no transcript)
- **Code mutation:** Source changes (semantic or refactor)
- **New task:** Requires understanding design + evaluating change impact
- **Three arms:**
  - **SOURCE_ONLY:** No memory, must read all source
  - **TMF_STALE:** Has claims but they're stale; TMF must block and force localized reread
  - **TMF_FRESH:** Has claims and they're fresh; can reuse design intent

### Success criteria

**1. Staleness gate (mandatory)**
- TMF_STALE detects staleness: 100%
- TMF_STALE reread bytes < 50% SOURCE_ONLY
- Zero stale trust errors (agent using outdated memory)

**2. Design-intent transmission (core value)**
- Task must ask "why" questions:
  - "Explain the design tradeoff..."
  - "Why was X chosen over Y?"
  - "What architectural constraint does Z enforce?"
- Scoring rubric (held-out, human-audited):
  - **0 points:** Implementation details only ("method M calls N")
  - **1 point:** Architecture mention ("uses branching strategy")
  - **2 points:** Design rationale ("branching enables parallel dispatch without subscriber coupling")
- Success: TMF_FRESH scores ≥1.5 average, SOURCE_ONLY scores <1.0 average

**3. Efficiency (secondary)**
- Token: TMF_FRESH < TMF_STALE < SOURCE_ONLY
- Time: TMF_FRESH should be fastest (not mandatory)

## Proposed tasks

### Subject: Guava EventBus
Well-documented, clear design decisions, ~2000 lines, multiple architectural choices to probe.

### T1: Branching dispatch design
**Phase A question (discarded):**
"Explain why Guava EventBus uses a branching routing strategy where post() immediately fans out to all matching subscribers, rather than a linear sequential dispatch. What are the design tradeoffs?"

**Golden design intent:**
- Branching enables parallel subscriber execution (via different Dispatcher implementations)
- Decouples subscribers (one subscriber's failure doesn't block others in ImmediateDispatcher)
- Performance: avoids sequential bottleneck when subscribers are independent
- Tradeoff: more complex than sequential, requires careful ordering guarantees (PerThreadQueuedDispatcher)

**Phase B mutation:** Change Dispatcher.dispatch to sequential mode (remove branching)

**Phase B question (measured):**
"This codebase just changed from branching to sequential dispatch. Evaluate the impact: what design property was lost? What performance/isolation tradeoff was made?"

**Expected answers:**
- SOURCE_ONLY: Reads all code, describes "what changed" (implementation details)
- TMF_STALE: Detects staleness, rereads only Dispatcher region, describes "what changed"
- TMF_FRESH: Reuses Phase A design intent, immediately states "parallel dispatch capability lost, subscriber isolation now sequential"

### T2: DeadEvent mechanism design
**Phase A question (discarded):**
"Explain why EventBus has a DeadEvent re-post mechanism. Why not just silently drop unsubscribed events? What design principle does DeadEvent enforce?"

**Golden design intent:**
- Observability: allows debugging of missing subscriptions
- Fail-visible principle: absence of subscribers might be a bug, not intended
- Tradeoff: extra allocation and recursive post() overhead for every unsubscribed event

**Phase B mutation:** Remove DeadEvent branch (silent drop)

**Phase B question (measured):**
"The DeadEvent re-post mechanism was just removed. What observability property was lost? Was this a performance optimization or a design principle change?"

### T3: Async boundary design
**Phase A question (discarded):**
"AsyncEventBus uses an Executor for async dispatch. Trace exactly where the async boundary is. Why is it there instead of at the post() entry or at the iterator drain?"

**Golden design intent:**
- Async boundary is in Subscriber.dispatchEvent (executor.execute call)
- Queue drain happens on calling thread (ordering guarantee)
- Design: preserve event ordering while allowing parallel subscriber execution
- Tradeoff: calling thread does O(N) enqueue work, executor threads do O(N) subscriber invocations

**Phase B mutation:** Move async boundary to post() entry (entire dispatch is async)

**Phase B question (measured):**
"The async boundary moved from Subscriber.dispatchEvent to post() entry. What ordering guarantee was affected? Explain the design tradeoff."

## Fixture preparation

### Phase A fixture
- Clean Guava EventBus at commit X
- Agent reads, understands, generates design-intent claims
- Claims stored in `.tmf/`

### Phase B fixtures
- **SOURCE_ONLY:** Clean fixture, no `.tmf/`
- **TMF_STALE:** Mutated fixture + stale `.tmf/` from Phase A
- **TMF_FRESH:** Original fixture + fresh `.tmf/` from Phase A

## Design-intent claim format

Current TMF claims don't capture design intent. Need to add:

```python
{
  "claim_id": "...",
  "kind": "design_rationale",
  "anchor": {"file": "EventBus.java", "line": 123},
  "summary": "Branching dispatch enables parallel subscribers",
  "rationale": "Design chose branching over sequential to allow parallel execution without subscriber coupling. Tradeoff: complexity for performance/isolation.",
  "alternatives_considered": ["sequential", "queue-based"],
  "constraints": ["ordering", "isolation"]
}
```

**Open question:** How should these claims be derived?
- Option A: Agent writes them explicitly in Phase A (tool call)
- Option B: Infer from Phase A answer + anchor to source
- Option C: Hybrid (agent tags key decisions, TMF anchors them)

## Attribution and validity

- **Machine-audited:** Staleness detection, reread bytes, stale trust errors
- **Human-audited:** Design-intent scoring (0/1/2 rubric)
- **Invalid if:** Task/fixture contradiction, fixture contamination, TMF modification during run, runtime failures

## Next steps

1. **Decide design-intent claim derivation strategy** (A/B/C above)
2. **Implement claim format** (extend TMF schema)
3. **Build Phase A understanding task harness** (captures design rationale)
4. **Build Phase B mutation + continuity test harness**
5. **Run smoke (N=2 tasks)**
6. **If smoke passes, run full (N=3 tasks × 3 arms = 9 runs)**

## Open questions

1. How to ensure Phase A answers actually contain design intent vs just implementation description?
2. Should Phase A be multi-turn (agent explores, asks clarifying questions) or single-turn?
3. How to prevent Phase A answer contamination into Phase B (different model? different session key?)
4. What's the minimum viable design-intent claim that's still useful in Phase B?

## Risk mitigation

- **Risk:** Agent ignores design-intent claims even when fresh
- **Mitigation:** Make Phase B questions explicitly require design reasoning ("What design property was lost?")

- **Risk:** SOURCE_ONLY accidentally scores high on design intent (gets lucky)
- **Mitigation:** Multiple tasks, average scoring, design-intent rubric requires specific keywords

- **Risk:** TMF_STALE fails to detect staleness
- **Mitigation:** Pre-flight check, verify mutation actually changed anchored blobs

## Timeline estimate

- Design-intent claim format: 2-4 hours
- Phase A harness: 4-6 hours
- Phase B harness + mutation logic: 4-6 hours
- Fixture preparation: 2-3 hours
- Smoke run (N=2): 1-2 hours
- Analysis + decision: 2-3 hours
- **Total:** ~20-30 hours

If smoke fails, abort and document failure mode.
