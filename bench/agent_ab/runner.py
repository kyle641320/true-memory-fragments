from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from tmf.explain import explain_claim, thin_view
from tmf.git import GitRepo
from tmf.retrieve import retrieve_text, reverse_callers, reverse_readers, reverse_subtypes
from tmf.store import Store
from tmf.warm import warm_repo

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
BUDGET = 6
SOURCE_SUFFIXES = {".py", ".java", ".toml"}
EXCLUDED_PREFIXES = ("bench/", "reports/", "vendor/", "scripts/")


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tokenize(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in TOKEN_RE.findall(text.lower()):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _is_universe_path(rel: str) -> bool:
    p = Path(rel)
    return (
        p.suffix in SOURCE_SUFFIXES
        and not rel.endswith(".md")
        and not rel.startswith(EXCLUDED_PREFIXES)
        and not rel.startswith(".")
        and "/." not in f"/{rel}"
    )


def universe(repo: Path) -> list[str]:
    git = GitRepo(repo)
    try:
        tracked = git.run("ls-files").splitlines()
    except Exception as exc:  # pragma: no cover - defensive for non-git use
        raise RuntimeError("agent_ab benchmark requires a git repository for a fixed universe") from exc
    return sorted(rel for rel in tracked if _is_universe_path(rel) and (repo / rel).is_file())


def universe_manifest(repo: Path, paths: list[str]) -> dict[str, Any]:
    git = GitRepo(repo)
    entries = [[path, git.blob_sha(path)] for path in paths]
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "file_count": len(paths),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "included_suffixes": sorted(SOURCE_SUFFIXES),
        "excluded_prefixes": list(EXCLUDED_PREFIXES),
        "entries": entries,
    }


def validate_golden(repo: Path, tasks: list[dict[str, Any]], paths: list[str]) -> None:
    allowed = set(paths)
    failures: list[str] = []
    for task in tasks:
        for path, qualname in task["golden_symbols"]:
            if path not in allowed:
                failures.append(f"{task['id']}: golden path outside universe: {path}::{qualname}")
                continue
            text = (repo / path).read_text(encoding="utf-8", errors="replace")
            if not symbol_hit(text, qualname):
                failures.append(f"{task['id']}: golden qualname not found in file: {path}::{qualname}")
    if failures:
        raise SystemExit("Golden validation failed:\n" + "\n".join(failures))


def files(repo: Path, paths: list[str]) -> list[Path]:
    return [repo / rel for rel in paths]


def symbol_hit(text: str, qualname: str) -> bool:
    return qualname in text or qualname.split(".")[-1] in text


def score_golden(reads: dict[str, str], golden: list[list[str]]) -> dict[str, Any]:
    hits = []
    for path, qualname in golden:
        if path in reads and symbol_hit(reads[path], qualname):
            hits.append([path, qualname])
    return {"hits": hits, "recall": len(hits) / len(golden) if golden else 1.0, "full_recall": len(hits) == len(golden)}


def baseline(repo: Path, paths: list[str], task: dict[str, Any]) -> dict[str, Any]:
    terms = tokenize(task["question"])
    ranked = []
    for p in files(repo, paths):
        rel = p.relative_to(repo).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        hay = (rel + "\n" + text).lower()
        score = sum(hay.count(t) for t in terms)
        if score:
            ranked.append((score, rel, text))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    reads: dict[str, str] = {}
    calls = 1
    bytes_read = 0
    calls_to_full = None
    for idx, (_score, rel, text) in enumerate(ranked[:BUDGET], start=1):
        reads[rel] = text
        bytes_read += len(text.encode("utf-8"))
        if calls_to_full is None and score_golden(reads, task["golden_symbols"])["full_recall"]:
            calls_to_full = calls + idx
    scored = score_golden(reads, task["golden_symbols"])
    return {"strategy": "baseline", "calls": calls + len(reads), "read_bytes": bytes_read, "golden": scored, "calls_to_full_recall": calls_to_full}


def _claim_in_universe(claim: Any, allowed_paths: set[str]) -> bool:
    return any(binding.path in allowed_paths for binding in claim.bindings)


def tmf_strategy(repo_path: Path, paths: list[str], task: dict[str, Any]) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    allowed_paths = set(paths)
    # The retrieval strategy is unchanged, but the measured universe is fixed:
    # ask for a larger candidate pool, then keep the top in-universe seeds only.
    result = retrieve_text(repo.root, task["question"], limit=200)
    calls = 1
    reads: dict[str, str] = {}
    bytes_read = 0
    seen_claims: set[str] = set()
    queued_claims: set[str] = set()
    queue: list[str] = []

    def enqueue(claim_id: str | None) -> None:
        if claim_id and claim_id not in seen_claims and claim_id not in queued_claims:
            claim = Store(repo.root).get_claim(claim_id)
            if claim and _claim_in_universe(claim, allowed_paths):
                queued_claims.add(claim_id)
                queue.append(claim_id)

    in_universe = [item for item in result.claims if _claim_in_universe(item.claim, allowed_paths)]
    for item in sorted(in_universe[:BUDGET], key=lambda item: item.claim.id):
        enqueue(item.claim.id)
    calls_to_full = None
    while queue and calls < BUDGET:
        cid = queue.pop(0)
        queued_claims.discard(cid)
        if cid in seen_claims:
            continue
        seen_claims.add(cid)
        claim = Store(repo.root).get_claim(cid)
        if claim and _claim_in_universe(claim, allowed_paths):
            thin = thin_view(explain_claim(repo, claim))
            calls += 1
            for b in claim.bindings:
                if b.path in allowed_paths and b.path not in reads and (repo.root / b.path).exists():
                    text = repo.read_file(b.path)
                    reads[b.path] = text
                    bytes_read += len(text.encode("utf-8"))
            graph_items = thin.get("callers", []) + thin.get("reads", []) + thin.get("read_by", [])
            for graph_item in sorted(graph_items, key=lambda item: json.dumps(item, sort_keys=True)):
                for key in ("source_id", "target_id"):
                    enqueue(graph_item.get(key))
            if claim.body.get("edge_kind") == "calls":
                for key in ("caller_id", "callee_id"):
                    enqueue(claim.body.get(key))
        if calls < BUDGET and len(seen_claims) <= 2:
            # Deterministic proxy for MCP expansion: one cheap reverse-callers probe plus
            # kind-specific readers/subtypes only when the seed itself looks relevant.
            expansions = [reverse_callers(repo.root, cid)]
            if claim and claim.scope == "declaration":
                expansions.append(reverse_readers(repo.root, cid))
            if claim and claim.body.get("node_kind") in {"class", "interface"}:
                expansions.append(reverse_subtypes(repo.root, cid))
            for rev in expansions:
                calls += 1
                reverse_items = rev.get("callers", []) + rev.get("readers", []) + rev.get("subtypes", [])
                for item in sorted(reverse_items, key=lambda item: json.dumps(item, sort_keys=True)):
                    for key in ("caller_id", "reader_id", "child_id"):
                        enqueue(item.get(key))
                if calls >= BUDGET:
                    break
        if calls_to_full is None and score_golden(reads, task["golden_symbols"])["full_recall"]:
            calls_to_full = calls
    scored = score_golden(reads, task["golden_symbols"])
    return {"strategy": "tmf", "calls": calls, "read_bytes": bytes_read, "golden": scored, "calls_to_full_recall": calls_to_full}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        cat = row["category"]
        strat = row["strategy"]
        bucket = out.setdefault(cat, {}).setdefault(strat, {"tasks": 0, "recall_sum": 0.0, "wins": 0, "losses": 0})
        bucket["tasks"] += 1
        bucket["recall_sum"] += row["golden"]["recall"]
    for cat, bys in out.items():
        for _strat, b in bys.items():
            b["mean_recall"] = b["recall_sum"] / b["tasks"] if b["tasks"] else 0.0
            del b["recall_sum"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--tasks", default="bench/agent_ab/tasks.jsonl")
    ap.add_argument("--out", default="bench/agent_ab/out")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    paths = universe(repo)
    manifest = universe_manifest(repo, paths)
    tasks = load_tasks(Path(args.tasks))
    validate_golden(repo, tasks, paths)
    warm_repo(repo)

    rows = []
    start = time.perf_counter()
    for task in tasks:
        b = baseline(repo, paths, task)
        t = tmf_strategy(repo, paths, task)
        for r in (b, t):
            rows.append({"id": task["id"], "category": task["category"], **r})
    # encode wall clock deterministically for byte-identical reports; benchmark is operation-count oriented.
    report = {
        "limitations": "Scripted deterministic retrieval proxy, not LLM task success rate. Measurement-only; findings including TMF losses are success.",
        "budget": BUDGET,
        "task_count": len(tasks),
        "wall_clock_seconds": 0.0,
        "universe_manifest_sha": manifest["sha256"],
        "universe_file_count": manifest["file_count"],
        "universe_included_suffixes": manifest["included_suffixes"],
        "universe_excluded_prefixes": manifest["excluded_prefixes"],
        "universe_entries": manifest["entries"],
        "rows": rows,
        "categories": aggregate(rows),
    }
    for task in tasks:
        b = next(r for r in rows if r["id"] == task["id"] and r["strategy"] == "baseline")
        t = next(r for r in rows if r["id"] == task["id"] and r["strategy"] == "tmf")
        if t["golden"]["recall"] < b["golden"]["recall"]:
            report.setdefault("tmf_losses", []).append(task["id"])
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# TMF Agent A/B Proxy Report",
        "",
        report["limitations"],
        "",
        f"Universe files: {manifest['file_count']}",
        f"Universe manifest sha256: `{manifest['sha256']}`",
        f"Universe excludes: {', '.join(EXCLUDED_PREFIXES)}; suffixes: {', '.join(sorted(SOURCE_SUFFIXES))}",
        "",
        f"Tasks: {len(tasks)}  Budget: {BUDGET}",
        "",
        "## Categories",
    ]
    for cat, data in sorted(report["categories"].items()):
        lines.append(f"- {cat}: baseline recall={data.get('baseline',{}).get('mean_recall',0):.3f}; tmf recall={data.get('tmf',{}).get('mean_recall',0):.3f}")
    lines += ["", "## TMF losses", ", ".join(report.get("tmf_losses", [])) or "None"]
    lines += ["", "## Universe sample", ""]
    for path, blob in manifest["entries"][:25]:
        lines.append(f"- `{path}` `{blob}`")
    if len(manifest["entries"]) > 25:
        lines.append(f"- ... {len(manifest['entries']) - 25} more files in report.json")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
