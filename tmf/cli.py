from __future__ import annotations

import argparse
import json
from pathlib import Path

from .feedback import apply_feedback
from .explain import explain_claim, full_view, render_reviewer_text, thin_view
from .freshness import check_freshness
from .git import GitRepo
from .retrieve import refresh_path, retrieve_path, retrieve_text, reverse_callers
from .warm import warm_repo
from .contract_warm import warm_contracts
from .batch_warm import batch_warm
from .store import Store
from .metrics import stats as metrics_stats
from .validation import run_heldout_validation, run_self_validation


def _claim_thin_view(repo: GitRepo, claim) -> dict:
    return thin_view(explain_claim(repo, claim))


def cmd_retrieve(args: argparse.Namespace) -> int:
    repo = GitRepo(args.repo)
    if args.full:
        store = Store(repo.root)
        claim = store.get_claim(args.full)
        if claim is None:
            print(json.dumps({"error": "claim not found", "claim_id": args.full}, indent=2))
            return 1
        print(json.dumps(full_view(repo, claim), ensure_ascii=False, indent=2))
        return 0

    if args.path:
        result = (
            refresh_path(args.repo, args.path, use_model=args.model_derive)
            if args.refresh else retrieve_path(args.repo, args.path)
        )
    else:
        result = retrieve_text(args.repo, args.query, limit=args.limit, use_model=args.model_derive)
    payload = {
        "query": result.query,
        "view": "thin",
        "claims": [_claim_thin_view(repo, item.claim) for item in result.claims],
        "source_fallback_paths": list(result.source_fallback.keys()),
        "gaps": result.gaps or [],
        "next_steps": {
            "explain": "tmf explain <claim-id> --repo <repo>",
            "full": "tmf retrieve --full <claim-id> --repo <repo>",
        },
    }
    for item in result.claims:
        hint = item.claim.body.get("java_extraction", {}).get("degrade_hint") if isinstance(item.claim.body, dict) else None
        if hint:
            payload["degrade_hint"] = hint
            break
    if args.include_source:
        payload["source_fallback"] = result.source_fallback
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    repo = GitRepo(args.repo)
    store = Store(repo.root)
    claim = store.get_claim(args.claim_id)
    if claim is None:
        print(json.dumps({"error": "claim not found", "claim_id": args.claim_id}, indent=2))
        return 1
    payload = explain_claim(repo, claim)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_reviewer_text(payload))
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    store = Store(args.repo)
    claim = store.get_claim(args.claim_id)
    if claim is None:
        print(json.dumps({"error": "claim not found", "claim_id": args.claim_id}, indent=2))
        return 1
    result = apply_feedback(claim, args.kind, args.note or "")
    store.put_claim(result.claim)
    print(json.dumps({"claim_id": claim.id, "changed": result.changed, "note": result.note, "confidence": claim.confidence, "evidence": claim.evidence, "claim": claim.claim}, ensure_ascii=False, indent=2))
    return 0


def cmd_callers(args: argparse.Namespace) -> int:
    print(json.dumps(reverse_callers(args.repo, args.claim_id), ensure_ascii=False, indent=2))
    return 0


def cmd_warm(args: argparse.Namespace) -> int:
    if getattr(args, "contracts", False):
        print(json.dumps(warm_contracts(args.repo, command=args.contract_command, limit=args.limit, sample_limit=args.sample_limit), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(warm_repo(args.repo), ensure_ascii=False, indent=2))
    return 0


def cmd_batch_warm(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root) if args.state_root else None
    result = batch_warm(Path(args.repo), state_root=state_root, batch_size=args.batch_size)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0



def _make_validation_fixture(parent: Path, name: str, files: dict[str, str]) -> Path:
    import subprocess

    repo = parent / name
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tmf"], cwd=repo, check=True)
    for rel, text in files.items():
        full = repo / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", *files.keys()], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "commit", "-m", "tmf validation fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return repo


def cmd_validate(args: argparse.Namespace) -> int:
    import tempfile

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out).resolve() if args.out else repo / "reports" / "cli-validate"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {}
    run_heldout = args.heldout or not args.self_only
    run_self = args.self_validate or not args.heldout

    if run_heldout:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = _make_validation_fixture(root, "fixture", {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n\ndef spare():\n    return 2\n",
            })
            realistic = _make_validation_fixture(root, "realistic", {
                "service.py": "from dataclasses import dataclass\n\n@dataclass\nclass User:\n    name: str\n\ndef normalize(user):\n    return user.name.strip().lower()\n",
                "api.py": "from service import normalize, User\n\ndef handler(raw):\n    return normalize(User(raw))\n",
            })
            payload["heldout"] = run_heldout_validation([fixture, realistic], out_dir / "heldout")
    if run_self:
        payload["self"] = run_self_validation(repo, out_dir / "self", sample_limit=args.sample_limit)

    summary = {
        "out_dir": str(out_dir),
        "heldout_status": payload.get("heldout", {}).get("summary", {}).get("status"),
        "heldout_precision": payload.get("heldout", {}).get("freshness", {}).get("precision"),
        "heldout_recall": payload.get("heldout", {}).get("freshness", {}).get("recall"),
        "self_status": payload.get("self", {}).get("summary", {}).get("status"),
        "self_precision": payload.get("self", {}).get("freshness_sampling", {}).get("precision"),
        "self_recall": payload.get("self", {}).get("freshness_sampling", {}).get("recall"),
        "self_fp": payload.get("self", {}).get("freshness_sampling", {}).get("fp"),
        "self_fn": payload.get("self", {}).get("freshness_sampling", {}).get("fn"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = any(v == "fail" for k, v in summary.items() if k.endswith("status"))
    return 1 if failed else 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import serve
    return serve(args.repo)


def cmd_stats(args: argparse.Namespace) -> int:
    print(json.dumps(metrics_stats(args.repo, since=args.since), ensure_ascii=False, indent=2))
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tmf", description="True Memory Fragments: explicit-refresh, source-bound code memory")
    sub = parser.add_subparsers(dest="cmd", required=True)

    retrieve = sub.add_parser("retrieve", help="retrieve a thin view by path or lexical query; use --full for one thick claim")
    retrieve.add_argument("query", nargs="?", help="lexical query when --path is not set")
    retrieve.add_argument("--path", help="repo-relative path to read through")
    retrieve.add_argument("--repo", default=".")
    retrieve.add_argument("--limit", type=int, default=5)
    retrieve.add_argument("--include-source", action="store_true")
    retrieve.add_argument("--model-derive", action="store_true", help="derive function claims through model candidate+verification interface")
    retrieve.add_argument("--refresh", action="store_true", help="explicitly re-derive --path before retrieving it")
    retrieve.add_argument("--full", metavar="CLAIM_ID", help="expand a single claim with thick body and full explain data")
    retrieve.set_defaults(func=cmd_retrieve)

    explain = sub.add_parser("explain", help="explain claim provenance, freshness, trust label, anchors, and action hint")
    explain.add_argument("claim_id")
    explain.add_argument("--repo", default=".")
    explain.add_argument("--json", action="store_true", help="emit structured agent-readable explanation")
    explain.set_defaults(func=cmd_explain)

    feedback = sub.add_parser("feedback", help="record feedback without treating hunches as facts")
    feedback.add_argument("claim_id")
    feedback.add_argument("kind", choices=["usage", "verified", "falsified", "hunch"])
    feedback.add_argument("--note", default="")
    feedback.add_argument("--repo", default=".")
    feedback.set_defaults(func=cmd_feedback)

    callers = sub.add_parser("callers", help="list conservative reverse callers for a function claim id")
    callers.add_argument("claim_id")
    callers.add_argument("--repo", default=".")
    callers.set_defaults(func=cmd_callers)

    warm = sub.add_parser("warm", help="derive supported claims for a repository into .tmf/ and build indexes")
    warm.add_argument("--repo", default=".")
    warm.add_argument("--contracts", action="store_true", help="resumably warm true-model semantic contract claims for non-trivial Python functions")
    warm.add_argument("--contract-command", help="model command for --contracts; defaults to TMF_MODEL_COMMAND")
    warm.add_argument("--limit", type=int, help="optional max functions to process this run")
    warm.add_argument("--sample-limit", type=int, default=20, help="number of contract samples with embedded source spans to write")
    warm.set_defaults(func=cmd_warm)

    batch_warm = sub.add_parser("batch-warm", help="memory-bounded warm: index repo in batches to avoid OOM")
    batch_warm.add_argument("--repo", default=".")
    batch_warm.add_argument("--batch-size", type=int, default=50, help="files per batch (default: 50)")
    batch_warm.add_argument("--state-root", help="optional state root directory")
    batch_warm.set_defaults(func=cmd_batch_warm)

    mcp = sub.add_parser("mcp", help="run a minimal MCP stdio server")
    mcp.add_argument("--repo", default=".")
    mcp.set_defaults(func=cmd_mcp)

    validate = sub.add_parser("validate", help="run held-out validation and/or self-dogfood validation")
    validate.add_argument("--repo", default=".", help="repository to self-validate; default: current directory")
    validate.add_argument("--out", help="output directory for validation reports; default: <repo>/reports/cli-validate")
    group = validate.add_mutually_exclusive_group()
    group.add_argument("--heldout", action="store_true", help="run only the held-out fixture bench")
    group.add_argument("--self", dest="self_only", action="store_true", help="run only self-dogfood validation")
    validate.add_argument("--self-validate", action="store_true", help="also run self-dogfood when --heldout is selected")
    validate.add_argument("--sample-limit", type=int, default=10, help="self-dogfood freshness sample limit")
    validate.set_defaults(func=cmd_validate)

    stats = sub.add_parser("stats", help="summarize local TMF metrics events")
    stats.add_argument("--repo", default=".")
    stats.add_argument("--since", help="ISO timestamp lower bound")
    stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "retrieve" and not args.path and not args.query and not args.full:
        parser.error("retrieve requires --path or query")
    if args.cmd == "retrieve" and args.refresh and not args.path:
        parser.error("retrieve --refresh requires --path")
    if args.cmd == "retrieve" and args.model_derive and not args.refresh:
        parser.error("retrieve --model-derive requires --refresh")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
