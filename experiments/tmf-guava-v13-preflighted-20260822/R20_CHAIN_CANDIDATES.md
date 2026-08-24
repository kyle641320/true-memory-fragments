# R20 chain candidates for tunnel-vision prevention

Candidate direction chosen from Guava search:
- `com.google.common.cache.LocalCache`
- `com.google.common.cache.CacheLoader#refresh`
- `com.google.common.cache.CacheBuilder#refreshAfterWrite`

Why this direction:
- It has a real multi-file causal chain.
- It contains a boundary change that can plausibly make an A-only edit wrong.
- It is closer to correctness / behavior than helper constants.

Potential tunnel-vision trap idea:
- change refresh behavior or ordering around a cache boundary so that a stale mental model of A alone would place a new call in the wrong side of the refresh/load boundary.

Need next:
- choose exact 4-5-file chain
- freeze t0/t1/t2 tasks
- define a mechanical oracle for call ordering / refresh boundary correctness
