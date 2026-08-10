# Release audit — TMF 0.1.0rc3 Java/Spring unreleased preflight

Audit date: 2026-08-10 (Asia/Shanghai)

## Verdict

- **Version blocker: RESOLVED.** The current package/public-surface version is consistently `0.1.0rc3` in `pyproject.toml`, `tmf/__init__.py`, the current-support README text, and the manual publish workflow default. The published `0.1.0rc2` release notes and changelog remain historical and unchanged.
- **Packaging and verification preflight: PASS.** The bounded Java/Spring handoff builds as an rc3 sdist and wheel; archive metadata, dependencies, contents/exclusions, installed-wheel behavior, and all requested verification baselines pass.
- **Publication: NOT AUTHORIZED.** `0.1.0rc3` is **UNRELEASED**. This worktree remains dirty, uncommitted, untagged, and not uploaded or released. Publication still requires explicit authorization.

## Protected worktree

The audit began with existing modified/untracked Java adapter work, generated Gradle/Maven outputs, root build/egg-info caches, and an untracked `uv.lock`. No existing user work, untracked fixture, or cache was deleted. Initial `reports/` status was empty; its complete file tree was archived and checksummed before verification, then restored byte-for-byte. Final `git status --porcelain=v2 -- reports` is identical to the initial empty status. `uv.lock` was not modified; its initial and final SHA256 is `24c2acfc225b5aa400f30dc83a1896d6d098d5a925d14e4a275e9ca2812d92ef`.

Version/preflight edits made by this audit are limited to:

- `pyproject.toml`: package version `0.1.0rc3`;
- `tmf/__init__.py`: runtime version `0.1.0rc3`;
- `README.md`: current support/public-surface references now say `0.1.0rc3`;
- `.github/workflows/publish-pypi.yml`: manual publish input defaults to the new, unreleased tag `v0.1.0rc3` (the workflow was not run);
- this rc3 preflight record.

`RELEASE_NOTES.md` and `CHANGELOG.md` retain their published `0.1.0rc2` history. No rc3 release note claims publication.

## Packaging and artifact audit

Backend: `setuptools.build_meta`, build requirement `setuptools>=68`. Core `dependencies = []`. The `java` extra is exactly `tree_sitter==0.25.2` plus `tree_sitter_java==0.23.5`.

The build used `uv build --no-create-gitignore --out-dir <tmp>/out <tmp>/source` against a sanitized temporary source copy. Both source and output stayed under `/tmp/tmf-rc3-build.JEOSvu`; no repository build was performed.

Temporary artifact names:

- `true_memory_fragments-0.1.0rc3.tar.gz`.
- `true_memory_fragments-0.1.0rc3-py3-none-any.whl`.

Exact byte sizes and SHA256 values are recorded in the external final preflight report after the final build. They are intentionally not embedded here: changing this sdist-included audit after hashing would change the sdist itself.

Archive inspection established:

- filenames, wheel `METADATA`, runtime package version, and distribution metadata all identify `0.1.0rc3`;
- wheel has 40 entries and contains only `tmf/` plus normal `.dist-info/` metadata;
- sdist has 1,119 entries and includes the handoff docs/manifest, implementation, current tests/verifiers/fixtures, scripts/config, and vendored offline Java wheels;
- neither archive contains `uv.lock`, VCS state, Gradle caches, Maven `target`, `.tmf`, `reports`, Python/test caches, virtualenvs, or repository `build`/`dist` output; the sdist contains only its normal build-generated `.egg-info` metadata, not the repository cache;
- wheel metadata has no unconditional `Requires-Dist`; its only requirements are the two pinned entries guarded by `extra == "java"`, and `Provides-Extra: java` is present.

## Installed-wheel smoke

Two isolated temporary Python virtual environments were used from outside the source tree with `PYTHONPATH` removed:

1. Core wheel installed with `--no-deps`: `tmf`, `tmf.cli`, and `tmf.java_extract` loaded from `site-packages`; package and distribution versions were `0.1.0rc3`; `tmf --help` passed. Warming/retrieving a Java file produced source fallback plus the documented optional tree-sitter dependency hint.
2. Wheel `[java]` installed with `--no-index --find-links vendor/wheels`: installed `tree-sitter==0.25.2` and `tree-sitter-java==0.23.5`; `java_status()` reported available with no degrade hint; warming/retrieving the same Java file produced a tree-sitter syntactic `App.run` Java method claim without a dependency-unavailable hint.

No network/runtime framework behavior, Maven publication, PyPI upload, Git tag, or enterprise runtime semantics were tested or claimed.

## Verification

```text
python3 tools/run_java_qualifications.py
# PASS: 46/46 qualifiers; 731/731 checks; failed=0; stderr empty

TMF_GRADLE=/root/.local/bin/gradle python3 tools/verify_java_gradle_integration.py
# PASS: 7/7 real Gradle clean builds; stderr empty

python3 -Werror -m unittest discover -s tests -v
# PASS: Ran 477 tests in 51.071s; OK

python3 tools/verify_java_source_only_smoke.py
# PASS: 685 exported files; 46/46 qualifiers; 731/731 checks; focused tests and compileall passed

python3 -m compileall -q tmf tests scripts tools
# PASS

git diff --check
# PASS
```

Version/reference checks found only intentional rc2 history after the update: `RELEASE_NOTES.md` and `CHANGELOG.md`. `pyproject.toml`, `tmf/__init__.py`, current README public-surface text, build filenames, and built metadata are rc3.

## Remaining limits / authorization boundary

- **Publication still requires explicit authorization.** No commit, tag, push, upload, GitHub release, PyPI publication, or publish workflow run occurred.
- Java/Spring evidence remains bounded source analysis. Compiler/JDT/SCIP classpath semantics, dynamic builds, full framework/runtime behavior, and enterprise-ready certification remain outside the verified scope.
- Only the manifest-selected seven Gradle fixtures were compiled by the real-build gate. Older historical fixtures with incomplete Gradle dependencies were not broadened or claimed.
