# Human audit — agent_middleware_value_v1

Real `gpt-5.6-sol` controlled-tool Agent smoke: **2/2 valid paired sequences**. Both arms succeeded on both tasks. TMF adoption was **0/2**, so the frozen smoke stop gate fired and the 10-pair full run was not executed. No tuning followed.

| Task | Type | SOURCE | TMF | Adoption | Source reads S/T |
|---|---|---:|---:|---:|---:|
| A01 | understanding | 1 | 1 | 0 | 1/1 |
| A03 | local_edit | 1 | 1 | 0 | 1/1 |

There were no attributed Agent, stale-memory, middleware, contract, or runtime errors. The negative outcome is specifically failure to demonstrate adoption/cost value, not a mechanism failure. Small N; no statistical claim.

Aggregate telemetry: `{"SOURCE_ONLY": {"adoptions": 0, "completion_tokens": 168, "injection_tokens": 0, "n": 2, "prompt_tokens": 1406, "source_bytes": 173, "source_reads": 2, "success_rate": 1.0, "successes": 2, "tool_calls": 8, "wall_seconds": 25.679165840148926}, "TMF_MIDDLEWARE": {"adoptions": 0, "completion_tokens": 181, "injection_tokens": 236, "n": 2, "prompt_tokens": 1874, "source_bytes": 173, "source_reads": 2, "success_rate": 1.0, "successes": 2, "tool_calls": 8, "wall_seconds": 33.978278160095215}}`
