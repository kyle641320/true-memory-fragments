# Human audit — middleware_hardening_v1

- Protocol/manifest were hash-frozen before implementation tests and result execution.
- Hook consumes structured tool target and prior navigation only; no prompt/golden/transcript path extraction.
- Exact repo/path/session/agent/branch/symbol/region checks are fail-closed. Branch/path changes miss rather than carrying facts.
- Fresh wire payload exposes identifiers/anchors/freshness/provenance/non-instruction only; claim fact and source text are absent. Malicious source/claim content cannot enter payload.
- Stale payload is fact-free and blocks final/edit until successful exact-path full-region evidence.
- Byte hashing deliberately reports comment/format change as one false-stale; no semantic-equivalence claim is made.
- Five frozen sequence mechanisms pass. Agent outcomes were not executed and are explicitly independent, not silently scored as mechanism success.
- Real Java fixture smoke was read-only and is illustrative (2 tasks), not statistical.

Product decision: **GO for parent independent verification**, not authorization to push. Operational integration still must call this hook after target selection and before read, and persist GateState across final/edit attempts.
