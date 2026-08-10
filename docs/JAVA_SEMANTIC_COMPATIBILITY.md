# Java semantic facts compatibility

| Contract/provider | Status | Trust/freshness |
|---|---|---|
| `tmf.java-semantic-facts.v1` fixture/offline verifier | supported | external attributed overlay; exact SHA-256; deterministic fail-closed |
| Eclipse JDT adapter | contract-compatible target, E2E unavailable here | must supply all v1 provenance; never inferred |
| `javac` adapter | contract-compatible target, E2E unavailable here | same |
| SCIP Java adapter | contract-compatible target, E2E unavailable here | same |
| no provider / disabled | supported default | syntax-only; explicit `default_off` degradation |

Documents are immutable snapshots per source path. Re-ingestion replaces the path's semantic overlay through normal TMF path reconciliation; mutation/hash mismatch yields no replacement facts and deletion of source/provider facts removes overlays on warm reconciliation. Conflicting providers fail closed rather than voting or merging confidence.
