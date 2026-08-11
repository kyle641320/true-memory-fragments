# ROUND 5 — Java freshness minimal repair

## Scope

Implemented only the diagnosed freshness slice. Existing uncommitted work was preserved; no commit/push and no other worktree was touched.

## Changes

- `tmf/freshness.py`: Java relationship bindings now dispatch by `(edge_kind, binding.role)` for `calls`, `reads`, `writes`, `uses_type`, `inherits`, `overrides`, and `injects`; overload hashes are compared as a set. Unknown roles fail closed with a specific stale reason rather than causing same-file blanket invalidation.
- `tmf/derive.py`: role-tagged inherit/override/DI endpoints and explicit endpoint kinds; corrected writer endpoint kind key.
- `tmf/java_extract.py`: endpoint identity fields retained; Spring Data repository metadata now carries a typed entity source dependency (`path`, `qualname`, `node_kind`, declaration hash, FQN).
- Repository node claims receive a `repository_domain_entity` binding. Schema v2's optional `Binding.role` remains backward compatible; no schema break was introduced.
- `run_evaluation.py`: comment-only oracle now comes from independent pre/post Java source facts and declaration hashes. File blob freshness is scored separately.
- Added `tests/test_java_freshness_mutations.py` covering method control/semantic mutation/rewarm, DI endpoint removal and candidate change, and JPA entity dependency/rebind.

## Mutation results (reported without normalization)

### Focused fixtures

| Family | TP | FN | FP | Precision | Recall | Delete / ambiguity / rebind | Rewarm |
|---|---:|---:|---:|---:|---:|---|---|
| Method | 3 | 0 | 0 | 1.0 | 1.0 | comment control: only file blob; semantic body mutation invalidates method, owner class, call endpoint; unrelated file remains fresh | 0 stale after rewarm |
| DI | 1 | 0 | 0 | 1.0 | 1.0 | old edge becomes stale when bean endpoint changes; removal/recreation and second implementation exercised. Current conservative resolver behavior is retained rather than expanded | rebuilt bindings carry `{injector, bean}` roles |
| JPA | 2 | 0 | 0 | 1.0 | 1.0 | entity body mutation invalidates explicit repository entity dependency; repository generic rebinds Owner → Pet | rebound dependency points to `Pet.java:Pet` |

Counts above are fixture assertions against independently authored source expectations, not mined from TMF output.

### Real-project comment-only control

The corrected independent oracle found **0 semantic declaration changes** and one file-blob change. The E2E run reported:

- semantic TP=0, FN=0, FP=6, precision=0.0, recall=N/A
- stale after rewarm=0

This is intentionally not beautified. The remaining six pre-rewarm stale claims are not justified by changed declaration facts and remain a real-project over-invalidation finding. The minimal endpoint-role repair removed the Round-4 same-file explosion (73 FP → 6 FP), but did not eliminate all legacy/derived-claim invalidation. Conservatively, this round does not broaden Java semantics to chase those six.

## Gates

- Focused relationship suite: **66/66 passed**.
- New mutation suite: **3/3 passed**.
- Java qualifications: **46/46 passed**, 0 failed.
- Full unittest discovery: **492/492 passed** in 53.576s.
- Real E2E assertions: all declaration/relationship/negative assertions passed; retrieval MRR **0.456498**, Recall@10 **0.75**.
- `git diff --check`: passed.

Logs:

- `java-qualifications-round5.log`
- `unittest-round5.log`
- `run-round5.log`
- `report.json`

## Conservative risks / limitations

- Unknown or legacy relationship roles fail closed and are reported stale; they are never silently mapped by path/qualname.
- Repository entity dependency is declaration-hash based. Therefore any entity class declaration-hash change invalidates the repository dependency; finer JPA contract hashing is deliberately outside this minimal repair.
- DI ambiguity behavior was not expanded. The existing conservative resolver remains source-authoritative and may retain an exact direct candidate rather than infer runtime Spring ambiguity.
- Six real-project comment-control FPs remain recorded above; no claim of perfect freshness precision is made.
