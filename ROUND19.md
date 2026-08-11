# Round 19 — fail-closed store-copy boundary

## Decision

The Round 18 evaluation lock now rejects symlinks and non-regular filesystem
entries anywhere in `.tmf`.  Round 18 copied repositories with symlinks
preserved; a symlinked store entry could therefore point outside the disposable
copy and invalidate the no-source-write boundary.  Rejecting such stores is the
smallest conservative fix: it neither changes TMF semantics nor silently
rewrites store topology.

## Verification

- The regression test constructs a claim symlink to an external file and
  verifies inventory generation fails closed with its store-relative path.
- Existing pinned Petclinic and JHipster stores contain no rejected entries and
  continue to match `store-lock.json`.
- Production retrieval/ranking and frozen Java real-v2 evidence are unchanged.

## Limitation

The lock supports regular files and directories only.  A future portable store
format should materialize an explicit archive rather than widening this
filesystem trust boundary.
