# External capability inventory — 2026-08-14

Bounded review: `projects/tmf-reflex-hook` plus recent installer/uninstaller,
voicewire, multi-repo, state-root and release artifacts. Archives and evidence
bundles were inventoried by names/summaries only; runtime payloads were not
mechanically imported.

| Category | Capability | Disposition |
|---|---|---|
| **应归仓（本次已归）** | Pre-tool stale hard gate, local one-file warm, SessionStart manifest consumer, generic Git calibration/hooks, OpenClaw plugin/schema/tests/docs | Productized under `integrations/reflex/`; private paths and runtime ledgers removed. |
| **应归仓（独立后续）** | Supported installer/uninstaller with idempotent dry-run, source/install manifests, rollback and multi-repo acceptance | Mature artifact lineage exists (`tmf-installer-*`, Claude binding, third-repo install/uninstall trials), but it is a larger packaging product independent of the reflex core. Promote as a reviewed `installer/` subsystem with tests rather than copying snapshots. |
| **应归仓（独立后续）** | First-class external `stateRoot` in the TMF engine/Store | OpenClaw routing accepts a state-root parameter, but current mainline `Store` remains repository-local. Prototype state-root/voicewire repairs should become an engine API and migration tests before adapters promise full external-state operation. |
| **应归仓（独立后续）** | Multi-repository binding/lifecycle isolation and collision rejection | Mature multirepo tests/evidence exist, but compliance leases/audience lifecycle are broader than freshness reflex. Port the generic config normalization, overlap/state collision checks and per-repo isolation as a separate integration release. |
| **应归仓（独立后续）** | Release packaging that includes integrations, install docs, SBOM/checksums and clean-build evidence | RC2 release policy/evidence is mature; extend packaging manifests after reflex merge rather than embedding generated release evidence here. |
| **仅部署集成** | OpenClaw gateway enable/restart, actual plugin link, Claude/Codex user config, per-repo hook installation, voicewire routing | Machine/operator policy; repository ships examples and verification commands only. |
| **仅部署集成** | Zhihu repository defaults, state directories, ledger/locks, cron/watchdog and audience/session wiring | Environment-specific orchestration; parameterize outside product code. |
| **实验证据** | Guava locator A/B, production smoke captures, compliance retry logs, third-repo trial transcripts | Valuable qualification evidence, not source product. Keep in artifact retention/release evidence. |
| **运行态私密** | `.tmf`, consumed-manifest state, lifecycle/voicewire ledgers, session identifiers, absolute home/repository paths, backups and logs | Never commit; may identify machines, repositories or live sessions. |
| **废弃重复** | Old `tmf-zhihu-calibrate.sh`, absolute-path Git hook copies, snapshot rollback commands, duplicated plugin prototypes and bytecode | Superseded by generic checked-in adapters or deployment tooling. |

## Priority recommendation

1. Merge this reflex integration now.
2. Next, productize external state-root in the engine, because reliable
   multi-repo installers and voicewire both depend on it.
3. Then upstream the tested installer/uninstaller and generic multi-repo
   isolation as one packaging milestone.
4. Finally extend the clean-build release policy to include integrations and
   linked-plugin smoke tests.
