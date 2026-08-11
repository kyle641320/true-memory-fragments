# ROUND 6 — remaining comment-only false positives

## Scope and decision

This round investigated only the six semantic false positives left by Round 5. Existing uncommitted changes were preserved; no commit/push and no other worktree was touched. No compiler integration was started.

The six claims are all **legacy Java `writes` claims** whose bindings already have roles (`writer`, `declaration`) but whose stored bodies predate `writer_node_kind`. Current freshness deliberately fails closed: the role resolves to a missing node-kind field, so the writer is reported as `java node missing`. This is not evidence that the method disappeared, and it is not safe to guess legacy endpoint kinds merely to make the metric zero. Therefore no production freshness relaxation was made.

## Independent comment-only oracle

The E2E now records two independent dimensions:

- **file freshness** — exact file blob identity; adding a comment must invalidate the file claim;
- **semantic freshness** — pre/post Java declaration identities and token hashes extracted independently from TMF claim/binding output; a comment outside declarations changes no semantic fact.

The report now stores every stale claim's id, edge kind, classification, stale reason, complete binding identity, and source anchors. `semantic_actual_stale` excludes the expected file-blob invalidation.

## Exact six semantic FPs

All are `kind=structure`, `scope=cross-repo`, `edge_kind=writes`, classification `legacy_role_metadata`, source file `src/main/java/org/springframework/samples/petclinic/owner/domain/Owner.java`, and stale reason `<writer>: java node missing`:

1. `claim_write_edge_1580e5f6f476cc92` — `Owner.setFirstName` (207–209) → `Owner.firstName` (58–60)
2. `claim_write_edge_370ce88740ee656e` — `Owner.setCity` (96–98) → `Owner.city` (70–72)
3. `claim_write_edge_753628126f8716a1` — `Owner.setLastName` (215–217) → `Owner.lastName` (62–64)
4. `claim_write_edge_a04c675e8f20bece` — `Owner.setAddress` (88–90) → `Owner.address` (66–68)
5. `claim_write_edge_a54cca52d5a797e9` — `Owner.setTelephone` (104–106) → `Owner.telephone` (74–77)
6. `claim_write_edge_d91707f42e1228c8` — `Owner.setId` (195–197) → `Owner.id` (54–56)

Full binding hashes and reasons are in `report.json` → `mutation.stale_details_before_rewarm`. The seventh stale item is the expected `claim_file_62809736d8fae777` file-blob control and is not a semantic FP.

## Attribution

- legacy role/body metadata: **6**
- class/container hash: **0**
- unexpected file blob: **0** (one expected file control)
- unknown role: **0**
- repository dependency: **0**
- other: **0**

## Controls and regressions

Existing focused mutation regressions remain active and cover comment-only method control, semantic method mutation and rewarm, DI endpoint removal/candidate change, and JPA entity mutation/rebind. Round 6 strengthens the real-project regression artifact by making the oracle dimensions explicit and persisting per-claim diagnostics. Semantic positive/negative controls remain in the full suite; unknown roles and incomplete legacy metadata continue to fail closed.

## Results

Before → after Round 6 (comment-only semantic oracle):

- TP: **0 → 0**
- FN: **0 → 0**
- FP: **6 → 6** (honestly retained legacy claims)
- expected file invalidations: **1 → 1**
- stale after rewarm: **0**

Project assertions: TP **77**, FN **0**, TN **12**, FP **0**. Retrieval MRR **0.456498**, Recall@10 **0.75**.

## Gates

- Java qualifications: **46/46 passed** (`java-qualifications-round6.log`)
- Full unittest discovery: **492/492 passed** in 52.438s (`unittest-round6.log`)
- Real-project E2E: passed; all 89 assertions passed (`run-round6.log`, `report.json`)
- `git diff --check`: passed

## Remaining reason / next decision

Exactly six semantic FPs remain because old stored write-edge bodies do not contain endpoint-kind metadata. Safe ways to eliminate them require an explicit migration/rewarm policy or derivation-version invalidation decision. Freshness must not infer a kind from role/qualname for legacy claims. This is handed back to the parent session; compiler integration is intentionally out of scope.
