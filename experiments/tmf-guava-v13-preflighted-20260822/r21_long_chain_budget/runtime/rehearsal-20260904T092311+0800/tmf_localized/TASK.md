# R21 rehearsal TMF_LOCALIZED_REFRESH

You are running one controlled benchmark arm.

Read `TASK_BASE.md` and the TMF localized refresh locator at:
`../../tasks/R21_TMF_LOCALIZED_REFRESH_LOCATOR.json`

The locator contains a stale claim plus fresh localized boundary anchors. Use the fresh boundary anchors to decide hook placement. Produce exactly:
- `patch.diff` — unified diff for `guava/src/com/google/common/cache/LocalCache.java`
- `NOTE.md` — short explanation and METRICS_JSON line

Do not read the SOURCE_ONLY directory. Do not inspect unrelated source. Do not modify the source tree directly.
