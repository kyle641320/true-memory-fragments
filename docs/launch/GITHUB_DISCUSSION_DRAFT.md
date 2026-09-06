# True Memory Fragments v0.1.0rc3 is available

TMF is a source-aware stale-context guard for AI coding agents.

When a coding agent remembers a call chain from an earlier session, source changes can make that memory unsafe. TMF checks the source-backed claim and blocks reuse when it is stale.

Try it from a clean checkout:

```bash
git clone https://github.com/kyle641320/true-memory-fragments.git
cd true-memory-fragments
python -m pip install --pre true-memory-fragments==0.1.0rc3
python scripts/demo_stale_gate.py
```

The demo is run from the repository root; installing the PyPI package alone does not download repository demo scripts.

Current evidence is deliberately narrow: validated source-analysis mechanics and scoped stale-context safety evidence. This is not a claim of general productivity, speed, token savings, or production readiness.

Feedback wanted:

- Could you install it without reading the source?
- Is the stale-gate result understandable?
- Does it fit any real coding-agent workflow?
- Did you encounter a false positive or false negative?

Project: https://github.com/kyle641320/true-memory-fragments
PyPI: https://pypi.org/project/true-memory-fragments/
