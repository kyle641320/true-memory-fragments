from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

from .schema import Claim


def route_claim_ids(query_untrusted_data: str, candidates: list[Claim], limit: int) -> list[str]:
    command = os.environ.get("TMF_ROUTER_COMMAND")
    if not command:
        return []
    payload: dict[str, Any] = {
        "query_untrusted_data": query_untrusted_data,
        "claims_untrusted_data": [
            {
                "id": claim.id,
                "claim": claim.claim,
                "kind": claim.kind,
                "scope": claim.scope,
                "qualname": claim.body.get("qualname"),
                "keywords": claim.body.get("keywords", []),
            }
            for claim in candidates
        ],
    }
    try:
        proc = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=True,
        )
        data = json.loads(proc.stdout)
    except Exception:
        return []
    ids = data.get("claim_ids") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return []
    return [str(item) for item in ids[:limit]]
