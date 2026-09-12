# Disposable Git fixture cleanup follow-up

Historical failure: https://github.com/kyle641320/true-memory-fragments/actions/runs/34695343890

The Python 3.12 job (Git 2.55.0) raised OSError 39 while removing a temporary .git directory in PrimaryTests.claims; it was not an assertion failure. Local Git 2.43.0 tracing confirms each fixture commit starts git maintenance run --auto. Git documents that automatic maintenance may detach (https://git-scm.com/docs/git-config#Documentation/git-config.txt-maintenanceautoDetach). This is a concrete lifetime hazard, but the historical runner has no process trace proving its exact writer; do not claim an exact reproduction of that race.

Change: disable automatic maintenance and automatic GC on this disposable fixture's commit only. Do not change production Git settings, ignore cleanup errors, add sleeps or retry cleanup. All original semantic assertions remain.

Regression: real Git TRACE2 confirms an actual commit and a valid derived claim, with no maintenance/GC child launched. The new test fails on the old fixture and passes with the fix. This proves removal of the identified background-maintenance path, not that every possible external writer is eliminated.

Local verification: four focused tests pass; full Python 3.12 -Werror suite runs 621 tests successfully with one optional skip. Evidence is retained in the task artifact directory; no historical failed run was relabelled.
