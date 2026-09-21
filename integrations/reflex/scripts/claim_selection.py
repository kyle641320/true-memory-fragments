"""Direct source nodes checked by the reflex and its local recovery verifier.

Python's function claims and Java's syntactic nodes use different scopes.
Relationship/contract claims are not direct file nodes: including them would
turn a target-file check into a cross-file dependency check.
"""

from dataclasses import replace
from pathlib import Path


def file_language(rel_path: str) -> str | None:
    return {".py": "python", ".java": "java"}.get(Path(rel_path).suffix)


def select_file_claims(claims, rel_path: str) -> list:
    """Select production direct-node claims, never inferred relationships."""
    language = file_language(rel_path)
    selected = {}
    for claim in claims:
        body = claim.body if isinstance(claim.body, dict) else {}
        if body.get("edge_kind"):
            continue
        bindings = claim.bindings
        if (language == "python" and claim.scope == "function"
                and len(bindings) == 1 and bindings[0].path == rel_path):
            selected[claim.id] = claim
        elif (
            language == "java"
            and claim.scope in {"class", "declaration"}
            and body.get("language") == "java"
            and body.get("extraction_tier") == "java-treesitter-syntactic"
            and isinstance(body.get("node_kind"), str)
            and body["node_kind"]
        ):
            # Enrichment can attach e.g. repository_domain_entity dependencies
            # to a direct node. Keep its own declaration, not the dependency
            # freshness, for this file-local gate. Never mutate the stored claim.
            direct = [binding for binding in bindings
                      if binding.path == rel_path and binding.role == "declaration"
                      and binding.hash_kind == "java-treesitter-token-stream"
                      and binding.fn_hash]
            if len(direct) == 1:
                selected[claim.id] = replace(claim, bindings=direct)
    return [selected[claim_id] for claim_id in sorted(selected)]


def empty_coverage(rel_path: str) -> tuple[str, str]:
    reason = "no_eligible_claims" if file_language(rel_path) else "unsupported_language"
    return reason, (
        f"TMF reflex has no eligible source-node coverage for {rel_path}; "
        "allowing without a freshness determination. Warm a supported file "
        "with its extraction dependencies installed."
    )
