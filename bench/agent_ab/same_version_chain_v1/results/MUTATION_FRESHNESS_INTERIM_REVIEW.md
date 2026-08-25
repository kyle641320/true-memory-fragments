# Mutation Freshness Interim Review

## What this line of experiments is testing

The target is TMF's distinctive value, not document-vs-TMF accuracy:

- stale detection from freshness bindings
- automatic invalidation when bound source changes
- withholding stale claims before the agent can rely on them

The fixture mutates B12 `Subscriber.java`: the old claim is bound to pre-mutation `Subscriber.invokeSubscriberMethod`, where `method.invoke(target, checkNotNull(event))` used to live. The mutation moves the concrete `Method.invoke` into `invokeReflectively(event)`, making the old method-hash-bound claim stale.

## Runs worth keeping

### V3 — clean withholding, but stale docs did not hurt

- SOURCE_ONLY: 5/5 raw pass, 5/5 semantic-adjusted pass
- STALE_DOC_CONTROL: 5/5 raw pass, 5/5 semantic-adjusted pass
- TMF_STALE_GATED: 5/5 raw pass, 5/5 semantic-adjusted pass
- TMF stale behavior: `stale_claim_withheld=5/5`

Interpretation: V3 cleanly demonstrates TMF stale detection and automatic claim withholding. However, the task prompt was strong enough that agents read/search current source and ignored the stale handbook note, so V3 does **not** demonstrate a stale-doc semantic penalty.

### V5 — stale docs can cause semantic wrong-site edits, but task became too hard

- SOURCE_ONLY: 0/5 raw pass, 0/5 semantic-adjusted pass
- STALE_DOC_CONTROL: 0/5 raw pass, 0/3 semantic-adjusted pass; `stale_doc_wrong_old_site=5/5`
- TMF_STALE_GATED: 0/5 raw pass, 0/5 semantic-adjusted pass; `stale_claim_withheld=5/5`

Interpretation: V5 successfully proves the stale handbook can lure edits to a still-existing, compiling, semantically wrong old wrapper boundary. But the base task became too underspecified: SOURCE_ONLY and TMF_STALE_GATED also failed. V5 is a useful negative/diagnostic fixture, not a clean TMF win.

## Runs not suitable as primary evidence

- V4: task prompt was too weak; early runs collapsed into edit-protocol failures. It was stopped.
- V6: attempted to require helper/source inspection while preserving stale-doc temptation, but still produced too many protocol/semantic failures across all arms. It was stopped.

## Current honest conclusion

Supported:

1. TMF freshness detects the mutation: old claim is `fresh=false` after method hash mismatch.
2. TMF gate withholds stale claims before injection: V3 and V5 both show `stale_claim_withheld=5/5`.
3. Stale unbound documentation can be harmful when its old anchor still exists: V5 shows `STALE_DOC_CONTROL stale_doc_wrong_old_site=5/5`.

Not yet supported:

- A clean, stable A/B where SOURCE_ONLY and TMF_STALE_GATED solve the task while STALE_DOC_CONTROL reliably fails semantically.

## Next fixture design

Do not keep prompt-tuning this exact B12 hook task. Build a new M07 fixture where:

1. The correct current-source solution is obvious from a local invariant, not from a prompt hint.
2. The stale old site still exists and compiles, but violates a deterministic assertion/test.
3. SOURCE_ONLY can solve by running/reading the test or local invariant.
4. STALE_DOC_CONTROL is biased toward the stale site by an unbound handbook note.
5. TMF_STALE_GATED withholds the stale claim and either gives source-only conditions or a fresh replacement claim if available.

Suggested M07 shape: two Java methods both call the same helper; the old claim says the hook belongs before caller A's helper call. Mutation moves the side effect into helper and adds a test asserting hook must fire immediately inside helper before `method.invoke`, not at caller entry. Wrong caller-site hook compiles but test/audit deterministically fails.
