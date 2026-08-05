from __future__ import annotations

from dataclasses import dataclass

from .git import GitRepo


@dataclass(frozen=True)
class ProvenanceEvidence:
    source_type: str  # docstring | commit | pr
    text: str
    commit: str | None = None
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    url: str | None = None

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "text_untrusted_data": self.text,
            "commit": self.commit,
            "url": self.url,
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


def docstring_evidence(path: str, qualname: str, docstring: str | None, line_start: int, line_end: int) -> ProvenanceEvidence | None:
    if not docstring:
        return None
    return ProvenanceEvidence(
        source_type="docstring",
        text=docstring,
        commit=None,
        path=path,
        line_start=line_start,
        line_end=line_end,
    )


def pr_evidence(*, text: str, url: str, path: str | None = None, line_start: int | None = None, line_end: int | None = None) -> ProvenanceEvidence:
    return ProvenanceEvidence(
        source_type="pr",
        text=text,
        commit=None,
        url=url,
        path=path,
        line_start=line_start,
        line_end=line_end,
    )


def blame_commit_evidence(repo: GitRepo, path: str, line_start: int, line_end: int) -> ProvenanceEvidence | None:
    """Return commit-message evidence for the most relevant blamed commit.

    Commit text is immutable provenance, not a freshness gate. The claim still
    binds to the current working-tree file_blob/fn_hash so code changes stale it.
    """
    try:
        out = repo.run("blame", "--porcelain", f"-L{line_start},{line_end}", "HEAD", "--", path)
    except Exception:
        return None
    commits: list[str] = []
    for line in out.splitlines():
        if not line or line.startswith("\t"):
            continue
        first = line.split(maxsplit=1)[0]
        if len(first) >= 7 and all(c in "0123456789abcdef" for c in first.lower()):
            commits.append(first)
    if not commits:
        return None
    # Pick the most frequent blamed commit in the span; stable tie by first occurrence.
    counts = {c: commits.count(c) for c in commits}
    commit = max(counts, key=lambda c: (counts[c], -commits.index(c)))
    try:
        message = repo.run("show", "-s", "--format=%B", commit)
    except Exception:
        return None
    if not message.strip():
        return None
    return ProvenanceEvidence(
        source_type="commit",
        text=message.strip(),
        commit=commit,
        path=path,
        line_start=line_start,
        line_end=line_end,
    )


def collect_function_provenance(repo: GitRepo, *, path: str, qualname: str, docstring: str | None, line_start: int, line_end: int) -> list[ProvenanceEvidence]:
    evidence: list[ProvenanceEvidence] = []
    doc = docstring_evidence(path, qualname, docstring, line_start, line_end)
    if doc:
        evidence.append(doc)
    commit = blame_commit_evidence(repo, path, line_start, line_end)
    if commit:
        evidence.append(commit)
    return evidence
