# R21 clean rehearsal TMF_LOCALIZED_REFRESH

You are running one controlled benchmark arm.

Read:
- `TASK_BASE.md`
- `PROTOCOL.md`
- `../../tasks/R21_TMF_LOCALIZED_REFRESH_LOCATOR.json`

Use the localized refresh locator's fresh boundary anchors to decide hook placement.

You may inspect the exact target source file only as needed to build a valid patch:
`/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java`

Do not read sibling `source_only`. Do not inspect unrelated source. Do not modify the source tree directly.

Produce exactly the required protocol files:
- `patch.diff`
- `NOTE.md`
- `VERIFY.sh`
- `VERIFY.log`
