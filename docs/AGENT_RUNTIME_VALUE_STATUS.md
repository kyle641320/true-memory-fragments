# Authoritative Agent runtime value status

**Single authoritative experiment ruling — updated 2026-08-28.** Read this page before interpreting any older A/B report. Older reports preserve their original observations; they are not interchangeable because they test different delivery modes. The 2026-08-28 `GUAVA_M10_PREREAD_R50` result supersedes the older blanket "Agent-outcome-unproven" wording only for one narrow value class: stale-context safety.

## Current ruling

| Evidence | Result | What it proves |
|---|---|---|
| Tool-mode Java real v1/v2 | no observed advantage when the Agent must actively retrieve TMF | Negative only for proactive/tool retrieval; **not** evidence that forced middleware is ineffective. |
| Retrieval E2E v1 | smoke stopped on retrieval relevance/value gates | Negative within that lexical retrieval protocol; not a universal memory ruling. |
| `middleware_hardening_v1` | mechanism hard gates **5/5 pass** | Exact-target/freshness injection, stale blocking and localized reread mechanics work on those fixtures. It does **not** prove Agent adoption or task value. |
| `agent_middleware_value_v1` cold-start Agent smoke | **2/2 valid pairs**, SOURCE 2/2 success, TMF 2/2 success, TMF adoption **0/2** | A new stateless Agent did not adopt injected notes on its first encounter. **Scope limit:** it never performed the first visit, so this cannot negate repeat/revisit value for one cognitive subject. Result is preserved and not regraded. |
| `cognitive_continuity_v1` | **INVALID_PROTOCOL**; 0/2 has no evidentiary force | Fixture/task/golden contradiction and non-TMF model-authored memory contamination. Preserve, never regrade or attribute to product. |
| `cognitive_continuity_v2` resumed smoke | **2/2 valid pairs**; SOURCE 2/2 success, TMF 2/2 success, qualified adoption **0/2**; STOP | Runtime recovered; the old blocked audit is retained but superseded. B01 had structural claim coverage yet repeated 1 read/91 bytes; B03 had no task coverage and repeated 2 reads/102 bytes. The frozen adoption gate prohibits a full run. |
| `guava_cognitive_v1` | **INVALID_PROTOCOL**; task design does not test core hypothesis | PROTOCOL.md promised call-chain tasks; tasks.json executed impact analysis and compile repair. Neither tests call-chain continuity or tunnel-vision bug prevention. Preserve, never regrade or attribute to product. |
| `GUAVA_M10_PREREAD_R50` | **POSITIVE, scoped stale-context safety evidence**: SOURCE_ONLY 40/50 raw, TMF_STALE_GATED 42/50 raw, PREREAD_STALE_SOURCE 2/50 raw, STALE_DOC_CONTROL 0/50 raw; stale arms wrong-inline 43/50 and 45/50, TMF wrong-inline 0/50 | Proves stale claims/docs can severely pollute boundary selection and TMF stale-gating can prevent that pollution on this real-Guava fixture. Does not prove broad productivity/speed/token savings; SOURCE_ONLY and TMF were close, and raw fails include protocol/no-final noise. |

### Product decision

**Do not recommend TMF_MIDDLEWARE for production on an Agent-value, speed, token, or reread-reduction claim.** It may be used only as an experimental safety/navigation mechanism where users explicitly accept unproven outcome value and count injection cost. Continue to recommend source-authoritative fallback and the hard freshness/stale gate as a qualified mechanism, not as a productivity win.

Evidence level is **mechanism-qualified / stale-context-safety-positive / broad Agent-outcome-limited**. Cognitive v1 invalid. Cognitive v2 stopped at smoke (0/2 adoption). Cognitive v3 (guava_cognitive_v1) invalid. `GUAVA_M10_PREREAD_R50` is valid scoped positive evidence that stale-gating prevents stale boundary pollution, but stable adoption, Python/Java breadth beyond this fixture, productivity, and net economic value remain unproved.

## Core hypothesis (corrected 2026-08-20)

TMF is designed to solve the **"tunnel vision bug" problem**:

**The problem:**
- Agent understands complete call chain `A → B → C → D` at time t₀
- Code changes at t₁ (e.g., `C` implementation modified)
- Agent receives task "modify A" at t₂
- If agent only looks at `A`, it may introduce bugs by not seeing downstream impact on changed `C`

**TMF's solution:**
1. **Precise staleness detection:** When agent retrieves the `A → B → C → D` chain from memory, TMF detects that `C` has changed and blocks stale memory
2. **Localized reread:** Forces agent to reread only `C` and its direct neighbors, not the entire codebase
3. **Complete chain understanding:** Ensures agent sees the full call chain when making changes

**What TMF is NOT designed for:**
- ❌ Helping agents understand code faster on first read
- ❌ Reducing source rereads through cached "facts"
- ❌ Providing "remembered truths" for direct reuse

**Valid test structure:**
- Phase A: Agent traces complete call chain at t₀
- Phase B: Code changes one node in chain at t₁, agent receives modification task at t₂
- Measurement: Does TMF (1) detect staleness, (2) force localized reread, (3) prevent tunnel-vision bugs?

`GUAVA_M10_PREREAD_R50` validly tests one subclaim: when old memory/documentation points at a stale boundary, TMF stale-gating prevents that stale boundary from being injected and avoids wrong-site edits. It does not fully test the broader Phase A→B cross-session continuity/productivity hypothesis.

## Why existing experiments don't test the core hypothesis

| Experiment | What it tested | Why it's invalid |
|---|---|---|
| `cognitive_continuity_v1` | Unknown — fixture/task/golden contradictions | Protocol was internally inconsistent |
| `cognitive_continuity_v2` | Whether fresh claims reduce rereads on second visit | Measured reread reduction, not staleness detection or call-chain continuity |
| `guava_cognitive_v1` | Whether agents answer "which paths become unreachable" and "fix compilation" tasks | Tasks asked "what breaks" not "trace call chain"; no cross-session continuity or bug prevention measurement |

## Cognitive continuity v2 resumed outcome

The unchanged frozen smoke completed after the external broker timeout hierarchy was repaired. Both arms were valid and successful on B01 and B03, but neither TMF arm qualified as adoption. B01's TMF context included a structural call-edge claim and still repeated the same phase-B source read (1 read/91 bytes). B03 had no task coverage and repeated 2 reads/102 bytes. Preflight claim coverage of 2/10 tasks is structural coverage only; it does not establish that a claim answers task-specific implementation semantics. Current derived claim content cannot generally replace a second source read.

TMF also cost more in each observed pair: B01 6,894 vs 1,376 SOURCE tokens and B03 7,420 vs 2,500. This is not a failure of the qualified middleware freshness/stale-blocking mechanism; it is failure to demonstrate claim-content sufficiency, Agent adoption, reread reduction, or value in this smoke.

## Guava cognitive v1 outcome

Experiment attempted to test "call-chain continuity" but executed tasks that did not measure those properties:

**PROTOCOL.md promise:**
- Test call-chain understanding across sessions
- Measure staleness detection and localized reread

**tasks.json reality:**
- B01: "Which call paths stop being reachable?" (pure impact analysis)
- B02: "Fix compilation errors" (pure mechanical repair)

**Observed outcome (6/9 arms completed):**
- All three B01 answers provided identical implementation-detail analysis
- Zero call-chain differentiation between arms
- No staleness detection measurement (all fixtures were static)
- No cross-session continuity (no Phase A→B time separation)

**Invalidation reason:** Task design did not test call-chain continuity or tunnel-vision bug prevention.

## Which experiment answers which question

| Mode | Question answered | Does not answer |
|---|---|---|
| Tool-mode | Will an Agent proactively call TMF retrieval? | Forced delivery or revisit continuity |
| Cold-start injection | Will a stranger Agent use supplied memory on first encounter? | Value on second visit by same cognitive subject |
| Mechanism | Are freshness, stale blocking, and localized reread mechanically sound? | Agent adoption/productivity |
| Cognitive continuity v2 | Can persistent cognitive layer carry source-bound knowledge across phases? | After smoke stop, broad/semantic/product value |
| Cognitive v3 (guava) | **INVALID** — tasks did not measure call-chain continuity | Staleness detection, localized reread, bug prevention |

## Cold-start Agent outcome details

| Task | Mode | SOURCE | TMF | Audited adoption | Reads S/T |
|---|---|---:|---:|---:|---:|
| A01 Python understanding | fresh revisit | pass | pass | no | 1/1 |
| A03 Python local edit + test | fresh revisit | pass | pass | no | 1/1 |

Aggregate: source bytes 173/173, tool calls 8/8, estimated prompt tokens 1406/1874, completion 168/181, TMF injection 0/236, wall seconds 25.68/33.98 (SOURCE/TMF). No errors occurred. Adoption is machine-audited.

## What a valid experiment needs

To test TMF's core hypothesis:

1. **Phase A → Phase B structure with time separation:**
   - Phase A: Agent traces complete call chain
   - Phase B: Code changes one node, agent receives modification task requiring chain understanding

2. **Measure staleness detection:**
   - TMF_STALE: 100% staleness detection, reread bytes < 50% of SOURCE_ONLY
   - Zero stale trust errors

3. **Measure call-chain completeness:**
   - Task requires understanding full chain to avoid bugs
   - Success: TMF arms correctly identify impact scope

4. **Measure bug prevention:**
   - Success: TMF warns about changes, agent checks before modifying
   - Failure: Agent modifies without seeing change, introduces bug

**No experiment has met these criteria yet.**

## Summary

TMF's middleware mechanics work (freshness detection, stale blocking, localized reread). `GUAVA_M10_PREREAD_R50` adds scoped Agent-outcome evidence: stale context caused severe wrong-boundary edits in preread/doc controls, while TMF stale-gating avoided that stale pollution and returned behavior near SOURCE_ONLY. The broader product hypothesis — durable cross-session call-chain continuity with net productivity/economic value — remains only partially tested and needs replication.

**Next step:** Design and execute valid experiment (`design_intent_v1`) that tests call-chain continuity and bug prevention.
