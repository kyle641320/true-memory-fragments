# Java Real Stale A/B v3 Smoke Protocol

Frozen before execution on 2026-09-02. This is a small discriminating real-repo smoke, not a broad causal claim.

## Goal

Test whether repo-local TMF freshness helps an agent avoid stale context on a real Java repository mutation where an old event contract note is plausible but obsolete.

## Repository

Petclinic modulith pinned at `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`, copied into `/root/.openclaw/workspace/experiments/tmf-java-real-v3/petclinic-event-type`, warmed with a repo-local `.tmf` store before mutation, then mutated by renaming the visit booking event contract from `VisitBooked` to `VisitScheduled` across producer and consumers.

## Arms

- `SOURCE_ONLY`: receives the same old note and current repo path, but is forbidden from TMF. It may inspect source under the same budget.
- `TMF_MAP`: receives the same old note and current repo path, and must first run repo-local TMF freshness over claims mentioning `VisitBooked`; stale output must be treated only as a locator before minimal source reread.

## Metrics

Correctness requires: current event type `VisitScheduled`, direct producer `VisitScheduler.bookVisit`, direct listener `VetEventListener.on(VisitScheduled)`, direct assignment consumer `VetRoster.assignVet(VisitScheduled)`, and explicit old-note blocked/not trusted. Citation correctness requires current source line citations for producer/listener/consumer plus event record.

Transport failures are excluded only if CLI exit is non-zero or no agent payload is produced. No golden facts are included in prompts.
