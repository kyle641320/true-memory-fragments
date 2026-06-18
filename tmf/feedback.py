from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .ids import now_utc
from .schema import Claim

FeedbackKind = Literal["usage", "verified", "falsified", "hunch"]


@dataclass(frozen=True)
class FeedbackResult:
    claim: Claim
    changed: bool
    note: str


def apply_feedback(claim: Claim, kind: FeedbackKind, note: str = "") -> FeedbackResult:
    """Apply v1 confidence dynamics without letting hunches become facts.

    Rules:
    - usage/read frequency never raises confidence;
    - verified evidence can raise confidence and mark evidence verified;
    - falsified lowers confidence and marks claim for re-derive;
    - hunch is recorded only as a low-authority note; it never overwrites the
      claim text, evidence, or bindings.
    """
    events = claim.body.setdefault("feedback_events", [])
    event = {"kind": kind, "note": note, "at": now_utc()}
    events.append(event)

    if kind == "usage":
        return FeedbackResult(claim, changed=False, note="usage recorded; confidence unchanged by design")

    if kind == "verified":
        claim.evidence = "verified"
        claim.confidence = max(claim.confidence, 0.75)
        claim.last_verified = now_utc()
        return FeedbackResult(claim, changed=True, note="verified evidence raised confidence")

    if kind == "falsified":
        claim.confidence = min(claim.confidence, 0.15)
        claim.body["needs_rederive"] = True
        claim.body.setdefault("notes", []).append("Falsified by feedback; re-derive from source before trusting.")
        return FeedbackResult(claim, changed=True, note="falsification lowered confidence and marked for re-derive")

    if kind == "hunch":
        claim.confidence = min(claim.confidence, 0.3)
        claim.body.setdefault("hunches", []).append({"note": note, "at": now_utc()})
        claim.body["needs_rederive"] = True
        return FeedbackResult(claim, changed=True, note="hunch recorded as non-factual; claim text unchanged")

    raise ValueError(f"unknown feedback kind: {kind}")
