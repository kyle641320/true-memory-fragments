# Changelog

## 0.1.0rc3 - UNRELEASED bounded Java/Spring handoff

### Added

- Conservative Java project, type, declaration, relationship, and bounded
  Spring source-analysis adapters, backed by 46 independent held-out corpora
  and 731 manifest-governed checks.
- Seven-fixture real Gradle integration and an index-free source-only smoke
  gate.
- Optional pinned `java` parser dependencies and vendored Linux wheels for
  offline verification.
- GitHub Actions release preflight covering all critical local release gates,
  isolated artifact construction and inspection, and installed-wheel smoke.

### Changed

- Corrected the Java semantic-provider boundary: TMF retains the optional
  javac adapter and provider-neutral ingestion, but build-system dependency
  resolution is permanently out of scope. Callers must supply classpaths
  explicitly; the experimental offline Maven resolver and its CLI surface
  were removed.

### Release status

- The warning-clean full suite baseline is 478 tests; the source-only gate
  exports its declared required inputs without VCS/generated state; all 46
  qualifiers, 731 checks, and seven real Gradle builds pass locally.
- `0.1.0rc3` is **UNRELEASED**. No tag, GitHub Release, or PyPI publication is
  claimed.
- Java/Spring evidence remains bounded source analysis, not compiler,
  classpath, framework-runtime, or enterprise-ready certification.

## 0.1.0rc2 - cross-repository release candidate

### Added

- Conservative Java relationship and framework windows with source-bound
  freshness, precise anchors, reverse lookups, and explicit partial coverage.
- Conservative YAML mapping/scalar config nodes and standalone SQL
  `CREATE TABLE` / `CREATE VIEW` declarations.
- Ten-repository production, mutation/restore, clean-build, and versioned
  clean-build release-policy gates.

### Changed

- Large-repository pristine clean warm now streams append-only claim writes
  instead of retaining the full claim cache. The post-remediation Guava run
  completed in 1,630 seconds with 299,900 KiB maximum RSS while retaining
  137,349 stable claim IDs.
- Package, Python API, and MCP server versions now share `0.1.0rc2`.

### Release status

- 206 tests pass, Java offline verification passes, and the ten-repository
  clean-build policy evaluates to `GO`.
- Guava passes both the 30-minute and 768-MiB performance targets, as well as
  the hard release limits.
- Three additional previously untested repositories—Apache Commons Lang,
  JUnit 5, and Java Design Patterns—pass clean/no-op, freshness, and edge
  endpoint integrity audits.
- Eventuate broker delivery, transaction commit, runtime dispatch, payload
  values, and compensation execution remain outside static proof.

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
- Current completion-window target: full suite 136 tests OK; held-out validation pass; self-dogfood freshness precision 1.0 / recall 1.0; Java offline verifier PASS.

### Pending confirmation

- MIT license choice and copyright holder/year must be confirmed by Kyle.
- Distribution name `true-memory-fragments` must be confirmed by Kyle before public PyPI publication.

## 2026-06-12 — Window 1/4 completion-plan maintenance

- Fixed Python nested class qualnames to remain scope-qualified inside function bodies; self-method call resolution remains conservative and links inherited methods only when the inheritance chain resolves to exactly one candidate.
- Kept mechanical contract slots honest: observed/mechanical slot confidence is capped at `<=0.6` and documented as interface-derived, not semantic proof.
- Hardened pure-rename identity migration: only one old missing path and one current path with the exact same blob migrate; ambiguous copies or rename+edit delete old tombstones and rederive new claims. Edge claims are rebound through endpoint id remapping and updated binding paths.
- Added local metrics/stat coverage and an offline `FIELD_TEST` plan harness. The harness writes a plan only and does not start repository reconnaissance, network access, or model warming.
