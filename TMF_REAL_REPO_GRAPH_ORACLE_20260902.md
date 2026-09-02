# TMF Real-Repo Graph Oracle — 2026-09-02

Verdict: **FAIL**.

Scope: bounded hand-checked reverse graph oracle over pinned real Petclinic and JHipster repositories from `bench/agent_ab/java_real_v2`. It warms only selected source files and evaluates callers/used-by-type/subtypes/implementors plus negative controls. This is larger real-repo graph evidence, not a complete enterprise graph certification.

## Summary

- Checks: 4/5 pass.
- Micro precision/recall: 0.800 / 0.800.
- Macro precision/recall: 0.900 / 0.900.
- TP/FP/FN: 4/1/1.

## Checks

- petclinic_callers_vetroster_assignVet: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- petclinic_used_by_type_visit_booked: FAIL; precision=0.500; recall=0.500; tp=1; fp=1; fn=1.
- jhipster_subtypes_operation_bag_relationships: PASS; precision=1.000; recall=1.000; tp=2; fp=0; fn=0.
- petclinic_no_callers_owner_repository_type: PASS; precision=1.000; recall=1.000; tp=0; fp=0; fn=0.
- jhipster_no_writers_operation_resource_type: PASS; precision=1.000; recall=1.000; tp=0; fp=0; fn=0.

## Failure analysis

The failing case is `petclinic_used_by_type_visit_booked`. Source shows both `VetEventListener.on(VisitBooked event)` and `VetRoster.assignVet(VisitBooked event)` use the `VisitBooked` type. The current reverse query returned `VetRoster.assignVet` plus a dangling historical listener claim id, while missing the current listener claim variant used by the caller edge. This is a real retained-store/index identity gap under the pinned real Petclinic repo, not a reason to mark the oracle PASS.

Earlier harness attempts also exposed oracle-design pitfalls and were corrected before this final report:

- `reverse_readers` is for field/declaration reads, not Java type-use edges; the real oracle now uses `reverse_used_by_types` for `VisitBooked`.
- Real-repo Java claim ids can differ from guessed stable IDs because the retained store has historical duplicate fresh variants; the oracle now resolves fresh Java claims from the store and keeps the remaining dangling-id mismatch as the finding.

## Interpretation

This upgrades graph query evidence beyond a synthetic fixture into pinned real Java repositories and finds a bounded real gap: most selected reverse graph queries pass, but Java type-use reverse identity is not yet clean on Petclinic retained-store history. Dynamic/reflection/DI runtime behavior remains out of scope.
