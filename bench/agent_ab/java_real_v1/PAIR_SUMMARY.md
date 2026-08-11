# Native-agent paired summary after Round 13

Only real native-agent runs are included. The earlier deterministic proxy rows in `REPORT.json` are excluded, as is the first P01 run that hit the wrong Zhihu store.

| task | arm | correct | source files | source lines | tool calls |
|---|---|---:|---:|---:|---:|
| P01 location/path | SOURCE_ONLY | yes | 8 | 396 | 12 |
| P01 location/path | TMF_MAP | yes | 8 | 378 | 5 |
| P02 impact analysis | SOURCE_ONLY | yes | 6 | 316 | 9 |
| P02 impact analysis | TMF_MAP | yes | 6 | 332 | 5 |
| P03 smallest validation change | SOURCE_ONLY | yes | 5 | 342 | 8 |
| P03 smallest validation change | TMF_MAP | yes | 3 | 296 | 3 |

## P01–P03 aggregate

- Correctness: 3/3 in both arms.
- Source lines: SOURCE_ONLY 1,054; TMF_MAP 1,006 — 48 fewer, about 4.6% reduction.
- Tool calls: SOURCE_ONLY 29; TMF_MAP 13 — 16 fewer, about 55.2% reduction.
- Source files: SOURCE_ONLY 19; TMF_MAP 17 — 2 fewer, about 10.5% reduction.

These are three paired pilot tasks, not a statistical conclusion. Line counts are taken from each agent's declared read ranges and are therefore approximate; correctness was checked against source evidence.

## P04 stale-memory pair

P04 is analyzed separately in `P04_REAL.md/json` because it tests stale-memory blocking rather than ordinary map retrieval.

- Both arms correctly rejected the old ordering statement.
- TMF freshness explicitly returned `fresh=false`, reason `java_hash mismatch`, before source reread.
- SOURCE_ONLY_WITH_STALE_MEMORY read 18 source lines; TMF_FRESHNESS reread 7 lines.
- Both used 2 tool calls.
- The single pair demonstrates a working freshness guard and narrower reread in this mutation, not a general causal estimate.

## Invalid/excluded data

- Deterministic proxy runs in `REPORT.json`: harness preflight only.
- Initial P01 TMF_MAP using the globally registered Zhihu store: wrong-repo routing, invalid.
- Failed ACP/acpx startups: no agent ran, excluded.
