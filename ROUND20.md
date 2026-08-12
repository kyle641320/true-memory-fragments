# Round 20 — content-addressed read-only evaluation-store archive

## Contract

The Round 18 semantic lock can now be materialized as a portable archive. `create_store_archive` stores every non-ephemeral regular `.tmf` file as an exact-byte SHA-256 blob, records a canonical path-to-blob manifest, derives the archive directory id from the canonical manifest bytes, and makes the resulting tree read-only. Repeating creation for the same bytes is idempotent and verifies the existing archive before reuse. `reconstruct_store_archive` accepts only a new destination, verifies the manifest id and every blob first, reconstructs exact bytes, and then requires the reconstructed semantic inventory to equal the manifest inventory.

This is deliberately a library primitive rather than a checked-in multi-megabyte snapshot. Benchmark owners can place archives in an artifact store while the small existing `store-lock.json` remains the reviewable expected-state record. Production retrieval, the frozen benchmark corpus, and existing evaluator invocation are unchanged.

## Threat model

Covered:

- corruption or substitution of a manifest or referenced blob;
- absolute, parent-traversal, empty/dot-component, backslash, NUL, duplicate, or malformed archive paths;
- source-store symlinks and special files (the Round 19 fail-closed boundary remains in force);
- accidental overwrite of an existing reconstruction destination;
- divergence between reconstructed exact bytes and the semantic store lock inventory;
- nondeterministic or duplicate archive creation for identical store bytes.

Not covered:

- an attacker able to replace both archive and externally trusted archive id;
- cryptographic SHA-256 compromise;
- filesystem permission bypass by a privileged user (read-only mode is an accidental-write guard, integrity remains hash-based);
- concurrent mutation of a source store during archive creation; callers must archive a quiescent, already lock-verified input (a future atomic capture API can bind verify/capture more tightly);
- artifact transport, retention, signing, or automatic evaluator fallback to archives.

## Verification

- Focused tests cover deterministic/idempotent creation, exact-byte reconstruction and semantic inventory fidelity, read-only output, expected-id and blob-tamper rejection, unsafe manifest paths, and source symlink/FIFO rejection.
- Both real pinned stores are archived and reconstructed in temporary storage, preserving their checked-in lock digests.
- Full unit suite and `git diff --check` pass.

## Deferred

The next increment should add an atomic `verify_lock_and_archive` entry point and optional locator/evaluator archive selection, explicitly binding repository id, source commit, and store lock digest to an externally supplied archive id. Archive distribution remains outside the repository.
