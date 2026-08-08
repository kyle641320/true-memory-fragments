# TMF Schema v1

Disk schema version: `tmf.schema.v1`.

v1 stores one claim per JSON file under `.tmf/claims/<claim_id>.json`.
Claim id is stable by node identity, not by content hash:
- file node: `path`
- Python function node: `path + qualname`

Re-derivation overwrites/supersedes the same node instead of creating content-hash orphan claims.

```json
{
  "schema_version": "tmf.schema.v1",
  "id": "claim_file_... | claim_fn_...",
  "claim": "One-sentence derived source summary.",
  "kind": "structure",
  "scope": "file | function",
  "bindings": [
    {
      "path": "relative/path.py",
      "file_blob": "working-tree git blob sha from git hash-object -- path",
      "fn_hash": "token-stream function hash or null",
      "commit": "HEAD commit at derivation time"
    }
  ],
  "provenance": "model|git|human:<name>",
  "evidence": "observed|inferred|verified",
  "confidence": 0.0,
  "endorsed_by": null,
  "last_verified": "ISO-8601 UTC timestamp",
  "model": "tmf-v1-heuristic",
  "body": {
    "summary": "Short derived mechanism summary, not a source-code copy.",
    "qualname": "function qualified name when scope=function",
    "anchors": [{"path": "relative/path.py", "line_start": 1, "line_end": 20}],
    "feedback_events": [],
    "hunches": []
  }
}
```

## Freshness protocol

- `file_blob` is always the current working-tree hash:
  ```bash
  git hash-object -- <path>
  ```
- `commit` remains provenance/time anchor only; it is not the freshness gate.
- `fn_hash` is computed from the working-tree function body token stream.
- Do not regex-strip whitespace for `fn_hash`.
  - Python v1 uses `tokenize`.
  - Comments/trivia are ignored.
  - `INDENT` / `DEDENT` / `NEWLINE` are recorded as bare structural events, without their whitespace strings, so indent width and CRLF/LF formatting do not trip freshness.
  - literals and identifiers are preserved, so `'a b'` and `'ab'` hash differently.
- if a file is deleted, blob mismatches, function disappears, or `fn_hash` mismatches, claim is stale.
- after re-deriving a path, storage is reconciled against current node ids; function rename/delete removes tombstone claims so dead nodes do not force perpetual re-derive.
- path reconciliation may only delete single-binding claims whose only binding is the current path (`len(bindings)==1 and bindings[0].path==relpath`). Multi-binding architecture/cross-file claims are skipped and must be managed by their own derivation flow.

## Model derive protocol

- Model output is only a candidate, not a fact.
- Source code, comments, docstrings, commit text, and PR text are untrusted data and must never be treated as model instructions.
- Candidate evidence classes:
  - `source_verifiable`: can be checked against source; only supported candidates can become `observed`, capped below high confidence.
  - `intent_needs_provenance`: why/intent claims; source alone usually cannot prove them, so they remain `inferred` + low confidence unless backed by docstring/commit/PR evidence or endorsement. Docstring/commit support makes them attributed mid-confidence, still `inferred`, not `observed`/`verified`.
- Docstring provenance lives inside the function span, so docstring edits change `fn_hash` and stale bound claims.
- Commit provenance records the blamed commit SHA and message for attribution/audit only; freshness still binds to current working-tree `file_blob`/`fn_hash`, so later code changes stale the claim even though the commit text is immutable.
- Provenance text is stored and passed as `*_untrusted_data`; it can support a claim but cannot issue instructions or alter confidence caps.
- Low temperature/model version provenance should be recorded in `model`; committed `.tmf/` is reproducible cache, not authority.

## Confidence protocol

- Fresh does not mean correct; it only means bindings match current source.
- Usage/read frequency never raises confidence.
- `verified` feedback can raise confidence and set evidence to `verified`.
- `falsified` feedback lowers confidence and marks `needs_rederive`.
- `hunch` feedback is recorded as a non-factual note; it never overwrites claim text, bindings, or evidence.

## Honesty rule

- stale claims may still be shown only as stale/low-confidence summaries;
- precise behavior must fall back to current source.

## Explain protocol

`tmf explain` recomputes freshness against the current worktree every time; it does not trust cached freshness.

Reviewer text separates:
- trust label and claim text;
- belief provenance (`docstring`, `commit`, future `pr`) with quoted untrusted data;
- freshness bindings (`file_blob`, `fn_hash`, commit anchor);
- source anchors.

Agent JSON includes machine-branchable fields:
- `fresh`
- `stale_reasons`
- `trust`
- `evidence`
- `confidence` and `raw_confidence`
- `confidence_cap_applied`
- `anchors`
- `belief_provenance`
- `freshness_bindings`
- `action_hint`

Quoted provenance text remains `quoted_text_untrusted_data` and must not be treated as instructions by downstream agents.

## Retrieve thin/thick protocol

Default `tmf retrieve` returns a thin list built from the same explain data:

- `id`
- one-line `claim`
- `kind` / `scope` / optional `qualname`
- `trust.level` + `trust.label`
- `fresh` + `stale_reasons`
- `confidence` + `confidence_cap_applied`
- `anchors`
- `action_hint`
- `belief_provenance_refs` without quoted text
- `freshness_binding_refs` with short hash prefixes only

Default thin output intentionally omits thick body, available provenance text, quoted untrusted provenance, feedback history, hunches, and full binding hashes.

To expand one node:

```bash
python3 -m tmf.cli retrieve --full <claim-id> --repo <repo>
```

This returns the explain payload plus `claim_record`, including thick body.

## Calls edge protocol v2-first-cut

Python calls edges are conservative. The resolver only creates observed edges for:

- module-local `Name()` calls that resolve to a unique top-level function in the same file;
- `self.method()` calls that resolve to a method on the same class.

It does not create guessed edges for dynamic dispatch, unknown attributes, external/stdlib functions, cross-file imports, or ambiguous names. These are recorded as `unresolved_calls` with a reason.

Function claims may carry a thin graph body:

```json
{
  "graph": {
    "callees": [{"target_id":"...", "target_qualname":"helper", "evidence":"observed", "resolution":"module_name_or_self_method"}],
    "callers": [{"source_id":"...", "evidence":"observed", "resolution":"module_name_or_self_method"}],
    "unresolved_calls": [{"expr":"obj.run", "reason":"attribute_call_not_resolved"}]
  }
}
```

Edges are regenerated on read-through with the function claims, so endpoint rename/delete recomputes or removes the relevant graph data.

## Cross-file import calls v2-first-cut

Cross-file calls are conservative and forward-only in this step. Resolved cases:

- `from x import f; f()` when `x` maps to exactly one repo-local `.py` or package `__init__.py`, and `f` is a direct top-level function in that target file.
- `import x as y; y.f()` when `x` maps uniquely and `f` is a direct top-level function in that target file.

Not resolved:

- `from x import *`
- re-export chains (`b.py` imports `f` from `c.py`)
- unknown attributes / dynamic calls
- external/stdlib imports
- ambiguous/missing module paths

Cross-file edge claims are stored as `claim_edge_*` with two bindings: caller function and callee function. They bind both endpoint `file_blob`/`fn_hash` values, so either endpoint changing stales the edge claim.

Path-local node reconciliation skips multi-binding claims. Cross-file edge lifecycle is handled by `reconcile_edge_claims_for_caller_path`, which deletes stale edge claims whose caller path was just re-derived and no longer emits that edge. Cross-file reverse callers are not yet a full repository index; that is a later v2 step.
