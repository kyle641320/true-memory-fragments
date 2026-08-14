# TMF product-capability inventory — 2026-08-14

## Scope and method

Compared the tracked `true-memory-fragments` tree at `a52fdda` with the sibling reflex project, named TMF worktrees, and recent artifact families covering installer/uninstaller, OpenClaw/Claude bindings, multi-repository routing, state-root/voicewire, invalidation/calibration, observation windows, and release packages. Runtime evidence was inspected as evidence, not treated as source. No artifact, production state, global configuration, absolute deployment path, credential, or private repository data was copied.

## Executive finding

The reflex-critical product slice is now complete in the main repository: Python hard gate, localized recovery, SessionStart manifest consumer, parameterized state roots, explicit multi-repository routing, OpenClaw adapter, Claude/Codex examples, tests, and documentation are tracked under `integrations/reflex/`.

There are mature capabilities outside the repository, most notably the installer/uninstaller/doctor suite and a separate Claude Code binding package. They are substantial independent products with their own lifecycle and acceptance matrices, not inseparable reflex files. Importing them during this change would silently expand scope and risk copying deployment assumptions. They should be promoted in dedicated reviewed changes.

## Classification

### 1. Should become main-repository source

| Capability | External evidence/source | Main-tree status | Recommendation |
|---|---|---|---|
| Installer, uninstaller, doctor and managed-hook lifecycle | `tmf-installer-batch1-20260803T1933` plus `tmf-installer-multirepo-20260804`; 14-unit-test closure doctor and multi-repo acceptance evidence | Missing | Highest-priority separate promotion. Rebuild as a package-owned CLI, sanitize environment assumptions, retain transactional/dry-run/idempotence/conflict tests. Do not copy evidence logs. |
| Claude Code binding/scavenger/installer | `tmf-claude-code-binding-20260805T172107+0800/source`; dedicated adapter and tests | Main tree has a generic PreToolUse command and example, but not this lifecycle package | Promote separately after reconciling overlap with `integrations/reflex/hooks/pre_tool_use.py`; preserve only generic adapter/install logic. |
| Release packaging for integrations | RC/release archives and binding-doc bundles | Core release workflow exists; integration package inclusion is not yet explicit | Add a dedicated release-manifest/preflight change after installer ownership is decided. Ensure npm package policy (currently private) and Python script distribution are intentional. |
| Invalidation-manifest producer/calibrator | Prototype `tmf-git-freshness-calibrate.py` and post-commit contract artifacts | Consumer is tracked; producer relies on prototype APIs absent from current mainline | Port only after engine invalidation contract is made public. Do not duplicate freshness derivation in the adapter. |

### 2. Integration/deployment layer only

- Production OpenClaw registry entries, gateway enable/restart steps, repository bindings, managed post-commit hook installation, and machine-local plugin links.
- Voicewire routing and active-manifest delivery plumbing tied to an OpenClaw deployment.
- Repository-specific shell wrappers (including Zhihu calibration) and operator rollout/rollback scripts.
- Multi-repository configuration values. The generic routing model itself is already productized (`repos[]`, per-repo `stateRoot`); actual roots remain deployment parameters.

These belong in operator tooling or sanitized deployment documentation, not as checked-in machine configuration.

### 3. Experiments and evidence

- Observation-window audits, warning-wording A/B runs, Guava locator A/B, collision transcripts, smoke logs, fingerprints, tarball checksums, rollout snapshots, held-out fixture outputs, and closure timelines.
- They establish provenance and acceptance but are not runtime product source. Keep externally or summarize in reports; do not vendor raw datasets/logs.
- Locator experiments remain logically separate from execution-reflex evidence.

### 4. Runtime state and private configuration

- `.tmf` directories/symlinks, ledgers, events, manifests, consumed state, active-manifest files, caches, traces, plugin registry snapshots, repository lists, absolute paths, environment dumps, credentials, and private-repository diffs.
- Explicitly prohibited from main-repository history. State-root is a configurable contract, not a state payload.

### 5. Deprecated, superseded, or duplicate

- Superseded RC archives, old v1/v2 engine snapshots, knife migration backups, duplicate reflex-hook copies, failed compliance deliveries, old wrappers, copied production plugin backups, bytecode caches, and repeated release bundles.
- Historical worktrees (`fn-hash-fix`, `granularity`, `perf-fix`, `v2-locator`, `v2-stateroot`) contain branch-era implementations/evidence; they are not authoritative over current source. Candidate changes must be compared semantically and cherry-picked only with independent tests, never bulk-copied.

## Focus-area disposition

- **Installer/uninstaller:** mature but independently large; report-only in this change.
- **OpenClaw plugin:** generic adapter now tracked and callback-harness tested.
- **Multi-repo binding:** generic unique-route/per-repo-state-root support now tracked; production bindings excluded.
- **State-root/voicewire:** state-root parameterization tracked; voicewire runtime delivery excluded. A future public delivery protocol may be documented without deployment data.
- **Invalidation/calibration:** SessionStart consumer tracked; incompatible producer deferred pending engine API.
- **Docs/config examples:** generic README/design/migration and Claude/Codex/plugin examples tracked; operator manuals need a later sanitized consolidation.
- **Release packaging:** gap identified; defer until installer/package boundaries are agreed.

## Changes made from this audit

No additional runtime code was copied. The only components inseparable from the reflex were already included in `a52fdda`: OpenClaw routing, per-repository state roots, manifest consumption, localized warm recovery, and portable examples. Expanding into installer or Claude-binding lifecycle code would violate the requested narrow-change boundary.

## Next recommended sequence

1. Promote installer/uninstaller/doctor as a self-contained, sanitized main-tree package with its existing transactional and multi-repo acceptance matrix.
2. Consolidate Claude binding against the canonical reflex hook and eliminate duplicate freshness logic.
3. Define a public invalidation-manifest producer API in the engine, then port post-commit calibration.
4. Add integration release packaging/preflight and a sanitized operator manual.
