# TMF Java freshness diagnosis

## Finding

Round 4’s `Owner.getPets` result (`TP=8, FN=1, FP=73`) combines **one oracle error** with **one freshness-dispatch bug**.

- The mutation only inserts `/* tmf-heldout-mutation */` in the method signature. Java declaration hashes are token/semantic hashes and ignore comments. Therefore the `Owner.getPets` method-node claim correctly remains fresh. The evaluator nevertheless defines every claim whose binding qualname is `Owner.getPets` as stale; that produces the sole FN. It is not a product freshness miss.
- At the round-4 implementation (`4431bc2`), `tmf/freshness.py:check_freshness()` handles every `body.language == "java"` binding with `body.node_kind`. Relationship claims (`calls`, `reads`, `writes`, `uses_type`, etc.) do not have one shared `node_kind`; endpoint kinds live in role-specific fields (`caller_node_kind`, `callee_node_kind`, `reader_node_kind`, `declaration_node_kind`, `user_node_kind`, `type_node_kind`). The empty kind makes `_current_java_node_hash()` return `None`, so every relationship claim touching the edited `Owner.java` is marked `java node missing`, irrespective of the bound declaration. This is the 73 FP. The 8 TP are relationship claims directly bound to `Owner.getPets`, invalidated accidentally by the same bug.
- File-scope blob claims are a separate, intentionally coarse dependency and should be scored by a file oracle, not a declaration oracle.

Thus the authoritative result for this comment-only mutation should be no semantic declaration staleness (plus the file blob claim stale, if file freshness is measured separately), not 9 expected stale claims.

## Minimal repair slice

1. **`tmf/freshness.py` — `check_freshness()`**: select Java endpoint kind by `(edge_kind, binding.role)` and compare the stored hash against all matching overload hashes. Cover at least calls, reads/writes, uses_type, inherits/overrides and injects; fail closed for an unknown role rather than applying file-wide invalidation.
2. **`tmf/derive.py` — relationship claim builders (especially `derive_inject_edge_claim`)**: give bindings explicit roles and preserve endpoint node kinds in the claim body. Existing call/read/write/type builders are the model. No new global graph is required.
3. **`tmf/java_extract.py` + Java node/edge dataclasses**: carry exact endpoint identity/hash/kind from extraction into derived claims. For repository→entity metadata, represent the entity source dependency explicitly (path, qualname, node kind, declaration hash), rather than embedding only an FQN/boolean in `graph.repository_declaration`.
4. **Oracle/evaluation only (`reports/.../run_evaluation.py` or focused tests)**: derive expected impact from independently captured pre/post source facts/hashes, never from `binding.qualname` alone.

Smallest data-structure change: role-tagged `Binding` plus role→node-kind fields already used by ordinary Java edges; add an entity dependency binding (or equivalent typed dependency record) to repository claims.

## Independent mutation oracles

### 1. Method

Use two separate mutations:

- **Comment-only control** in `Owner.getPets`: method declaration hash must remain equal; only the file blob claim is expected stale.
- **Semantic token mutation** (for example return type/body token while preserving parseability): independently extract pre/post method identity and declaration hash. Expected stale = method-node claim and edges whose typed endpoint identity is that exact method; unrelated declarations/edges in `Owner.java` remain fresh. Include overload and same-file negative controls.

### 2. DI

Fixture with one exact interface injection point and one explicitly stereotyped implementation, plus an unrelated bean. Mutate independently:

- injection-point type/annotation token: injection endpoint and its `injects` edge stale;
- implementation stereotype or implemented-interface token: bean endpoint and edge stale;
- implementation method body only: DI edge remains fresh;
- add a second candidate: previous unique-resolution edge must reconcile away and unresolved reason must become ambiguity.

Oracle is a source-authored tuple `(injector identity, inject kind, requested FQN, unique bean identity)` computed from fixture literals, not TMF claims.

### 3. JPA / Spring Data

Fixture with `Repo extends JpaRepository<Entity, Id>` and tracked source `@Entity`, plus unrelated entity/repository. Mutate independently:

- repository domain generic `Entity -> OtherEntity`: repository declaration/dependency stale and rebinds;
- remove/change exact `@Entity`: entity dependency stale/reconciles unresolved;
- entity method body or unrelated field: repository→entity contract remains fresh;
- ID generic change: repository contract stale, entity declaration need not stale;
- query text change: only query metadata stales; repository→entity dependency remains fresh.

Oracle is the direct source tuple `(repository declaration identity, exact repository base FQN, domain FQN, id FQN, tracked @Entity declaration hash)`; query/runtime persistence behavior is explicitly excluded.
