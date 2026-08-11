"""Semantic cache versions for source-derived claims.

These are deliberately independent of the on-disk schema version: changing an
extractor can change the set or meaning of valid claims without changing their
JSON shape.  Bump only the affected language pipeline so warm can invalidate a
precise source slice rather than rebuilding an unrelated repository.
"""

JAVA_DERIVATION_VERSION = "java.derive.v6"


def versions_for_path(path: str) -> dict[str, str]:
    return {"java": JAVA_DERIVATION_VERSION} if path.endswith(".java") else {}
