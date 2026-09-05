# Open-source minimum checklist (2026-09-05)

This checklist is the minimum bar for publishing TMF and promoting it to external developers. It is intentionally smaller than the research validation backlog.

## P0 — release blockers

- [ ] Clean-environment install smoke passes on Python 3.10–3.12.
- [ ] `tmf --help` and the documented `warm` / `retrieve` / `explain` commands work from a fresh checkout or wheel. **Verified locally with an isolated venv on 2026-09-05.**
- [ ] A self-contained stale-behavior demo is runnable in 3–5 minutes: derive a claim, mutate its bound source, retrieve it, and visibly show stale omission, source fallback, and reread guidance. **Verified locally with `python3 scripts/demo_stale_gate.py` on 2026-09-05.**
- [ ] README does not imply that `retrieve` automatically re-derives claims. Refresh is explicit through `refresh_path` / `warm`.
- [ ] The README states the evidence boundary on the first screen: mechanics validated; stale-boundary safety is scoped-positive; productivity, token savings, general bug reduction, adoption, and ROI are unproven.
- [ ] Published code, demo fixture, and result paths are separated from dirty local benchmark artifacts.
- [ ] License, supported Python versions, optional Java dependency, and known limitations are accurate.

## P1 — before active promotion

- [ ] Record a short terminal GIF or asciinema capture of the stale demo.
- [ ] Add a copy-paste repository-local demo script with deterministic output and a clean temporary directory.
- [ ] Add GitHub repository description and topics using problem vocabulary: `AI coding agents`, `stale context`, `source-aware code memory`, `code graph`, `developer tools`.
- [ ] Add one technical case study linking to the Guava M10 report, explicitly calling it scoped evidence rather than a productivity benchmark.
- [ ] Add issue templates for reproduction, integration, and false-positive/stale-gate reports.
- [ ] Test the OpenClaw / Claude Code integration separately from the core library; do not imply every integration is production-ready.

## P2 — validation backlog, not an open-source blocker

- [ ] Repair one behavior-level M12 or M14 oracle with fake dependency and runtime assertions.
- [ ] Execute a valid Phase A → source mutation → Phase B same-agent experiment.
- [ ] Replicate stale-boundary protection across at least three scenarios, languages, or repositories.
- [ ] Measure adoption, stale trust errors, reread bytes, runtime overhead, and token cost separately.

## SEO judgment

Current keywords are directionally reasonable, but keywords alone will not create organic stars. The main discoverability blockers are the missing self-contained demo, unclear first-run path, and lack of external case studies or distribution. Keep the wording problem-led and evidence-limited; do not add stronger claims merely to target search volume.

## Release recommendation

Open-source release is appropriate after P0. Active promotion should wait until the deterministic demo, clean install smoke, and first external-readable case study exist. The project should be presented as an experimental safety/navigation tool, not production middleware or a proven productivity layer.
