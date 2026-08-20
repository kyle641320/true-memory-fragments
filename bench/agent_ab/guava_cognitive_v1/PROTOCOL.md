# guava_cognitive_v1 — frozen preregistration

Pre-registered on 2026-08-19. This is a real stateless coding-Agent paired comparison testing **cognitive continuity and design-intent value** on Guava EventBus. `SOURCE_ONLY`, `TMF_STALE`, and `TMF_FRESH` use the same `gpt-5.6-sol`, raw-inference broker, prompts, task order, tools, and budgets. The runner owns a constrained read/search/edit/test loop. The broker has no tools or repository access. Each arm starts from a fresh isolated fixture copy.

## Protocol structure

Each task has two phases:

**Phase A: Familiarization (discarded)**
- Agent reads Guava EventBus module (~2000 lines including routing, subscription, dispatch)
- Derives TMF claims: call edges, routing shape (branching/linear), async boundaries, design-intent annotations
- Completes understanding task: "Explain EventBus event dispatch mechanism and design tradeoffs"
- Phase A transcript and answer are **discarded**; only derived claims persist

**Phase B: Cognitive continuity test (measured)**
- Source may be mutated (semantic changes or refactoring)
- Agent receives a new task requiring EventBus understanding or modification
- **SOURCE_ONLY:** no memory, must reread all source
- **TMF_STALE:** has claims but they're stale; TMF freshness gate must block and force localized reread
- **TMF_FRESH:** has claims and they're fresh; can reuse design intent without full reread

## Arms

| Arm | Phase A | Phase B | Expected behavior |
|---|---|---|---|
| **SOURCE_ONLY** | No memory, full read | No memory, full read | Reads all implementation, answers "what it does" |
| **TMF_STALE** | Generates claims | Claims stale, blocks+reread | Detects staleness, rereads only changed regions |
| **TMF_FRESH** | Generates claims | Claims fresh, reuses | Reuses design intent, minimal/no source reads |

## Success criteria

**1. Freshness gate (mandatory)**
- TMF_STALE detects staleness: 100%
- TMF_STALE reread bytes < 50% SOURCE_ONLY
- Zero stale trust errors

**2. Design-intent transmission (core value)**

Held-out rubric evaluates:
- **Architecture shape:** mentions `branching`, `N downstream`, routing strategy
- **Design tradeoffs:** explains "why designed this way" (e.g., performance vs flexibility)
- **Boundary identification:** correctly identifies async boundaries, module responsibilities
- **Implementation-detail vs design-intent ratio:** TMF should favor design, SOURCE favors implementation

**Scoring:**
- **0 points:** only implementation details ("this method does X")
- **1 point:** mentions architecture ("uses branching")
- **2 points:** explains design tradeoffs ("branching enables parallel subscriber dispatch")

**3. Efficiency metrics (secondary)**
- Token consumption: TMF_FRESH < TMF_STALE < SOURCE_ONLY
- Read bytes: TMF_FRESH << SOURCE_ONLY
- Wall time: TMF_FRESH should be fastest (not mandatory)

## Tasks

**B01: EventBus design understanding**
- **Prompt:** "Explain why Guava EventBus uses a branching routing strategy rather than linear sequential dispatch. What are the design tradeoffs?"
- **Golden keywords:** `subscriber matching`, `parallel dispatch`, `performance`, `decoupling`, `branching shape`
- **Mutation:** Change subscriber matching logic (semantic)

**B02: Add event filter**
- **Prompt:** "Add an event filter to EventBus. Requirements: 1) preserve existing branching architecture, 2) don't break subscriber isolation, 3) support filter chaining"
- **Golden keywords:** `preserves routing shape`, `filter chain`, `before dispatch`, `no subscriber coupling`
- **Mutation:** Extract Dispatcher interface (refactor)

**B03: Debug missing subscriber event**
- **Prompt:** "A subscriber isn't receiving events. Trace the complete call chain from post() to subscriber, and identify possible breakpoints"
- **Golden keywords:** `EventBus.post`, `Dispatcher.dispatch`, `Subscriber.invokeSubscriberMethod`, `routing decision`, `async boundary`
- **Mutation:** Modify Dispatcher routing logic (semantic)

## Attribution and validity

Tasks use structured answer+citations (understanding) or tests+diff assertions (modifications). Machine-audited adoption requires correct final/patch dependency on an injected claim anchor without rereading that source region; self-report never counts.

Attribution classes: `memory-caused`, `stale-memory-caused`, `post-reread-agent-failure`, `baseline-agent-failure`, `output-contract`, `tool/runtime`; mechanism errors reported separately. Infrastructure/schema failures are invalid and never used to tune prompt, golden, scorer, middleware, retrieval, packing, parser, or freshness.

**Design-intent score** is human-audited from held-out rubric. One symmetric schema repair permitted and charged.

## Run protocol

Smoke runs B01/B03 (2 tasks × 3 arms = 6 runs). Full run proceeds only if:
1. All smoke pairs valid
2. TMF_STALE demonstrates freshness blocking in at least 1/2 tasks
3. TMF_FRESH demonstrates adoption (reuses claims without full reread) in at least 1/2 tasks
4. No success regression vs SOURCE_ONLY

Stop gates and value gates frozen separately. Small N is descriptive only: report every row and do not claim statistical significance.

## TMF integration

Uses unmodified middleware at current HEAD (must not modify TMF engine code). Immediately before router-selected read, injects fresh allowlisted anchor or blocks final/edit on stale until affected source region is reread. Unknown/unrelated controls must not false-inject.

Phase A claims derived from real Guava EventBus source at fixed commit. Phase B mutations are controlled semantic/refactor changes preserving core EventBus behavior for TMF_FRESH, or breaking it for TMF_STALE.
