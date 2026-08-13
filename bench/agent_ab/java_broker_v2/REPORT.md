# TMF Java Agent A/B v2 pilot report

## Execution

The v2 manifest and protocol were frozen before inference. v1 was neither modified nor rescored. The one-pair smoke passed all transport, isolation, citation, candidate-catalog, and equal-source-budget gates, so the preregistered three-pair pilot ran unchanged.

## Results

All 3/3 pilot pairs were valid. Both arms used two broker calls and exactly 600 source lines per task. SOURCE_ONLY task/citation accuracy was 3/3 (1.000); TMF_MAP was 2/3 (0.667). Mean total tokens were 7,460 versus 7,387; mean latency was 16.086s versus 15.151s. TMF adoption was 0/3 by the frozen path-overlap telemetry. The paired accuracy difference (TMF_MAP minus SOURCE_ONLY) was -0.333 on this tiny pilot.

The shared v1 floor disappeared once both arms received a real selection/read loop, supporting the failure taxonomy: v1 primarily measured an inadequate static evidence dump. v2 does **not** demonstrate net TMF benefit. Because recorded TMF adoption was zero, the result is best interpreted as “the available TMF hints did not alter selected source paths,” not strong evidence that useful adopted TMF is harmful. Do not expand or tune this protocol based on these outcomes; any follow-up must separately preregister a stronger, observable TMF action interface while retaining equal source/tool budgets.

Machine-readable run and independent audit are in `results/pilot-3pair.json` and `results/pilot-3pair.audit.json`.
