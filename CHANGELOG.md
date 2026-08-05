# Changelog

## 0.1.0-writes - relationship completion step 1

### Added

- New additive edge type `body.edge_kind = "writes"` for Python functions writing module-level declaration nodes.
- Stable write edge ids via `stable_write_edge_claim_id(writer_id, declaration_id)`.
- Conservative `global`-aware write parser:
  - `global X; X = ...`, `X: T = ...`, `X += ...`, and `del X` can write same-file tracked declaration `X`;
  - assignment to `X` without `global X` is local and never linked;
  - `nonlocal` is unresolved, not linked;
  - nested def/class bodies are not attributed to the enclosing function.
- `X += ...` / `X = X + ...` with `global X` can surface both `reads` and `writes`.
- Function graph surface: `writes` and `writes_unresolved`.
- Declaration graph surface: `written_by` with `coverage = "partial"`.
- Separate `reverse_writers()` API; writers, readers, and callers remain distinct.
- Forward and reverse call/read/write references now expose precise anchors `{path, line_start, line_end, qualname}` when available.
- Held-out `_write_edge_checks` bench and self-dogfood expected-stale oracle support for `writes` endpoints.

### Backlog explicitly not done in this window

- use-type / implements / inheritance / override / construct relations.
- DI assembly, pub-sub / Kafka topics, SQL / ORM, codegen, macros, reflection, multi-language edges.


## 0.1.0-read-edges - config-usage Python MVP

### Added

- New additive edge type `body.edge_kind = "reads"` for Python functions reading module-level declaration nodes.
- Stable read edge ids via `stable_read_edge_claim_id(reader_id, declaration_id)`.
- Conservative parser for unambiguous `Name` loads only:
  - same-file top-level declarations;
  - direct `from module import NAME` when that module has a tracked declaration;
  - local parameters, assignments, and comprehension targets shadow names and prevent edges.
- Function graph surface: `reads` and `reads_unresolved`.
- Declaration graph surface: `read_by` with `coverage = "partial"`.
- Separate `reverse_readers()` API; readers are not mixed into `reverse_callers()`.
- Held-out `_read_edge_checks` bench and self-dogfood expected-stale oracle support for `reads` edge endpoints.

### Deferred explicitly

- Config file key reads.
- Environment variable reads.
- Framework getters, dependency injection, annotations, and dynamic sources.
- Non-Python extractors, YAML, and SQL.


## 0.1.0 - release-wrapup

Initial open-source preparation release for True Memory Fragments.

### Added / included

- Lazy source-bound memory store in `.tmf/` with `.tmfignore` support.
- Stable import package `tmf` and distribution package `true-memory-fragments`.
- Console entry point `tmf = tmf.cli:main`.
- Zero runtime dependencies (`dependencies = []`).
- Conservative Python node support:
  - functions;
  - classes;
  - partial module-level declarations;
  - partial JSON/TOML top-level config nodes;
  - partial literal Flask/FastAPI-style API route nodes.
- Conservative observed call edges and reverse callers.
- Thin retrieval by default, thick/full view opt-in by claim id.
- Reviewer/JSON explanations with freshness, trust, provenance, anchors, bindings, and action hints.
- Feedback recording that does not turn hunches into facts.
- Held-out validation bench and real-package self-dogfood validation.
- Release docs: README, DESIGN correctness contract, CONTRIBUTING, GitHub Actions CI stub.

### Validation milestones

- Held-out validation bench covers freshness precision/recall, invariants, source support, degrade-to-source, thin/full consistency, verification boundaries, router/embedder additivity, config nodes, API nodes, and reverse callers.
- Real-repository self-dogfood exposed and drove fixes for two over-invalidation classes before this release:
  - boundary indentation over-invalidation around class/function spans;
  - nested containment measurement for self-validation freshness sampling.
- Current release-wrapup target: full suite 82 tests OK; held-out validation pass; self-dogfood freshness precision 1.0 / recall 1.0.

### Pending confirmation

- MIT license choice and copyright holder/year must be confirmed by Kyle.
- Distribution name `true-memory-fragments` must be confirmed by Kyle before public PyPI publication.
