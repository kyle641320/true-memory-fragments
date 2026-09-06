# Version-pinned test snapshots — 2026-09-06

This verification records two separate source snapshots, not interchangeable release results.

- master snapshot: `bba964581aec83c7f41f13e202bc07ed100b9ee9`
- v0.1.0rc3: `be85e04670ece701838f5206beb417e2efbd6c64`

Tests ran in separate clean checkouts and virtual environments, using Python 3.12.3, tree-sitter 0.25.2 and tree-sitter-java 0.23.5. These are source-checkout tests, not standalone wheel verification.

## Commands and results

Commands, in each checkout with its own virtual environment activated:

```sh
python -m unittest discover -s tests -q
python -Werror -m unittest discover -s tests -v
```

| Snapshot | Command | Ran | Passed | Failed | Skipped | Exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| rc3 | ordinary | 617 | 612 | 0 | 5 | 0 |
| rc3 | -Werror | 617 | 612 | 0 | 5 | 0 |
| master snapshot | ordinary | 617 | 610 | 1 | 6 | 1 |
| master snapshot | -Werror | 617 | 611 | 0 | 6 | 0 |

Skipped tests are included in Ran, not in Passed. The later successful run does not erase the earlier failure.

## Failure and skip observations

The master ordinary run failed `test_fresh_cross_file_edge_does_not_force_permanent_rederive` in `test_cross_file_edges`: the before/after comparison showed a one-second difference in `last_verified`. The test already excluded `generated_at` as refresh metadata but omitted `last_verified`, which is also set by `now_utc()` on every derivation. A boundary-forced reproduction confirmed that this metadata-only difference appears when the two refreshes cross a UTC-second boundary. The regression assertion now excludes both refresh metadata fields while continuing to compare every source-backed field.

Five skip reasons shared by both verbose runs: no publishes_to edges; no overrides edges; no call edges in each of two routing checks; no inferred semantic contracts/model command. The master run additionally skipped a Java binding test because commit `5896859` removed its machine-local Guava fallback, while `fixtures/guava` is not tracked. Thus a clean checkout necessarily skipped that regression. The test now uses the tracked `fixtures/java-kafka-heldout/.../Messaging.java` corpus, which contains ordinary Java methods sufficient to verify binding line, role, and hash metadata without an external repository.

## Historical counts and separate units

The 478-test count in RELEASE_AUDIT.md and earlier release notes is a historical audit baseline, not the current test count. This run does not substantiate a 618-test claim.

The Java qualification baseline of 46 qualifiers / 731 checks is separately reported in historical release evidence. That aggregate was not rerun for this verification; it must not be added to or equated with unittest counts. Agent experiment runs are a third, distinct unit and were not rerun. No paid model experiments were performed.

## Committed raw test logs

- [rc3 ordinary](2026-09-06/rc3-unittest.log)
- [rc3 warning-strict](2026-09-06/rc3-unittest-werror.log)
- [rc3 revision](2026-09-06/rc3-revision.log)
- [master ordinary](2026-09-06/master-unittest.log)
- [master warning-strict](2026-09-06/master-unittest-werror.log)
- [master revision](2026-09-06/master-revision.log)

Release rc3 retains its historical notes and links this dated rc3 re-verification. README links the master snapshot without presenting it as an unconditional all-green baseline. A subsequent fix and post-fix verification are documented in the repository history; the snapshot table above remains an immutable record of the original runs.
