# ROUND 7 — explicit legacy Java relationship rewarm

## Decision

Round 6's six false positives were not a freshness-rule defect. The Petclinic evaluation store already advertised `java.derive.v6`, but some relationship claim bodies still had pre-v6 endpoint metadata. A normal version bump could not fire again, and read-time inference would be unsafe.

The implementation therefore adds a narrow, explicit migration detector in `warm`:

- inspect only stored Java relationship claims whose known edge schema is missing a required endpoint node-kind field;
- resolve only the claim's explicit owner path (`writer_path`, `caller_path`, etc.); never infer endpoint kinds;
- schedule only that tracked Java owner path for normal source-authoritative derivation/reconciliation;
- report affected claim/path counts;
- leave unrelated Java and non-Java paths untouched.

The existing per-path warm checkpoint and claim reconciliation provide the migration semantics: replacement is deterministic, a completed owner is checkpointed, interruption leaves remaining owners discoverable, and rerun converges to a no-op. No whole-store rebuild and no read-time compatibility guess were added.

## Code and tests

Changed in this round:

- `tmf/warm.py`: required endpoint-kind schema, legacy detector, owner-only rewarm scheduling, migration counters, no-op guard.
- `tests/test_warm.py`: a mixed Java/Python old-store fixture removes `writer_node_kind` after a complete v6 warm, refreshes the synthetic manifest inventory, then proves exactly one Java owner is rederived, the old write claim id is replaced with a source-derived claim containing `writer_node_kind=method`, freshness is restored, and the second run is idempotent.

Freshness remains fail-closed for incomplete metadata. The migration repairs the store before normal reads rather than weakening `check_freshness`.

## Real-store migration impact

First Round 7 E2E warm:

- Petclinic: **29 legacy relationship claims / 10 tracked Java owner paths**; derived 10, skipped 48.
- JHipster: **140 legacy relationship claims / 32 tracked Java owner paths**; derived 32, skipped 137.
- Total: **169 claims / 42 Java paths**.

These counts include every recognized legacy Java relationship edge in the two old evaluation stores, not only the six visible Round 6 write FPs. No unrelated path was scheduled by the migration.

The exact six Round 6 write claim ids remain deterministic and were replaced in place. All now contain `writer_node_kind=method` and `java.derive.v6`:

- `claim_write_edge_1580e5f6f476cc92`
- `claim_write_edge_370ce88740ee656e`
- `claim_write_edge_753628126f8716a1`
- `claim_write_edge_a04c675e8f20bece`
- `claim_write_edge_a54cca52d5a797e9`
- `claim_write_edge_d91707f42e1228c8`

## Mutation results

Independent comment-only oracle after migration:

- changed semantic facts: **0**
- expected semantic stale: **0**
- actual semantic stale: **0**
- semantic FP: **0**
- expected file-blob invalidations: **1**
- unrelated stale: **0**
- stale after rewarm: **0**

The focused suite also retains the real semantic mutation control (`return 1` → `return 3`) and proves the affected method/class claims become stale and rewarm cleanly. DI endpoint and JPA entity dependency mutations also remain green.

## Gates

- Targeted migration/freshness tests: **5/5 passed** (`targeted-round7.log`).
- Java qualifications: **46/46 passed** (`java-qualifications-round7.log`).
- Full unittest discovery: **493/493 passed** in 52.344s (`unittest-round7.log`).
- Real-project E2E: **89/89 assertions passed**, TP 77, FN 0, TN 12, FP 0 (`run-round7.log`, `report.json`).
- Retrieval unchanged: MRR **0.456498**, Recall@10 **0.75**.
- `git diff --check`: passed.

## Scope stop

Existing uncommitted work was preserved. No commit or push was made, no other worktree was modified, and compiler integration was not started.
