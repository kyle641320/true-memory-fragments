#!/usr/bin/env python3
"""
TMF 局部重新认知（local re-warm）

用法：
  python3 tmf-local-warm.py <repo_root> <rel_path>

在 agent 被反射钩子阻断后，用此脚本局部 warm 单个文件，
使 TMF 缓存更新到当前版本，下一次操作即可放行。

为什么这能避免死循环：
  - 此脚本通过 Bash 工具执行（非 Read/Edit/Write）
  - 钩子只拦截 Read/Edit/Write → 不拦截 Bash
  - warm 完成后文件 claims 与当前源码一致 → stale 消失
  - 下一次 agent 正常 Read/Edit/Write → freshness check 通过 → 放行
  ══  闭环完成，零循环风险 ══
"""

import argparse
import os
import sys
from pathlib import Path

# 确保 TMF 可导入
_TMF_WORKTREE = Path(__file__).resolve().parent.parent / "tmf-worktree"
if not _TMF_WORKTREE.exists():
    _TMF_WORKTREE = Path(os.environ.get(
        "TMF_WORKTREE",
        str(Path(__file__).resolve().parents[3]),
    ))

if str(_TMF_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_TMF_WORKTREE))


def local_warm(repo_root: str, rel_path: str, state_root: str | None = None) -> dict:
    """只 warm 指定文件的 claims，不触碰其他文件。"""
    from tmf.git import GitRepo
    from tmf.derive import derive_claims_for_path
    from tmf.store import Store
    from tmf.freshness import check_freshness

    repo = GitRepo(repo_root)
    state_path = Path(state_root).expanduser().resolve() if state_root else Path(repo_root).resolve() / ".tmf"
    store = Store(state_path.parent if state_path.name == ".tmf" else repo_root)
    store.init()

    text = repo.read_file(rel_path)
    blob = repo.blob_sha(rel_path)

    # 推导当前文件的 claims
    claims = derive_claims_for_path(repo, rel_path)
    python_function_claims = [c for c in claims if c.scope == "function"]
    java_method_claims = [
        c for c in claims
        if c.scope == "class" and c.body.get("language") == "java"
        and c.body.get("node_kind") == "method"
    ]
    java_constructor_claims = [
        c for c in claims
        if c.scope == "class" and c.body.get("language") == "java"
        and c.body.get("node_kind") == "constructor"
    ]
    callable_claims = python_function_claims + java_method_claims + java_constructor_claims
    all_claim_types = list(set(c.scope for c in claims))

    # Reconcile through Store's guarded path/edge lifecycle. In particular,
    # never delete multi-file claims merely because one binding matches.
    with store.write_lock():
        store.reconcile_path_claims(rel_path, claims)
        edge_claims = [claim for claim in claims if claim.body.get("edge_kind")]
        store.reconcile_edge_claims_for_caller_path(rel_path, edge_claims)
        for claim in claims:
            store.put_claim(claim)

    # 验证：重新检查 freshness
    stale_check: list[dict] = []
    for claim in callable_claims:
        fresh_result = check_freshness(repo, claim)
        stale_check.append({
            "claim_id": claim.id,
            "qualname": claim.body.get("qualname", ""),
            "fresh": fresh_result.fresh,
            "stale_bindings": fresh_result.stale_bindings if not fresh_result.fresh else [],
        })

    all_fresh = all(c["fresh"] for c in stale_check)

    return {
        "schema_version": "tmf.reflex.local_warm.v1",
        "action": "local_re_warm",
        "file": rel_path,
        "canonical_repo_root": str(Path(repo_root).resolve()),
        "canonical_state_root": str(state_path),
        "blob": blob,
        "total_claims": len(claims),
        # Preserve the original field while making callable coverage explicit.
        "function_claims": len(python_function_claims),
        "python_function_claims": len(python_function_claims),
        "java_method_claims": len(java_method_claims),
        "java_constructor_claims": len(java_constructor_claims),
        "callable_claims": len(callable_claims),
        "claim_types": all_claim_types,
        "functions": [c["qualname"] for c in stale_check],
        "callables": [c["qualname"] for c in stale_check],
        "all_fresh_now": all_fresh,
        "stale_check": stale_check,
        "message": (
            f"✅ 局部重新认知完成：{rel_path}\n"
            f"   callable 数：{len(callable_claims)} | 全部 fresh：{all_fresh}\n"
            f"   仍需在同一会话成功 Read 当前文件，双门才会允许修正后的重试。"
            if all_fresh
            else f"⚠️ 局部 warm 后仍有 stale：{rel_path}\n"
            f"   请检查文件是否在 warm 期间被再次修改。"
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Warm one file into the selected TMF state root.")
    parser.add_argument("repo_root")
    parser.add_argument("rel_path")
    parser.add_argument("--state-root", default=None)
    args = parser.parse_args()

    try:
        result = local_warm(args.repo_root, args.rel_path, args.state_root)
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        import json
        print(json.dumps({
            "error": str(exc),
            "action": "local_re_warm_failed",
            "file": args.rel_path,
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
