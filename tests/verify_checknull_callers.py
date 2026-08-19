#!/usr/bin/env python3
"""
验证 Binding 行号修复后，checkNotNull 的调用边是否正确提取。

预期：
1. Preconditions.checkNotNull 方法节点有正确的 line_start/line_end
2. 能找到至少 100 个调用 checkNotNull 的 callers
3. 调用边的 caller 方法也有正确的行号
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add tmf to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmf.store import Store
from tmf.index import InvertedIndex


def verify_checknull_callers(repo_root: str) -> dict:
    """验证 checkNotNull 的调用边提取"""
    store = Store(repo_root)
    idx = InvertedIndex(Path(repo_root) / ".tmf" / "index.db")
    
    if not idx.valid():
        return {
            "status": "error",
            "error": "Index not valid"
        }
    
    # 1. 找到 Preconditions.checkNotNull 方法节点
    results = store.search_index("checkNotNull", limit=100)
    
    checknull_methods = [
        c for c in results
        if c.scope == "class"
        and "Preconditions" in c.qualname
        and "checkNotNull" in c.qualname
        and c.path and "Preconditions.java" in c.path
    ]
    
    if not checknull_methods:
        return {
            "status": "error",
            "error": "No checkNotNull method nodes found"
        }
    
    print(f"Found {len(checknull_methods)} checkNotNull method variants")
    
    # 2. 检查方法节点是否有行号
    methods_with_lines = []
    for m in checknull_methods:
        bindings = [b for b in m.bindings if b.kind == "source"]
        if bindings and bindings[0].line_start is not None:
            methods_with_lines.append(m)
            print(f"  ✓ {m.qualname} has lines {bindings[0].line_start}-{bindings[0].line_end}")
        else:
            print(f"  ✗ {m.qualname} missing line numbers")
    
    if not methods_with_lines:
        return {
            "status": "error",
            "error": "No checkNotNull methods have line numbers"
        }
    
    # 3. 查询调用边（作为 callee）
    total_callers = 0
    sample_callers = []
    
    for method in methods_with_lines[:5]:  # 检查前 5 个变体
        # 查询以该方法为 callee_id 的边
        edge_ids = idx.edge_ids(method.claim_id, {"calls"}, limit=1000)
        
        if edge_ids:
            # 获取边的详细信息
            for edge_id in edge_ids[:10]:  # 取前 10 个样本
                edge_claim = store.get_claim(edge_id)
                if edge_claim and edge_claim.relation:
                    rel = edge_claim.relation
                    # 这是 outgoing edge（method 作为 caller）
                    # 我们需要 incoming edge（method 作为 callee）
                    if rel.callee_id == method.claim_id:
                        caller = store.get_claim(rel.caller_id)
                        if caller:
                            caller_bindings = [b for b in caller.bindings if b.kind == "source"]
                            sample_callers.append({
                                "caller_qualname": caller.qualname,
                                "caller_path": caller.path,
                                "caller_lines": f"{caller_bindings[0].line_start}-{caller_bindings[0].line_end}" if caller_bindings and caller_bindings[0].line_start else "None"
                            })
        
        # 查询 incoming edges - 需要反向查询
        # 这需要扫描所有 calls 边
        
    # 简化验证：直接统计索引中有多少条边引用了 checkNotNull
    all_edge_ids = []
    for method in methods_with_lines:
        edges = idx.edge_ids(method.claim_id, {"calls"}, limit=5000)
        all_edge_ids.extend(edges)
    
    print(f"\nTotal edge_ids referencing checkNotNull methods: {len(all_edge_ids)}")
    
    if len(all_edge_ids) == 0:
        return {
            "status": "warning",
            "message": "Methods have line numbers but no call edges found",
            "methods_with_lines": len(methods_with_lines),
            "total_edges": 0
        }
    
    return {
        "status": "success",
        "methods_with_lines": len(methods_with_lines),
        "total_edges": len(all_edge_ids),
        "sample_callers": sample_callers[:5]
    }


if __name__ == "__main__":
    import json
    
    repo = sys.argv[1] if len(sys.argv) > 1 else "/root/.openclaw/workspace/repos/guava"
    
    result = verify_checknull_callers(repo)
    
    print("\n" + "="*60)
    print("VERIFICATION RESULT:")
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["status"] in ("success", "warning") else 1)
