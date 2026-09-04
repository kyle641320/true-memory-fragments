#!/usr/bin/env bash
set -u
REPO="/root/.openclaw/workspace/repos/guava"
PATCH_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/patch.diff"
CMD="git apply --check ${PATCH_FILE}"
echo "cd ${REPO}"
echo "${CMD}"
cd "${REPO}" || exit 99
git apply --check "${PATCH_FILE}"
EC=$?
echo "exit code: ${EC}"
exit "${EC}"
