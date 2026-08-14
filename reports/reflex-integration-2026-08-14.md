# TMF reflex integration report — 2026-08-14

## Result

The reflex mechanism was productized under `integrations/reflex/` on top of commit `1518051` (`perf: add persistent claim inverted index`). The source prototype was audited in place and not modified. No gateway/global OpenClaw configuration was changed, and no remote push was performed.

## Migration

Added:

- framework-neutral Python PreToolUse hard gate
- SessionStart invalidation-manifest calibration
- one-file local re-warm recovery command
- native OpenClaw plugin adapter and callback-registration harness
- Claude/Codex deployment examples
- architecture, installation, safety-boundary, and migration documentation

Excluded deliberately: runtime state, bytecode caches, machine-specific paths, Zhihu-specific shell orchestration, external telemetry/Guava A/B artifacts, and prototype invalidation code incompatible with current mainline. See `integrations/reflex/MIGRATION.md` for the file-level manifest.

## Architecture and evidence boundary

TMF remains the sensory organ and freshness fact source. `integrations/reflex` is the reflex arc/execution adapter. Locator retrieval and execution reflexes are separate paths. Earlier Guava A/B v2 work exercised locator behavior only; zero locator hits are not evidence against an execution-path reflex that those experiments never invoked.

## Verification

- Full repository Python unittest: **PASS**, 571 tests in 64.360s.
- Java offline verifier: **PASS**, 13 unit tests plus minimal Java fixture and inheritance bench.
- Reflex Python tests: **PASS**, 21 tests in 5.698s.
- OpenClaw plugin callback harness: **PASS**, 3/3 Node tests.
- OpenClaw plugin build (`tsc --noEmit`): **PASS**.
- OpenClaw plugin typecheck (`tsc --noEmit`): **PASS**.
- Diff hygiene / host-path scan: **PASS** after removal of generated `__pycache__`; no install-time workspace or Zhihu path is embedded.

## E2E collision evidence

`test_E_call_symbol_collision_on_editing_caller` warms an old two-argument `build_url`, drifts the defining source to a three-argument signature, and attempts to add a two-argument call in a fresh caller file. The PreToolUse adapter returns exit 2 and names both `build_url` and `u.py`. A one-file re-warm of `u.py` makes claims fresh; retrying with the new three-argument call is allowed. Additional tests cover Read/Edit/Write/apply-patch boundaries, ambiguous-symbol fail-open behavior, existing-call isolation, no recursive shell interception, and unrelated-file locality.

Temporary fixture repositories are restored/removed by context-managed test harnesses. The product checkout is clean after the integration commit.

## Known boundaries

- Precise call-expression collision detection is currently Python-focused and relies on unique symbol resolution.
- Ambiguous/pathless actions, absent state, unsupported languages, and engine/adaptor errors fail open to avoid deadlock; therefore coverage is conservative rather than absolute.
- Shell-driven edits are not intercepted. This is also what makes local recovery non-recursive.
- SessionStart calibration consumes compatible manifests but does not duplicate an invalidation producer absent from this mainline.
- OpenClaw wiring was validated using a real registration/callback harness without installing or enabling the plugin globally.

## Release state

Local product commit: recorded after this report was staged (see repository HEAD). It is technically ready for review and push, but **must not be pushed without explicit publication confirmation**.
