#!/usr/bin/env bash
set -euo pipefail
FILE="$1"
python3 /root/.openclaw/workspace/experiments/tmf-guava-v13-preflighted-20260822/scripts/r20_scenario1_oracle.py "$FILE"
