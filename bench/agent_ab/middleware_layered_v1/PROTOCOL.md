# middleware_layered_v1 (preregistered)

This held-out protocol evaluates TMF as a **freshness-gated context middleware**, separately from downstream model outcome. Files in prior path-injection/revisit experiments are out of scope and immutable.

Each arm/sequence uses independent sessions. `first_visit` must read source and creates claims only from the real source-tool trace; memory is never handwritten. On later sessions the middleware runs before the first model action. A current source hash match injects at most Top-3 bounded fresh claims. A mismatch supplies only a stale pointer; old claim text is withheld and final is rejected until the affected path has been successfully read. Unknown regions miss. An unrelated mutation preserves the affected file hash and freshness. Source is authoritative. Prompt, transcript, answer, and golden data are forbidden middleware inputs.

Primary mechanism gates: stale precision/recall 1.0, false inject 0, stale trust errors 0, unknown false hits 0, localized semantic reread 1.0, fresh claim accuracy 1.0, injection before first read, provenance/session independence, no leakage, and budget compliance. These gates are independent of final answer correctness. Smoke L41 must pass before the five-sequence pilot.

Secondary outcome reports task/citation accuracy; source lines/bytes/read calls; prompt/completion/injection/total tokens; latency. Machine attribution priority: output-contract failure; memory-caused (wrong fresh claim used or stale fact trusted); post-reread model failure (valid affected-path read then wrong); baseline model failure (SOURCE_ONLY wrong); otherwise none. Human audit fields record reviewer, agreement, notes.

Value gate is directional reduction in fresh-revisit source reads/lines or total tokens; mutation answer perfection is not required. One symmetric schema-only repair is allowed per session and cannot add source facts.
