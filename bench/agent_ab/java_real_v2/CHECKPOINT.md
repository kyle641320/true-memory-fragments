# Java Real-Agent A/B v2 Safety Checkpoint

Stopped 2026-08-11 after notification of a higher-priority trust-model correctness defect.

- No new agent runs may be started from this checkpoint.
- Completed evidence retained: 6 valid ordinary pairs and 2 valid freshness pairs.
- One service-overload run and one optional JHipster TMF timeout remain marked invalid and excluded.
- Repository-store pollution gate passed 3/3.
- `validate.py`, JSON parsing, Python compilation, and diff whitespace checks passed before stop.
- v1 P01-P04 artifacts remain unchanged.
- No commit or push was performed.
- No TMF engine, parser, or retrieval changes were made by this benchmark task.

Concurrent tracked modifications were observed in `tmf/derive.py` and `tmf/java_extract.py`. They were not produced, edited, or reverted by this task. Parent review must treat them as separately owned work; the v2 benchmark deliverable itself is confined to `bench/agent_ab/java_real_v2/`.
