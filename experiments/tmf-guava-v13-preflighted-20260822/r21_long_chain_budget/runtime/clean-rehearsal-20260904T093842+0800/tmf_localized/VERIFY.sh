#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/repos/guava
cmd='git apply --check /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/clean-rehearsal-20260904T093842+0800/tmf_localized/patch.diff'
printf '%s\n' "$cmd"
eval "$cmd"
code=$?
printf 'EXIT_CODE:%s\n' "$code"
