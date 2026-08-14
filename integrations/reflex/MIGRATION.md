# Migration manifest

Source audited in place (not modified or deleted): the sibling workspace project `tmf-reflex-hook` (audit location is intentionally not embedded as an install-time path).

| Source | Product destination | Disposition |
|---|---|---|
| `hook/tmf-reflex-hook.py` | `hooks/pre_tool_use.py` | Migrated; checkout-relative engine and local-warm paths; Store API updated |
| `hook/tmf-sessionstart-calibration.py` | `hooks/session_start.py` | Migrated as framework-neutral advisory calibration |
| `scripts/tmf-local-warm.py` | `scripts/local_warm.py` | Migrated; checkout-relative import and current Store API |
| `configs/*` | `examples/*` | Migrated; local workspace paths removed |
| `openclaw-plugin/index.ts` | `openclaw-plugin/index.ts` | Reimplemented as small generic product adapter; retained native hooks, removed deployment telemetry/lifecycle specialization |
| `openclaw-plugin/openclaw.plugin.json` | same | Rewritten with parameter-only roots and no machine defaults |
| reflex/session tests | `tests/*`, plugin `tests/harness.test.cjs` | Relevant collision, loop, calibration, and actual hook-registration coverage migrated |
| `scripts/tmf-git-freshness-calibrate.py` | not copied | Depends on later prototype-only `tmf.invalidation`/timeout APIs absent from current mainline; existing manifest consumer retained without duplicating engine invalidation logic |
| `scripts/tmf-zhihu-calibrate.sh`, git hook prototypes | not copied | Zhihu/deployment-specific absolute paths and duplicated invalidation orchestration |
| source validation snapshots | replaced by `reports/reflex-integration-2026-08-14.md` | Runtime evidence is regenerated against mainline |
| `__pycache__`, state, ledger/trace files, Guava external telemetry/A-B artifacts | not copied | Runtime or experiment-only artifacts |

The source directory is part of the broader workspace repository and had four tracked files at audit time; its historical knife commits and working files were left intact.
