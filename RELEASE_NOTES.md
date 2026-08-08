# True Memory Fragments 0.1.0rc2

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

This is a release candidate. It is not a git tag, pushed release, or PyPI publication.
