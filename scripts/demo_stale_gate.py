#!/usr/bin/env python3
"""Deterministic, offline demonstration of TMF stale-claim gating.

Run from a checkout with: python scripts/demo_stale_gate.py
No model, network, Java parser, or pre-existing .tmf store is required.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow running directly from a source checkout.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tmf.retrieve import refresh_path, retrieve_path  # noqa: E402


ORIGINAL = """def charge(amount):\n    return amount * 2\n\n\ndef submit(order):\n    return charge(order[\"total\"])\n"""
UPDATED = """def charge(amount):\n    # The implementation changed after the original claim was derived.\n    return amount * 3\n\n\ndef submit(order):\n    return charge(order[\"total\"])\n"""


def run(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tmf-stale-demo-") as directory:
        repo = Path(directory)
        run("init", cwd=repo)
        run("config", "user.email", "tmf-demo@example.com", cwd=repo)
        run("config", "user.name", "TMF demo", cwd=repo)
        source = repo / "payments.py"
        source.write_text(ORIGINAL, encoding="utf-8")
        run("add", "payments.py", cwd=repo)
        run("commit", "-m", "initial source", cwd=repo)

        first = refresh_path(repo, "payments.py")
        claim_count = len(first.claims)
        source.write_text(UPDATED, encoding="utf-8")
        second = retrieve_path(repo, "payments.py")

        stale = any("stale" in gap for gap in (second.gaps or []))
        fallback = "payments.py" in second.source_fallback
        blocked = len(second.claims) < claim_count
        result = {
            "demo": "tmf stale claim gating",
            "initial_claims": claim_count,
            "claims_after_source_change": len(second.claims),
            "stale_claim_omitted": blocked,
            "source_fallback_provided": fallback,
            "reread_required": stale,
            "gaps": second.gaps or [],
        }
        print(json.dumps(result, indent=2))
        if not (claim_count > 0 and blocked and fallback and stale):
            print("DEMO FAILED", file=sys.stderr)
            return 1
        print("STALE CLAIM BLOCKED: PASS")
        print("SOURCE FALLBACK PROVIDED: PASS")
        print("REREAD REQUIRED: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
