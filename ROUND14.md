# Round 14 — explicit unknowns for role-shaped Java annotations

## Correctness defect

TMF previously returned empty resolved and unresolved arrays for source annotations that structurally looked like message-consumer or dependency-injection roles but were outside its exact supported annotation set. That made an unknown look identical to a true negative.

## Implemented boundary (Layer 1 + Layer 2)

- Message subscription extraction no longer uses the old marker-only early return. It still avoids repository-wide Eventuate discovery unless relevant markers exist, but directly scans method annotations with a bounded role vocabulary (`Listener`, `Consumer`, `Receiver`, `Receive`).
- An unrecognized role-shaped method annotation now creates only `subscribes_to_unresolved`, with `expr`, `annotation`, `qualname`, `bucket=topic_subscription`, `reason=topic_annotation_not_recognized`, and `edge_kind=subscribes_to`. It never creates a topic or resolved edge.
- Field annotations ending in the bounded DI vocabulary (`Inject`, `Autowired`, `Resource`) create only `injects_unresolved` when unsupported/unproved, with `expr`, `annotation`, `qualname`, `bucket=dependency_injection`, and `reason=injection_annotation_not_recognized`. Same-name unrelated imports and custom role-shaped annotations are explicit unknowns; arbitrary non-role annotations remain true negatives.
- `Resource`, `Inject`, `Singleton`, and `Named` presence resolvers now accept exact explicit Jakarta or Javax imports. Ambiguous imports, wildcard/static imports, and same-name local declarations remain fail closed. Namespace-specific resolution and `source_namespace` are retained.
- `Singleton` and `Named` remain presence-only declaration facts. They do not create DI edges, bean names, scope, runtime registration, or other resolved semantics.
- Existing graph keys are unchanged. Downstream consumers distinguish known absence from uncertainty through the populated existing `*_unresolved` arrays.

## Layer 3 deliberately not implemented

There is no broad heuristic over arbitrary annotation names, parameter names, method names, annotation arguments, framework packages, or prose similarity. Such inference would have an unacceptable false-positive surface. Future Layer 3 work requires a separately reviewed evidence model, confidence/coverage contract, corpus measurement, and explicit unresolved taxonomy; it must not manufacture resolved edges.

## Verification

`tests/test_java_trust_model_unknown_annotations.py` is a minimal end-to-end derivation fixture covering the reported `MdpMafkaMsgReceive` shape, true-negative arbitrary annotations, DI unknowns, all four Javax/Jakarta presence namespace mappings, fail-closed Resource decoys, exact Resource non-misclassification, presence-only Singleton/Named, and MQ/DI annotation rename/delete/exact rebind freshness.

- Directed trust/presence/Kafka/Spring suite: 55 passed.
- Full test suite: 518 passed.
- Java qualification runner: 46/46 verifiers passed, 731/731 checks; the four former Javax-negative checks are now positive exact-parity checks, so the gate was not weakened.
- `py_compile` and `git diff --check` passed for the changed implementation, tests, and qualification scripts.
- The minimal committed-source derivation fixture is the available E2E gate for this defect; no private repository was accessed.

The frozen `bench/agent_ab/java_real_v2/` directory was inspected read-only and has no Round 14 diff. No commit or push was performed.
