# Independent smoke audit

The frozen hashes verify, broker preflight is stateless and pinned to `gpt-5.6-sol`, store allowlist contains only claim/anchor/freshness/provenance fields, CONTROL has no memory, unknown identity misses, and the mutated claim is blocked and reread locally. Pre/post fingerprints differ.

**STOP GATE: FAIL.** Both arms returned semantically correct first-visit and unknown answers, but the preregistered lexical golden required `80` in first visit (the task did not ask for an example subtotal) and literal `not available` for unknown (answers said `unavailable`). Because scoring was frozen, these are not regraded. `valid_sequences=0`; therefore the 3-sequence pilot was not run.

Direction-only, non-valid smoke observations: fresh revisit source lines 17→0, bytes 513→0, tokens 355→267; mutation revisit source lines 17→7, bytes 513→165, tokens 402→220. Stale trust errors: 0. Stale detection and localized reread precision/recall: 1.0 each. These observations do not pass the product gate and do not prove the hypothesis.
