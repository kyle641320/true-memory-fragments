# Round 18 — pinned-store evaluation reproducibility

## Decision and contract

Evaluation infrastructure now pins the mutable `.tmf` inputs independently of the frozen Java real-v2 evidence. `bench/agent_ab/java_real_v2/store-lock.json` records, per repository, only the public repository id, pinned source commit, canonical store digest, file count, and component counts. It contains no absolute/private paths, claim text, raw context, local machine identity, or store payloads.

Before TMF evaluation, both `repo_tmf_locator.py` and the Round 17 offline evaluator must pass source-commit and store-lock preflight. They then copy the repository and `.tmf` store to a temporary directory and create `McpService` only against that copy. Freshness/read-through writes may change the temporary store but cannot change the locked source store.

The digest is SHA-256 over sorted relative file names and canonical content hashes. JSON object key/format order is normalized; JSON list order remains significant because it can encode semantic binding or relation order. Only ephemeral lock/temporary files are ignored. Verification metadata, local identity, provenance, and foreign-store markers remain locked because they can affect freshness or trust behavior. Inventory output exposes counts and a digest, not file names or content.

## Locked state

The current pinned stores are accepted as a **new Round 18 lock**:

- Petclinic at `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`: 1,073 claims / 1,077 locked files, digest `badf619c34a7e14b0a638d297e5640a64f9328b19f7b6b81e1d395d484fb3b52`.
- JHipster at `f8da577c944ecc4db46fc961a1ba022d5bbf8964`: 5,768 claims / 5,772 locked files, digest `212934e461e9bae86da556472bb226111cf20dedd9c8f8292ddafe39cd608665`.

This does **not** reconstruct the Round 16 store. No Round 16 store snapshot or complete content inventory exists, and Round 17 observed different metrics from mutable stores at unchanged source commits. The only supported statement is that these are the observed current stores captured by the new lock.

## Threat model

Covered:

- silent claim/index additions, removals, or semantic content edits;
- using a store with the right repository source commit but wrong mutable cache state;
- source-store mutation caused by status, warm, context, or freshness read-through;
- false drift from JSON formatting/object-key order;
- leakage of absolute store paths, machine identity, claim text, or raw answers through the lock artifact.

Not covered:

- malicious edits to both the lock and store in the same change (review/version control is the trust root);
- reconstruction or archival recovery of historical Round 16 bytes;
- cross-platform changes in non-JSON bytes or genuine JSON list ordering;
- deterministic model/agent outputs beyond deterministic store inputs;
- production store semantics or relation ranking (unchanged).

## Verification

- Focused store-lock tests: 5/5 passed, covering canonical hashing, identity/trust and semantic drift, commit drift, private-path/content omission, and disposable write isolation.
- Both current pinned stores pass the checked-in lock.
- Locator smoke test returns Petclinic status from a disposable copy with locked digest `badf619c…`.
- Round 17 evaluator completes against locked disposable copies with baseline metrics unchanged at 3k `2/20` and 10k `7/20`; source-store inventories are byte-identical before/after.
- Full Python suite: 525/525 passed.
- Java qualification aggregate: 46/46 groups passed.
- `py_compile`, `git diff --check`, frozen-evidence hashes, and sensitive-context pattern scan passed.

## Frozen integrity

No frozen prompt, golden, report, raw answer, manifest, or protocol file was changed. The separate store lock and helper live alongside the frozen corpus but outside those evidence files. Round 17 evaluator behavior changes only at input preflight/copy setup; ranking, packing, scoring, goldens, and result semantics are unchanged.

## Limitations

The lock is an input fingerprint, not a portable snapshot: another machine must obtain exactly matching stores independently. Changing any claim field, freshness/verification metadata, local identity, trust marker, reverse index, warm manifest, schema version, path inventory, or list order changes the digest. A missing or drifted store fails closed rather than rebuilding silently.
