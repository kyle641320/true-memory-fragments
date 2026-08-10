# True Memory Fragments release notes

## 0.1.0rc3 — UNRELEASED

Status: **UNRELEASED**. The bounded Java/Spring source-analysis handoff is
release-ready under the gates in `RELEASE_AUDIT.md`, but rc3 has not been
tagged, uploaded to PyPI, or published as a GitHub Release.

### Added

- Conservative Java project, type, declaration, relationship, and framework
  source evidence, including bounded Spring bean/injection, endpoint,
  messaging, persistence, resilience, scheduling, security, transaction, and
  configuration-properties adapters.
- A manifest-governed aggregate qualification gate covering 46 independent
  held-out corpora and 731 checks.
- A bounded real-Gradle integration gate for seven selected fixtures and an
  index-free source-only smoke gate.
- The optional `java` extra, pinned to `tree_sitter==0.25.2` and
  `tree_sitter_java==0.23.5`, with vendored Linux wheels for offline release
  verification.
- GitHub Actions release preflight for qualifications, real Gradle builds, the
  warning-clean full Python suite, source-only smoke, isolated package builds,
  archive inspection, and installed core/offline-Java smoke tests.

### Verified preflight baseline

- Aggregate Java qualifications: 46/46 verifiers and 731/731 checks.
- Real Gradle integration: 7/7 clean builds.
- Full Python suite: 478 tests under `-Werror`.
- Source-only smoke: required source inputs exported without VCS/generated
  state, with qualifications, focused tests, and compileall passing (685 files
  in the audited local worktree; ignored caches are not part of the contract).
- Isolated rc3 sdist/wheel build, metadata and exclusion inspection, core
  install smoke, and offline `java` extra install smoke.

### Scope boundary

Java/Spring support remains conservative source analysis. Compiler/JDT/SCIP
classpath semantics, dynamic builds, broad framework runtime behavior, and
enterprise-ready certification are not claimed. Publication remains a separate
explicitly authorized operation.

## 0.1.0rc2 — PUBLISHED

Status: **GO** under policy `tmf-java-clean-build-2vcpu-4g-v1`.

## Verified gates

- Full unittest suite: 206 tests OK after the warm-memory remediation.
- Offline Java verifier: PASS.
- Ten-repository cache validation: 8 PASS, 2 Eventuate PARTIAL, 0 BLOCKED.
- Mutation/restore: ordinary repositories pass; Eventuate remains PARTIAL only for declared runtime-proof boundaries.
- Guava clean warm after streaming remediation: 3,230 files, 137,349 claims, 1,630 seconds, 299,900 KiB RSS, complete coverage, zero failures.
- Guava no-op warm: 17.23 seconds, derived=0, skipped=3,230.

## Scope boundary

Runtime broker delivery, transaction commit, dispatch, payload values, and compensation execution remain outside static TMF proof. Eventuate PARTIAL is not full-stack runtime certification.

This release candidate is published as Git tag and GitHub prerelease `v0.1.0rc2`, and on PyPI as `true-memory-fragments==0.1.0rc2`. PyPI publication used GitHub OIDC Trusted Publishing after SHA256 verification of the GitHub release artifacts.
