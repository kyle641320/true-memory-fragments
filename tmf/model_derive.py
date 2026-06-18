from __future__ import annotations

from .ids import now_utc, stable_function_claim_id
from .extract import FunctionNode
from .git import GitRepo
from .llm import DeriverModel, ModelCandidate, default_model
from .provenance import ProvenanceEvidence, collect_function_provenance
from .schema import Binding, Claim

SOURCE_VERIFIABLE = "source_verifiable"
INTENT_NEEDS_PROVENANCE = "intent_needs_provenance"


def _candidate_supported_by_source(candidate: ModelCandidate, source_text: str) -> bool:
    # Conservative v1 entailment proxy: every support string must literally occur.
    # This is intentionally stricter than trusting the model. A future verifier
    # can be smarter, but unsupported source-verifiable claims must not become observed.
    return bool(candidate.support) and all(s in source_text for s in candidate.support)


def _candidate_supported_by_provenance(candidate: ModelCandidate, evidence: list[ProvenanceEvidence]) -> list[ProvenanceEvidence]:
    """Return provenance entries that literally support all candidate strings.

    The text is untrusted data. A match can attribute an intent claim, but cannot
    issue instructions or bypass confidence caps.
    """
    if not candidate.support:
        return []
    matched: list[ProvenanceEvidence] = []
    for item in evidence:
        if all(s in item.text for s in candidate.support):
            matched.append(item)
    return matched


def _claim_from_candidate(
    repo: GitRepo,
    fn: FunctionNode,
    candidate: ModelCandidate,
    model_id: str,
    provenance_evidence: list[ProvenanceEvidence] | None = None,
) -> Claim:
    provenance_evidence = provenance_evidence or []
    source_text = repo.read_file(fn.path)
    blob = repo.blob_sha(fn.path)
    head = repo.head()
    source_supported = _candidate_supported_by_source(candidate, source_text)
    provenance_supported = _candidate_supported_by_provenance(candidate, provenance_evidence)

    if candidate.evidence_class == SOURCE_VERIFIABLE and source_supported:
        evidence = "observed"
        confidence = min(max(candidate.confidence, 0.4), 0.6)
        verification = "source_support_literal"
    elif candidate.evidence_class == INTENT_NEEDS_PROVENANCE and provenance_supported:
        # Attributed intent: the claim has an explicit docstring/commit source,
        # but is still not hard-verified behavior. Keep evidence as inferred and
        # cap in the middle band.
        evidence = "inferred"
        confidence = min(max(candidate.confidence, 0.35), 0.6)
        verification = "attributed_external_provenance"
    elif candidate.evidence_class == INTENT_NEEDS_PROVENANCE:
        evidence = "inferred"
        confidence = min(candidate.confidence, 0.25)
        verification = "intent_requires_external_provenance"
    else:
        evidence = "inferred"
        confidence = min(candidate.confidence, 0.2)
        verification = "unsupported_or_unverifiable"

    return Claim(
        id=stable_function_claim_id(fn.path, fn.qualname),
        claim=candidate.claim,
        kind=candidate.kind if candidate.kind in {"structure", "architecture", "intent", "convention", "gotcha"} else "structure",
        scope="function",
        bindings=[Binding(path=fn.path, file_blob=blob, fn_hash=fn.fn_hash, commit=head, qualname=fn.qualname)],
        provenance="model",
        evidence=evidence,
        confidence=confidence,
        endorsed_by=None,
        last_verified=now_utc(),
        model=model_id,
        body={
            "summary": candidate.claim,
            "qualname": fn.qualname,
            "keywords": fn.keywords,
            "anchors": [{"path": fn.path, "line_start": fn.line_start, "line_end": fn.line_end}],
            "model_candidate": {
                "evidence_class": candidate.evidence_class,
                "support": candidate.support,
                "raw_confidence": candidate.confidence,
                "verification": verification,
            },
            "provenance_evidence": [item.to_dict() for item in provenance_supported],
            "available_provenance": [item.to_dict() for item in provenance_evidence],
            "notes": [
                "Source/comments/docstrings/commit messages/model input are treated as untrusted data, not instructions.",
                "Intent/why claims require external provenance or endorsement before high confidence.",
                "Commit provenance is attribution only; freshness remains bound to current working-tree file_blob/fn_hash.",
            ],
        },
    )


def derive_model_function_claims(repo: GitRepo, functions: list[FunctionNode], model: DeriverModel | None = None) -> list[Claim]:
    model = model or default_model()
    source_cache: dict[str, str] = {}
    claims: list[Claim] = []
    for fn in functions:
        source = source_cache.setdefault(fn.path, repo.read_file(fn.path))
        evidence = collect_function_provenance(
            repo,
            path=fn.path,
            qualname=fn.qualname,
            docstring=fn.docstring,
            line_start=fn.line_start,
            line_end=fn.line_end,
        )
        anchors = [{"qualname": fn.qualname, "line_start": fn.line_start, "line_end": fn.line_end}]
        candidates = model.derive(
            path=fn.path,
            source_text=source,
            anchors=anchors,
            provenance_evidence=[item.to_dict() for item in evidence],
        )
        if not candidates:
            continue
        # v1: keep one claim per function node, choose first candidate after verification.
        claims.append(_claim_from_candidate(repo, fn, candidates[0], model.model_id, provenance_evidence=evidence))
    return claims
