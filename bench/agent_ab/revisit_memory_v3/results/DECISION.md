> **Status note (2026-08-13):** Historical result for this specific protocol. Do not generalize it across delivery modes. See the unique current [Agent runtime value status](../../../../docs/AGENT_RUNTIME_VALUE_STATUS.md).

# v3 pilot decision

Frozen smoke passed (1/1 valid), so the preregistered pilot ran. Pilot: **2/3 valid sequences**. All 24 outputs were structurally schema-valid; format repair was never invoked (0/24, 0%; zero repair tokens/latency). S12 CONTROL unknown-region correctly answered `exists=false` but cited class line 2 rather than frozen method-evidence line 3. This was not a format failure and was not eligible for semantic repair.

Typed correctness/citation was 1.0 except CONTROL unknown-region at 2/3. TMF fresh revisit read 0 lines/bytes versus CONTROL 33 lines/842 bytes, with 3/3 hits/adoptions. Mutation revisit read 18 lines/320 bytes versus CONTROL 33 lines/841 bytes; all three stale claims were blocked and none adopted. Stale errors: 0; stale detection and localized reread precision/recall: 1.0. Machine audit reports tokens/latency by phase and arm.

Verdict: strict output formatting is operational and this broker is suitable for the protocol's format contract; overall parity is not fully supported due to one CONTROL citation coverage miss. No v4; frozen inputs remain unchanged.
