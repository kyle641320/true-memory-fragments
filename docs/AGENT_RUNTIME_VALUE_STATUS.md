# Authoritative Agent runtime value status

**Single authoritative experiment ruling — 2026-08-13, frozen mechanism base `45ab3e4`.** Read this page before interpreting any older A/B report. Older reports preserve their original observations; they are not interchangeable because they test different delivery modes.

## Current ruling

| Evidence | Result | What it proves |
|---|---|---|
| Tool-mode Java real v1/v2 | no observed advantage when the Agent must actively retrieve TMF | Negative only for proactive/tool retrieval; **not** evidence that forced middleware is ineffective. |
| Retrieval E2E v1 | smoke stopped on retrieval relevance/value gates | Negative within that lexical retrieval protocol; not a universal memory ruling. |
| `middleware_hardening_v1` | mechanism hard gates **5/5 pass** | Exact-target/freshness injection, stale blocking and localized reread mechanics work on those fixtures. It does **not** prove Agent adoption or task value. |
| `agent_middleware_value_v1` cold-start Agent smoke | **2/2 valid pairs**, SOURCE 2/2 success, TMF 2/2 success, TMF adoption **0/2** | A new stateless Agent did not adopt injected notes on its first encounter. **Scope limit:** it never performed the first visit, so this cannot negate repeat/revisit value for one cognitive subject. Result is preserved and not regraded. |
| `cognitive_continuity_v1` | **INVALID_PROTOCOL**; 0/2 has no evidentiary force | Fixture/task/golden contradiction and non-TMF model-authored memory contamination. Preserve, never regrade or attribute to product. |
| `cognitive_continuity_v2` resumed smoke | **2/2 valid pairs**; SOURCE 2/2 success, TMF 2/2 success, qualified adoption **0/2**; STOP | Runtime recovered; the old blocked audit is retained but superseded. B01 had structural claim coverage yet repeated 1 read/91 bytes; B03 had no task claim coverage and repeated 2 reads/102 bytes. The frozen adoption gate prohibits a full run. |

### Product decision

**Do not recommend TMF_MIDDLEWARE for production on an Agent-value, speed, token, or reread-reduction claim.** It may be used only as an experimental safety/navigation mechanism where users explicitly accept unproven outcome value and count injection cost. Continue to recommend source-authoritative fallback and the hard freshness/stale gate as a qualified mechanism, not as a productivity win.

Evidence level is **mechanism-qualified / Agent-outcome-unproven**. The cold-start smoke is descriptive (N=2). Cognitive v1 is invalid and excluded. Cognitive v2's runtime recovered and its real N=2 smoke completed, but adoption was 0/2, so the frozen gate stopped the full run. Stable adoption, Python/Java breadth, semantic outcome, and net economic value remain unproved.

## Cognitive continuity v2 resumed outcome

The unchanged frozen smoke completed after the external broker timeout hierarchy was repaired. Both arms were valid and successful on B01 and B03, but neither TMF arm qualified as adoption. B01's TMF context included a structural call-edge claim and still repeated the same phase-B source read (1 read/91 bytes). B03 had no task claim coverage and repeated 2 reads/102 bytes. Preflight claim coverage of 2/10 tasks is structural coverage only; it does not establish that a claim answers task-specific implementation semantics. Current derived claim content cannot generally replace a second source read.

TMF also cost more in each observed pair: B01 6,894 vs 1,376 SOURCE tokens and B03 7,420 vs 2,500. This is not a failure of the qualified middleware freshness/stale-blocking mechanism; it is failure to demonstrate claim-content sufficiency, Agent adoption, reread reduction, or value in this smoke. The historical runtime-blocked [`audit.json`](../bench/agent_ab/cognitive_continuity_v2/results/audit.json) and [`HUMAN_AUDIT.md`](../bench/agent_ab/cognitive_continuity_v2/results/HUMAN_AUDIT.md) remain intact, while the resumed [`audit_resumed.json`](../bench/agent_ab/cognitive_continuity_v2/results/audit_resumed.json) and [`HUMAN_AUDIT_RESUMED.md`](../bench/agent_ab/cognitive_continuity_v2/results/HUMAN_AUDIT_RESUMED.md) supersede only their runtime status.


## Which experiment answers which question

| Mode | Question answered | Does not answer |
|---|---|---|
| Tool-mode | Will an Agent proactively call TMF retrieval? | Forced delivery or revisit continuity |
| Cold-start injection (`agent_middleware_value_v1`) | Will a stranger stateless Agent use supplied memory on its first source encounter? | Value on a second visit by the same cognitive subject |
| Mechanism (`middleware_hardening_v1`) | Are exact-target freshness, stale blocking, and localized reread gates mechanically sound? | Agent adoption/productivity |
| Cognitive continuity (`cognitive_continuity_v2`) | Can an explicit persistent cognitive layer carry source-bound knowledge from phase A into a different phase-B task across stateless model calls? | Hidden-state continuity or, after its smoke stop, broad/semantic/product value |

A cognitive subject here is the audited `logical_agent_id` + `workflow_id` and minimal envelope (completion flag, memory IDs, provenance), **not** language-model hidden state or transcript replay. SOURCE receives the same envelope without claims.

## Cold-start Agent outcome details

The comparison used stateless `gpt-5.6-sol`, the same prompts/order/tool/source/turn and call budgets, a raw-inference safety broker, isolated fixture copies, and a controlled autonomous read/search/edit/test loop. Middleware was the unchanged `45ab3e4` implementation and was forced immediately before selected reads; it did not depend on proactive TMF calls.

| Task | Mode | SOURCE | TMF | Audited adoption | Reads S/T |
|---|---|---:|---:|---:|---:|
| A01 Python understanding | fresh revisit | pass | pass | no | 1/1 |
| A03 Python local edit + test | fresh revisit | pass | pass | no | 1/1 |

Aggregate: source bytes 173/173, tool calls 8/8, estimated prompt tokens 1406/1874, completion 168/181, TMF injection 0/236, wall seconds 25.68/33.98 (SOURCE/TMF). No memory, stale-memory, post-reread, baseline, output-contract, runtime, or middleware errors occurred. Adoption is machine-audited and does not rely on model self-report.

## Experiment index and non-mixing rule

- Cognitive second-read v2: [`cognitive_continuity_v2`](../bench/agent_ab/cognitive_continuity_v2/) — resumed frozen smoke completed; 2/2 valid, both arms 2/2 successful, adoption 0/2; stopped before full run.
- Cognitive v1: [`cognitive_continuity_v1`](../bench/agent_ab/cognitive_continuity_v1/) — **INVALID_PROTOCOL**, historical artifacts only.
- Cold-start forced-middleware value: [`agent_middleware_value_v1`](../bench/agent_ab/agent_middleware_value_v1/) — preserved 0/2 scope-limited result.
- Mechanism only: [`middleware_hardening_v1`](../bench/agent_ab/middleware_hardening_v1/).
- Retrieval E2E: [`retrieval_e2e_v1`](../bench/agent_ab/retrieval_e2e_v1/).
- Active tool-mode Agent trials: [`java_real_v1`](../bench/agent_ab/java_real_v1/) and [`java_real_v2`](../bench/agent_ab/java_real_v2/).
- Historical revisit/path-injection studies are narrower simulated or mediated protocols.

**Never combine denominators or conclusions across tool retrieval, supplied-evidence broker answers, mechanism fixtures, and forced real-Agent middleware.** Commit under evaluation: `45ab3e43f8a8e3ef12b08c5c6bed76d1dade7d48`; experiment artifact commit is recorded in repository history after this page is committed.
