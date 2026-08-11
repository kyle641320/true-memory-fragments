# Round 13 — source-observed Java event type rendezvous

## Boundary

This slice adds static source facts only. `publishes_type` means a method contains an explicitly resolved `ApplicationEventPublisher.publishEvent(new EventType(...))` call. `listens_type` means a method directly declares one supported, exactly imported listener annotation and one statically resolved parameter type. A shared event type is only a static candidate rendezvous. TMF does **not** claim runtime bean/listener registration, publication, delivery, ordering, transaction phase effectiveness, fallback behavior, or invocation.

Supported listener annotations require exact explicit imports: Spring `EventListener`, Spring `TransactionalEventListener`, and Spring Modulith `ApplicationModuleListener`. Same-named custom annotations fail closed. Dynamic `classes`/`value`, generic/unknown/ambiguous/external event types, non-exact publisher receiver types, and invalid parameter shapes stay unresolved with a reason and create no edge. `TransactionalEventListener.phase` and `fallbackExecution` are retained as declaration-only metadata and never evaluated.

## Implementation

- Added provider-neutral `publishes_type` / `listens_type` edge contracts and stable IDs.
- Each edge binds the source method, event type declaration, and annotation/callsite hash. Java derivation version is `java.derive.v8`; rename/delete/rebind reconciliation removes stale edges precisely.
- Retrieval exposes existing fresh event edges and a bounded shared-type static candidate. Presentation labels it `shared_source_observed_event_type_candidate`; it is not an event chain.
- No Petclinic symbol/path is hard-coded in extraction or retrieval.

## Tests

`tests/test_java_event_types.py` covers positive publication/listening, same-name annotation rejection, dynamic classes fail-closed behavior, transactional declaration metadata, and mutation cleanup/rebinding.

- Directed: `python3 -m unittest tests.test_java_event_types tests.test_mcp_ergonomics tests.test_final_contracts -q` — 16 passed.
- Java qualifications: `python3 tools/run_java_qualifications.py` — 46/46 passed, 731/731 checks.
- Full: `python3 -m unittest discover -s tests -q` — 508 passed.
- Real pinned Petclinic warm/assertion: `VisitScheduler.bookVisit -> VisitBooked` has a fresh `publishes_type` edge; overloaded `VetEventListener.on(VisitBooked)` has a fresh `listens_type` edge; both share the exact `VisitBooked` type claim.
- Real pinned P01 smoke at 3000 chars: valid bounded JSON; relations are `listens_type`, `publishes_type`, and one `calls`; no runtime claim.

## Frozen offline ablation

`bench/agent_ab/java_real_v1/ROUND13_ABLATION.json` was generated from unchanged frozen P01–P04 prompts before golden inspection. P01 and P02 now recall the listener through a source-observed `listens_type` relation. P03/P04 receive no event beautification. This establishes locator recall only, not agent correctness or causal benefit.

`bench/agent_ab/java_real_v1/ROUND13_REAL_SMOKE.json` records the pinned real P01 context payload. A frozen real-agent TMF_MAP rerun is intentionally launched only after this commit/push, as requested.
