# Show HN: True Memory Fragments — stale-context protection for AI coding agents

AI coding agents can remember a call chain from an earlier session and continue editing after the source has changed. True Memory Fragments (TMF) is a small, source-aware layer that checks whether a remembered claim is still fresh before it is reused.

The narrow claim is intentional: TMF can identify stale source-backed claims and require re-derivation. This project does **not** yet claim general productivity gains, lower token usage, faster agents, or production readiness.

## 30-second demo

```bash
git clone https://github.com/kyle641320/true-memory-fragments.git
cd true-memory-fragments
python -m pip install --pre true-memory-fragments==0.1.0rc3
python scripts/demo_stale_gate.py
```

Run the demo from the repository root; the PyPI install does not include repository demo scripts.

The demo changes a source function after a claim has been derived. The stale claim is blocked, the source fallback is shown, and an explicit reread is required.

## What is included

- Python source-aware freshness and stale-gate checks
- CLI support for warming, retrieval, explanation, and status inspection
- Optional Java parsing support
- An offline demo and a scoped Guava M10 case study

## Evidence and limits

The repository has green CI and release preflight checks. The strongest runtime evidence is scoped to stale-context safety in a Guava M10 pre-read experiment. The project has not established broad agent productivity or bug-prevention effects.

PyPI: https://pypi.org/project/true-memory-fragments/
GitHub: https://github.com/kyle641320/true-memory-fragments

I am an independent developer. I would especially value reports of confusing installation steps, false freshness decisions, or real coding-agent integrations.
