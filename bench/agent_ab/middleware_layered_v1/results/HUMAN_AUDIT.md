# Human audit — smoke stop gate

- Reviewer: automated trial subagent, manual trace inspection
- Frozen protocol hash: recorded in `FROZEN.sha256`
- Smoke sequence: L41; independent sessions verified
- Mechanism verdict: **FAIL / STOP**
- Agreement with machine attribution: yes for mechanism counters; semantic Agent output failure is correctly downstream and does not alter stale mechanism success.

## Trace findings

Fresh revisit used a hash-bound claim from the prior independent first-visit source-tool trace, injected before any read, and eliminated the repeat read. Semantic mutation emitted only a stale pointer, withheld the old fact, and the affected source path was successfully reread before final. The model then produced an invalid final after reread; this is an output-contract/downstream failure, not a TMF stale-detection failure. Unrelated mutation remained fresh.

The preregistered unknown-region gate failed: middleware selection was driven only by the previous navigation path, so it injected the still-fresh OrbitLedger claim into the QuietRelay task. Machine metrics correctly recorded `false_inject=1` and `unknown_false_hits=1`. No leakage, ordering, token-cap, stale-trust, or session-independence errors were observed.

Per frozen STOP_GATES, the five-sequence pilot was not run and no rules were tuned after results. This smoke therefore does not support promotion of this implementation as the validated freshness-gated context middleware, though it supports the stale-blocking mechanism in the observed semantic-mutation case.
