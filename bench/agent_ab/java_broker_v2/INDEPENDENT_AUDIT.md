# Independent v2 audit

- Manifest/protocol hashes in each run match the frozen files.
- Smoke gate: 1/1 valid pair; both arms task/citation correct; exactly 600 source lines and two broker calls each.
- Pilot: 3/3 valid pairs; all citations counted only when they resolved to supplied source and required frozen paths were covered.
- Budget symmetry: both arms had identical candidate catalog hashes per pair, 600 source lines, two tool-loop calls, and the same answer evidence format.
- Capability isolation: TMF context appeared only in TMF_MAP selection prompts; raw broker remained stateless/tool-free; network and ambient-secret probes passed.
- Pollution defenses rejected non-candidate/duplicate selections and deterministic fill preserved budget. Unit tests cover these invariants.
- No v1 artifact was changed or rescored. No v2 prompt, golden, metric, or budget changed after results.

Conclusion: valid small pilot, no observed TMF net gain; common v1 floor was resolved by agent-loop evidence mediation. TMF adoption telemetry was zero, so recommend no expansion under this protocol.
