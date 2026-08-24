# R20 Scenario 1 Oracle Smoke Report

## Verdict

PASS for the mechanical oracle smoke.

## Script

- `scripts/r20_scenario1_oracle.py`

## What it checks

The oracle classifies hook placement in `LocalCache.java`:

- FAIL: hook appears in `Segment.refresh(...)` initiation path after `loadAsync(...)`
- PASS: hook appears in `Segment.loadAsync(...)` completion listener path around `getAndRecordStats(...)`

## Smoke artifacts

- `runtime/r20-oracle-smoke/LocalCache_wrong_initiation.java`
- `runtime/r20-oracle-smoke/LocalCache_right_completion.java`

## Smoke result

- wrong initiation sample: rc=2, classification=`initiation_path`
- right completion sample: rc=0, classification=`completion_path`

## Interpretation

The oracle can mechanically distinguish the tunnel-vision bug shape for Scenario 1.
This is now ready to be used as the correctness oracle for SOURCE_ONLY vs TMF_PROTECT.
