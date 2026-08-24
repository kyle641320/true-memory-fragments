# R20 Tunnel Vision Prevention Plan

## Why this experiment

Previous TMF experiments mostly measured:
- stale detection
- local reread behavior
- intent-only runner gating
- token / read efficiency proxy effects

Those are useful, but they do not directly test TMF's core product claim.

TMF's core claim to test here is:
- reduce tunnel-vision bugs during code edits when a dependency boundary has changed

## What changes in this experiment

- Main metric is bug rate, not token count
- Fixture must be a meaningful Java / Spring / Guava chain with 4-5 files
- Mutation must make A-only reasoning dangerous
- Oracle must be mechanical
- TMF must be compared against a SOURCE_ONLY baseline

## Status

Spec drafted in:
- `TUNNEL_VISION_PREVENTION_SPEC.md`

Next step:
- choose a Guava chain / fixture that actually contains a tunnel-vision trap
- pre-register task list, mutation list, and oracle
- then run SOURCE_ONLY vs TMF_PROTECT

## Current judgment

The earlier TMF experiments are still valid, but they only prove mechanism-level gating.
They are not sufficient to claim the full core value of TMF.
