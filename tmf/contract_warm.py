from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .contracts import derive_contract_candidate_with_command, sanitize_contract_candidate
from .derive import derive_contract_claim
from .extract import extract_functions
from .git import GitRepo
from .store import Store


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _function_span(source: str, line_start: int, line_end: int) -> str:
    lines = source.splitlines()
    return "\n".join(lines[max(0, line_start - 1): line_end]) + ("\n" if line_end >= line_start else "")


def _iter_python_functions(repo: GitRepo) -> list[Any]:
    out = []
    for path in sorted(repo.root.rglob("*.py")):
        rel = path.relative_to(repo.root).as_posix()
        if rel.startswith((".git/", ".tmf/", ".tmf_contracts/", ".ts-venv/")):
            continue
        if "/.git/" in rel or "/.tmf/" in rel or "/.ts-venv/" in rel:
            continue
        try:
            text = repo.read_file(rel)
            out.extend(extract_functions(rel, text))
        except Exception:
            continue
    return out


def _contract_version_counts(store: Store) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for claim in store.iter_claims():
        if claim.scope != "contract":
            continue
        version = claim.body.get("contract_version") if isinstance(claim.body, dict) else None
        counts[str(version or "unknown")] += 1
    return dict(counts)


def warm_contracts(repo_root: str | Path, *, command: str | None = None, limit: int | None = None, sample_limit: int = 20) -> dict[str, Any]:
    """Warm semantic contract claims with a real model command, resumably.

    Each function is written independently to `.tmf/contract_warm/records/*.json`
    before the claim is stored, so interruptions can resume safely. The model
    command receives untrusted source/provenance JSON and must return contract JSON.
    """
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    store.init()
    out_root = repo.root / ".tmf" / "contract_warm"
    records_dir = out_root / "records"
    samples_dir = out_root / "samples"
    records_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    run_log = out_root / "run_log.jsonl"
    started = time.time()
    old_command = os.environ.get("TMF_MODEL_COMMAND")
    if command:
        os.environ["TMF_MODEL_COMMAND"] = command

    functions = [fn for fn in _iter_python_functions(repo) if (fn.line_end - fn.line_start + 1) >= 5]
    total = len(functions)
    processed = skipped_existing = succeeded = failed = skipped = 0
    reasons: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    sample_count = 0
    records = []
    try:
        for fn in functions:
            if limit is not None and processed >= limit:
                break
            rec_id = f"{fn.path}::{fn.qualname}".replace("/", "__").replace(" ", "_")
            rec_path = records_dir / (rec_id.replace("<", "_").replace(">", "_") + ".json")
            if rec_path.exists():
                try:
                    rec = json.loads(rec_path.read_text(encoding="utf-8"))
                    if rec.get("status") == "ok":
                        skipped_existing += 1
                        succeeded += 1
                        for a, n in rec.get("sanitizer_actions", {}).items():
                            action_counts[a] += int(n)
                        records.append(rec)
                        continue
                except Exception:
                    pass
            processed += 1
            t0 = time.time()
            source = repo.read_file(fn.path)
            try:
                claim = derive_contract_claim(repo, fn)
                if claim is None:
                    skipped += 1
                    reasons["derive_contract_claim_returned_none"] += 1
                    rec = {"status": "skipped", "reason": "derive_contract_claim_returned_none", "path": fn.path, "qualname": fn.qualname, "line_start": fn.line_start, "line_end": fn.line_end, "elapsed_s": round(time.time()-t0, 3)}
                    _write_json(rec_path, rec)
                    continue
                store.put_claim(claim)
                d = claim.to_dict()
                checks = d.get("body", {}).get("_contract_checks", {})
                actions = Counter(c.get("action") for c in checks.get("checks", []) if isinstance(c, dict))
                action_counts.update(actions)
                rec = {
                    "status": "ok",
                    "path": fn.path,
                    "qualname": fn.qualname,
                    "line_start": fn.line_start,
                    "line_end": fn.line_end,
                    "claim_id": claim.id,
                    "contract_version": d.get("body", {}).get("contract_version"),
                    "evidence": d.get("evidence"),
                    "confidence": d.get("confidence"),
                    "sanitizer_actions": dict(actions),
                    "elapsed_s": round(time.time()-t0, 3),
                }
                _write_json(rec_path, rec)
                if sample_count < sample_limit:
                    sample_count += 1
                    sample = dict(d)
                    sample.setdefault("body", {})["source_span_untrusted_data"] = {
                        "path": fn.path,
                        "line_start": fn.line_start,
                        "line_end": fn.line_end,
                        "text": _function_span(source, fn.line_start, fn.line_end),
                    }
                    sample_path = samples_dir / f"{sample_count:02d}_{claim.id}.json"
                    _write_json(sample_path, sample)
                    rec["sample_path"] = str(sample_path.relative_to(repo.root))
                succeeded += 1
                records.append(rec)
            except Exception as e:
                failed += 1
                reasons[type(e).__name__] += 1
                rec = {"status": "failed", "reason": type(e).__name__, "detail": str(e)[:500], "path": fn.path, "qualname": fn.qualname, "line_start": fn.line_start, "line_end": fn.line_end, "elapsed_s": round(time.time()-t0, 3)}
                _write_json(rec_path, rec)
            with run_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    finally:
        if command:
            if old_command is None:
                os.environ.pop("TMF_MODEL_COMMAND", None)
            else:
                os.environ["TMF_MODEL_COMMAND"] = old_command

    coverage = {
        "contract_versions": _contract_version_counts(store),
        "semantic_sanitized": _contract_version_counts(store).get("contract.v2.semantic_sanitized", 0),
        "mechanical": _contract_version_counts(store).get("contract.v1.mechanical", 0),
    }
    summary = {
        "status": "complete" if failed == 0 else "partial",
        "total_nontrivial_functions": total,
        "processed_this_run": processed,
        "skipped_existing_ok": skipped_existing,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "failure_or_skip_reasons": dict(reasons),
        "sanitizer_actions": dict(action_counts),
        "sample_count": sample_count,
        "elapsed_s": round(time.time() - started, 3),
        "coverage": coverage,
        "records_dir": str(records_dir.relative_to(repo.root)),
        "samples_dir": str(samples_dir.relative_to(repo.root)),
    }
    _write_json(out_root / "summary.json", summary)
    return summary
