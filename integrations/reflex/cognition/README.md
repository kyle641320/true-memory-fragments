# Experimental trusted-local recovery cognition

This is a **source-checkout experiment**, not a production cognition service or a
claim that TMF is complete. The existing C1 recovery gate remains authoritative.
Observation persistence runs only **after** an already matched mutation releases
pending recovery. Recording failures do not reverse that release.

## Explicit opt-in and use

The plugin leaves observation recording disabled unless its optional
`recoveryObservationRoot` is supplied. Use an explicitly selected private local
directory. Observations contain source snippets and caller identifiers; this is a
trusted-local experiment, not an authenticated host custody boundary. The root
must be separate from the mechanical `.tmf` root and the cognition Store root.
Nothing automatically sends these files anywhere.

From a repository source checkout, an explicit caller can import:

```python
from integrations.reflex.cognition.bridge import (
    ObservationContext, CognitionIdentity, submit_candidate, validate_candidate,
)
from integrations.reflex.cognition.prototype import Store
```

Supply a canonical repository root, canonical mechanical state root, separate
canonical cognition state root and independent caller session/run/tool-call
identity via `ObservationContext`. Pass an explicit `CognitionIdentity(artifact,
task_scope)`. Do not reconstruct caller authority from the observation itself.
`submit_candidate` requires a ticket, context, identity, path, function, parameter,
and producer, with an optional explicit parent revision. `validate_candidate`
also requires a revision, event ID and expected sequence. See the runnable tests
for complete fixture callers.

The bridge currently supports only a **Python required-parameter declaration**
proposition. A passing predicate is not business correctness, semantic proof,
agent understanding or adoption. Submission and validation are separate explicit
calls; neither adopts or activates a revision.

## Stable identity and preserved lineage

Stable artifact/task-scope keys bind explicit cognition identity to the canonical
repository/mechanical/cognition route. Session/run/call IDs and ticket IDs are
provenance, not stable identity. One reserved canonical JSON provenance entry in
each immutable revision's `limitations` binds the full context, explicit identity
and complete observation digest. This is structured metadata, not authentication.
Validation requires the original provenance and current source vector; a new
ticket cannot retarget an old revision. A parent must have exactly matching stable
identity and route/provenance. A stale parent can remain historical lineage, but
cannot thereby become current. No inferred parent, automatic supersession,
adoption or reactivation is introduced.

## Bounds and known limitations

- Snapshots: at most 16 paths, 8 KiB per UTF-8 source, 160 KiB per observation.
- Journal: at most 64 directory entries; no silent eviction of provenance.
- Recording gaps: bounded in-memory debug records, not durable host notifications.
- Source reads are bounded and checked for drift, but not a hostile-filesystem
  custody or atomic multi-file snapshot protocol.
- Store events/revisions are trusted-local SQLite state. Generic lifecycle APIs
  in `prototype.py` do not imply host-owned approval or activation.
- The existing package build intentionally includes `tmf*` only. This integration
  is not added to the pip wheel, CLI, preview package or default agent setup.
- No F3/C2 delivery, fence, token, operation-queue or session-start changes are
  included; this is based on the existing C1 mainline.

## Reproducible checks

From the repository root:

```sh
python3 -m unittest discover -s integrations/reflex/tests -v
cd integrations/reflex/openclaw-plugin
npm ci
npm test
npm run typecheck
```

Python requires the project's supported Python and standard library; the plugin
harness requires Node, Git, Python and its declared development dependencies.
No model or OpenClaw SDK installation is needed for these tests.

- `test_cognition_lineage.py`: 14 route, provenance, identity and parent cases.
- `recovery-observation.test.cjs`: 13 synthetic-oracle observation/bridge cases
  plus UUID failure containment. The latter injects a UUID throw into an isolated
  evaluation of current source, without changing production code.
- `recovery-lineage-engine.test.cjs`: actual C1 Python `pre_tool_use` and
  `local_warm` against a temporary Git repository, manually dispatched hooks and
  synthetic built-in-shaped executors with real file I/O. Two recoveries preserve
  stable identity/explicit parent, reject stale first evidence, reopen the Store,
  and independently execute USD/EUR fixture outcomes. It is **not** installed SDK
  executor coverage or real host runtime end-to-end coverage.

An earlier local experiment additionally exercised installed Read/Edit executors
with manually dispatched hooks. That environment-specific result is not a
portable CI claim and its SDK-internal imports are deliberately excluded here.
Actual automatic host hook scheduling, autonomous candidate generation/adoption,
durable host custody/activation, and production/promotional readiness remain
unverified by this slice.
