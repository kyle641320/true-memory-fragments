# TMF Real-Repo Graph Oracle — 2026-09-02

Verdict: **PASS**.

Scope: bounded hand-checked reverse graph oracle over pinned real Petclinic and JHipster repositories from `bench/agent_ab/java_real_v2`. It warms only selected source files and evaluates callers/used-by-type/subtypes/implementors plus negative controls. This is larger real-repo graph evidence, not a complete enterprise graph certification.

## Summary

- Checks: 5/5 pass.
- Micro precision/recall: 1.000 / 1.000.
- Macro precision/recall: 1.000 / 1.000.
- TP/FP/FN: 5/0/0.

## Checks

- petclinic_callers_vetroster_assignVet: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- petclinic_used_by_type_visit_booked: PASS; precision=1.000; recall=1.000; tp=2; fp=0; fn=0.
- jhipster_subtypes_operation_bag_relationships: PASS; precision=1.000; recall=1.000; tp=2; fp=0; fn=0.
- petclinic_no_callers_owner_repository_type: PASS; precision=1.000; recall=1.000; tp=0; fp=0; fn=0.
- jhipster_no_writers_operation_resource_type: PASS; precision=1.000; recall=1.000; tp=0; fp=0; fn=0.

## Interpretation

This upgrades graph query evidence beyond a synthetic fixture into pinned real Java repositories. Any failed case should be treated as either oracle mismatch or a real extraction/query gap after source inspection; dynamic/reflection/DI runtime behavior remains out of scope.
