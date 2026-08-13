# Frozen attribution rules

- memory-caused: fresh injected claim is wrong, or audited dependency on injection leads to failure.
- stale-memory-caused: old fact appears/gets trusted after freshness mismatch.
- post-reread-agent-failure: stale gate and local reread worked, but Agent still failed.
- baseline-agent-failure: SOURCE_ONLY task failure not caused by runtime/contract.
- output-contract: transport succeeded but required JSON/tool schema remained invalid after allowed repair.
- tool/runtime: broker, timeout, sandbox, compiler, or runner failure.
- mechanism_error is an orthogonal boolean for false injection, stale leakage, or failed block/reread enforcement.
