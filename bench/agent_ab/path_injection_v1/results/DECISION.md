# path_injection_v1 decision

**STOP after smoke; pilot not run; no v2 opened.** The frozen smoke produced 1/1 sequence and all 15 arm-phase answers were accurate with valid citations, but the preregistered validity audit failed.

Failures: (1) `tool_missing`: the audit requires TMF_TOOL capability on every action transcript entry, while the schema-only repair entry has no action capability field; (2) semantic-stale localized reread precision/recall were 0 because the agent reread the touched file after the stale pointer, yielding two reads of one path (`source_files` telemetry counts reads, not distinct files). These are harness/audit validity defects, not grounds for post-hoc repair or regrading.

Directional smoke only: TMF_INJECT_ONLY fresh and unrelated revisits each had 1 hit/1 adoption, 105 injection tokens, 100% accuracy/citation; unknown region missed; semantic mutation emitted pointer-only (59 tokens), no stale adoption/error. TMF_TOOL made one autonomous lookup (semantic mutation), with zero fresh adoption. Injection did not reduce source reading in this implementation because the hook fires after first code touch; accuracy tied at 100%. Product gate is therefore not established.
