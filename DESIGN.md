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

## Window 1 conservative maintenance rules

- Python qualnames are scope-qualified for nested functions and nested classes. Identity is based on path plus qualname; nested class names must not collapse to their short name.
- Mechanical contracts are summaries of observed interface facts only. Slot confidence is capped at `<=0.6`; semantic contract candidates, when enabled in later workflows, remain attributed/inferred after sanitizer checks.
- Rename persistence is deliberately narrow: migrate identity only for exact blob-preserving one-old/one-new renames. Do not migrate rename+edit or ambiguous same-blob copies; delete stale old-path tombstones and rederive current paths.
- Edge claims are source-bound to all endpoint bindings. Any rename migration must remap endpoint claim ids, update binding paths, and keep freshness as an AND over all bindings.
- FIELD_TEST harnesses in this window are plan-only. They may produce local command templates and metrics-to-capture lists, but must not start external reconnaissance.

## Window 2 continuation Java design notes

- Java Spring routes remain syntactic and literal-only. Dynamic annotation arguments, constants, SpEL, wildcard imports, and framework inference are data, not authority; no route node is fabricated without literal path evidence.
- Java `uses_type` is intentionally conservative: same-file definitions and explicit imports are the only resolved targets. JDK/external/wildcard/unknown/ambiguous types are represented as unresolved, and TMF never creates external type nodes merely to satisfy a relation.
- Java semantic contracts use the same sanitizer discipline as Python. Mechanical interface facts are observed; model-derived semantic slots are inferred/attributed, capped at 0.6, and rejected when contradicted by params/throws/writes/void-return mechanical evidence. Contract freshness binds to the full method body hash.

## Window 3/4 trust and robustness design notes

### Semantic-resolved tier / SCIP status

`semantic-resolved` is a separate evidence tier for facts resolved by an external semantic indexer such as SCIP/LSP. It is not direct syntax (`observed`) and not framework convention (`attributed`). Accepted semantic overlay claims are capped at `<=0.6`, tagged with `tier/extraction_tier = semantic-resolved`, and may not override deterministic syntactic or observed claim ids.

Freshness still binds to source. If source bodies change, semantic-resolved claims become stale and must be refreshed or degraded back to syntax/source. The implemented path is an interface skeleton with three-state behavior: backend unavailable -> degrade without crash; backend available -> queue background refresh; accepted claims -> sanitized semantic overlay. True `scip-python` end-to-end consumption is not verified in this environment and must be checked separately by Kyle.

### Framework-inferred edges

Spring DI `injects` and Kafka `publishes_to`/`subscribes_to` are framework/annotation inferences, not syntax-direct proofs. They are `attributed`, confidence `<=0.6`, and route through explicit nodes where appropriate (Kafka topic nodes) rather than inventing direct producer-consumer edges. Ambiguous or dynamic cases are unresolved with reasons.

### Foreign `.tmf` trust boundary

A cloned repository may contain a malicious `.tmf/` cache. TMF treats pre-existing caches without the local identity as foreign data. Foreign claims are surfaced as `unverified_foreign`, effective confidence is zeroed in explain/thin views, and retrieval re-derives from source instead of trusting cached confidence. A local re-derive is the only upgrade path to `locally_derived`; source remains authority.

### Concurrency boundary

TMF uses a repository-local file lock for writer serialization plus atomic replace for claim/metadata files. This prevents corrupt half-writes during concurrent warm/read-through writers. It is not a transactional database and does not promise snapshot isolation for arbitrary concurrent readers; users needing stronger guarantees should serialize agent warm/write phases.

### Scale and retrieval measurement boundaries

Scale and retrieval reports are diagnostic measurements. Window 4 measured 200/1000-function synthetic repos and a 20-query self-retrieval set. The observed retrieval recall@10 was 0.50, so natural-language relevance remains a known weak area. These numbers are not marketing claims and should be rerun in Kyle's private field environment.

### Default-view redaction for unverified foreign claims

`unverified_foreign` is treated as untrusted input, including the natural-language claim text itself. Default explain/thin views therefore redact the assertion text and show a neutral placeholder. This prevents downstream consumers that read only `claim` + `fresh` from accidentally absorbing attacker-supplied assertions before source re-derivation. Full explain may expose the original text only as `raw_foreign_claim_untrusted_data`, explicitly labeled for audit rather than reasoning.
