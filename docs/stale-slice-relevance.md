# Java stale-slice relevance: bounded improvement

`tmf_stale_slice` still withholds stale claims and requires their bound source.
This change narrows its additional Java reading suggestions, not freshness
hashes or dependency validity.

## Selection

Current declarations are located by qualified name, including moved declarations.
A deleted or unresolved Java symbol does not seed terms from its previous line
range or the whole file. Supplemental method names must match explicit question
terms or call-shaped identifiers in the current bound source. Container-name
matches alone do not qualify. Specific call names receive priority without a
same-file bonus, and already-required stale declarations do not consume the
supplement budget.

## Real-source replay

A temporary index was built from Guava `Hashing.java` and `HashCode.java` at
`94f39958baf7ad51ddf9c70e406ed6b188194daa`, then source was replaced with
`a8adf77c0eddafde7e3646c6fa0083d72a6b6f64`. Baseline `b02b219` and this candidate
were compared with no question and the default four-read budget.

For both `Hashing.combineOrdered` and `Hashing.combineUnordered`, the mandatory
changed method and the stale-binding report are unchanged. The other reads are:

| Before | After |
| --- | --- |
| `Hashing.LinearCongruentialGenerator.nextState` | `HashCode.getBytesInternal` |
| `Hashing.Crc32CSupplier.pickFunction` | `HashCode.fromBytesNoCopy` |
| `Hashing.checkPositiveAndMakeMultipleOf32` | `HashCode.BytesHashCode.getBytesInternal` |

The after-set concerns input-array access and result-array ownership in the real
upstream change. This replays the planner on two exported source files; it is
not a new full-worktree agent experiment, a compiler-resolved dependency graph,
or evidence of lower agent token/time cost.

## Validation and remaining limits

The added regression fails on the baseline and passes on the candidate. It covers
moved and deleted declarations, exclusion of unrelated file/header identifiers,
and preservation of a sibling callee. Existing explicit-task and side-effect
checks pass. Initial slice suite: 619 run, 618 passed, 1 optional skip. Held-out: pass.

The original local self-validation did not produce a final report within a
ten-minute budget and was interrupted; that run is not counted as passed.
Subsequent CI at commit `77842c7` passed self-validation on Python 3.10–3.12. The captured stack is in Java
inheritance resolution / graph-coverage file enumeration, outside modified
modules. The interrupted run alone is not proof that the patch caused (or could not
contribute to) the runtime cost. Current-head CI must be checked separately.

Suggestions remain heuristic: call-shaped text in comments/strings and methods
with the same name can match without receiver/type resolution. Sibling scanning
is bounded and can omit distant declarations. Stale line numbers are still
historical anchors; consumers should resolve `read_symbol` against current
source. This is neither complete dependency coverage nor a mandatory write gate.

## Validation enumeration follow-up

The Java coverage audit used a fresh project fingerprint for each resolver call.
It now reuses the existing lazy Java snapshot only within that audit's local
`GitRepo` instance, over an unchanged validation fixture. A new audit creates a
new view: added and deleted Java files are covered by regression tests. Runtime
freshness/cache policy and validation scoring/coverage targets are unchanged.

A mixed-language fixture with resolved and unresolved inheritance has identical
before/after coverage statistics, with project enumeration reduced from eight
to two calls. An additional nine-Java-file test fails on the old 20 enumerations
and passes with a constant bound; subsequent addition/deletion changes remain
visible. The updated full suite runs 620 tests: 619 passed, one optional skip.
See the PR's current-head checks for final self-validation and release status;
older successful checks must not be substituted for the current head.
