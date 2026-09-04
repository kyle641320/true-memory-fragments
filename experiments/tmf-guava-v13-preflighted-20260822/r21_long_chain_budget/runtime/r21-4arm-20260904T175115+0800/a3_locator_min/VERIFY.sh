#!/bin/sh
cd "/root/.openclaw/workspace/repos/guava"
echo "COMMAND: git apply --check /root/.openclaw/workspace/repos/guava/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/r21-4arm-20260904T175115+0800/a3_locator_min/patch.diff"
git apply --check "/root/.openclaw/workspace/repos/guava/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/r21-4arm-20260904T175115+0800/a3_locator_min/patch.diff"; rc=$?; echo "EXIT_CODE: $rc"; exit $rc
