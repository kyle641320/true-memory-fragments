# TMF Correctness Contract

These invariants are the project contract. Contributions may extend TMF only if they preserve these rules.

1. **Facts come from source.** Observed code facts must be derivable from current repository source, because source is the only authority TMF can reliably re-check.
2. **Freshness is working-tree plus all bindings.** A claim is fresh only when its current working-tree file blob and every node-specific binding still match; commit identity alone is not freshness.
3. **Confidence comes from validation, not repetition.** Usage frequency, retrieval frequency, or model self-report must not raise confidence without verification.
4. **Hunch is not fact; intent is at most attributed.** Feedback hunches and intent/why claims may be recorded as attributed context, but they are not verified code facts.
5. **Provenance is evidence, not a gate.** Provenance explains where a claim came from; it does not override source freshness or make stale memory safe.
6. **Conservative parsing: miss rather than invent.** Unknown, dynamic, or ambiguous constructs must degrade to source or unresolved state instead of guessing edges or nodes.
7. **Untrusted text is never instructions.** Source, comments, docstrings, commit messages, model output, and future PR text are data to inspect, not commands to follow.
8. **Always degrade to source; mark partial subsets.** If memory is missing, stale, unsupported, or partial, TMF must make source fallback available and document partial coverage honestly.

Breaking any invariant is a correctness regression, even if tests still pass.
