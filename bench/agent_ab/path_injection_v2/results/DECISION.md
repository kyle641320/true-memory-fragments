> **Status note (2026-08-13):** Historical result for this specific protocol. Do not generalize it across delivery modes. See the unique current [Agent runtime value status](../../../../docs/AGENT_RUNTIME_VALUE_STATUS.md).

# Prior-path pre-read injection v2 decision

**STOP after smoke; do not run pilot and do not open v3.**

The frozen one-sequence smoke is audit-invalid (`valid_sequences=0/1`) despite correct pre-read triggering and a positive fresh efficiency signal. INJECT fresh revisit achieved 100% accuracy/citation with 0 reads/0 lines versus SOURCE 1 read/5 lines (573 versus 720 total tokens), and unrelated revisit also directly adopted fresh memory. Unknown conservatively received the prior-path claim, did not adopt it, and read the correct unknown file (noise recorded). Mutation produced a stale path-only pointer and localized all reads to one distinct path with zero stale-trust errors, but INJECT and TOOL failed answer/citation validity in semantic mutation; TOOL also failed unrelated mutation. Therefore the preregistered all-arm smoke validity gate failed and the three-sequence pilot was not executed.

Audit implementation treats capabilities per original/repair call and reports distinct source paths separately from read calls. v1 remains untouched.
