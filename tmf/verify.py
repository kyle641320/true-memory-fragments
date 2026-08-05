from __future__ import annotations

from .schema import Claim


def verify_observed_claim(claim: Claim, source_text: str) -> Claim:
    """Conservative second-pass verification for v1 heuristic claims.

    This is not semantic proof. It only verifies that observed identifiers stored
    in the claim body are present in the bound source. Unsupported claims are
    downgraded, not silently promoted.
    """
    keywords = [str(k) for k in claim.body.get("keywords", [])]
    supported = all(k in source_text for k in keywords[:8])
    claim.body["verification"] = {
        "method": "v1-observed-keyword-check",
        "supported": supported,
    }
    if supported:
        claim.evidence = "observed"
        claim.confidence = min(claim.confidence, 0.45)
    else:
        claim.evidence = "inferred"
        claim.confidence = min(claim.confidence, 0.2)
        claim.body.setdefault("notes", []).append("Second-pass check could not support all observed identifiers; treat as low-confidence.")
    return claim
