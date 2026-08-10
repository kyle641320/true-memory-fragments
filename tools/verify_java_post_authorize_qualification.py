#!/usr/bin/env python3
"""Held-out qualification for exact-import Java @PostAuthorize declarations."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tmf.java_extract import (extract_java_classes, extract_java_methods,
                              resolve_java_post_authorize_declarations)

FIX = ROOT / "fixtures/java-post-authorize-heldout"
POSITIVE = FIX / "maven/src/main/java/heldout/security/SecuredService.java"

def resolve(path: Path, source: str | None = None):
    text = path.read_text() if source is None else source
    rel = path.relative_to(FIX).as_posix()
    return resolve_java_post_authorize_declarations(
        rel, text, extract_java_classes(rel, text), extract_java_methods(rel, text))

def snapshot():
    declarations, rejected = [], []
    for path in sorted(FIX.rglob("*.java")):
        found, unresolved = resolve(path)
        declarations.extend((x.owner_id, x.owner_qualname, x.owner_kind, x.expression,
                             x.line_start, x.line_end, x.annotation_hash, x.owner_hash)
                            for x in found)
        rejected.extend((path.relative_to(FIX).as_posix(), item.owner_id, item.reason)
                        for values in unresolved.values() for item in values)
    return sorted(declarations), sorted(rejected)

def main() -> int:
    first, second = snapshot(), snapshot()
    declarations, rejected = first
    source = POSITIVE.read_text()
    original, _ = resolve(POSITIVE, source)
    mutated, _ = resolve(POSITIVE, source.replace("hasAuthority('AUDIT')", "hasAuthority('REVIEW')"))
    deleted_source = "\n".join(line for line in source.splitlines() if "AUDIT" not in line) + "\n"
    deleted, _ = resolve(POSITIVE, deleted_source)
    original_by_owner = {x.owner_id: x for x in original}
    mutated_by_owner = {x.owner_id: x for x in mutated}
    changed = [owner for owner in original_by_owner if owner in mutated_by_owner and
               original_by_owner[owner].expression != mutated_by_owner[owner].expression]
    method_decls = [x for x in original if x.owner_kind == "method"]
    reason_list = [x[2] for x in rejected]
    reasons = set(reason_list)
    expected_anchors = {
        ("SecuredService", "class", 3, 3),
        ("SecuredService.load", "method", 5, 5),
        ("SecuredService.load", "method", 7, 7),
    }
    actual_anchors = {(x.owner_qualname, x.owner_kind, x.line_start, x.line_end) for x in original}
    checks = {
        "independent_maven_fixture": (FIX / "maven/pom.xml").is_file(),
        "independent_gradle_fixture": (FIX / "gradle/build.gradle").is_file(),
        "deterministic_repeat": first == second,
        "exact_literal_metadata": sorted(x.expression for x in original) == ["#id == authentication.name", "hasAuthority('AUDIT')", "hasRole('ADMIN')"],
        "class_and_overload_safe_declarations": len(original) == 3 and len(method_decls) == 2 and len({x.owner_id for x in method_decls}) == 2,
        "stable_ids_under_literal_mutation": len(changed) == 1 and set(original_by_owner) == set(mutated_by_owner),
        "token_hash_changes_on_literal_mutation": len(changed) == 1 and original_by_owner[changed[0]].annotation_hash != mutated_by_owner[changed[0]].annotation_hash,
        "deletion_reconciliation": len(deleted) == 2 and len({x.owner_id for x in original} - {x.owner_id for x in deleted}) == 1,
        "dynamic_constant_placeholder_unresolved": "post_authorize_value_not_literal_string" in reasons and sum(r == "post_authorize_value_not_literal_string" for r in reason_list) >= 3,
        "decoy_annotation_excluded": all("decoy" not in x[3] for x in declarations),
        "import_ambiguity_excluded": "post_authorize_annotation_not_exact_explicit_import" in reasons and all("ambiguous" not in x[3] for x in declarations),
        "precise_annotation_anchors": actual_anchors == expected_anchors,
        "owner_token_hash_changes_on_annotation_mutation": len(changed) == 1 and original_by_owner[changed[0]].owner_hash != mutated_by_owner[changed[0]].owner_hash,
    }
    # Owner hash is the method token hash and intentionally changes with its annotation.
    ok = all(checks.values())
    limitations = [
        "Declaration-only: exact explicit Spring Security PostAuthorize imports and direct annotations are recognized.",
        "Expression strings are retained as opaque literals; SpEL is never parsed or evaluated.",
        "Constants, computed expressions, placeholders, wildcard/ambiguous imports, aliases, meta-annotations, and inheritance are unresolved or excluded.",
        "No authorization outcome, security context, proxying, call graph, or runtime enforcement is inferred.",
    ]
    report = {"format": "tmf.java-post-authorize-qualification.v1", "status": "PASS" if ok else "FAIL",
              "checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks),
              "declarations": len(declarations), "unresolved": len(rejected), "limitations": limitations}
    out = ROOT / "reports/java-post-authorize-qualification"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = [f"# Java PostAuthorize qualification: {report['status']}", "",
             f"- Checks: {report['checks_passed']}/{report['checks_total']}",
             f"- Held-out declarations: {len(declarations)}", f"- Held-out unresolved: {len(rejected)}", "", "## Checks", ""]
    lines += [f"- [{'x' if passed else ' '}] `{name}`" for name, passed in checks.items()]
    lines += ["", "## Explicit limitations", ""] + [f"- {item}" for item in limitations]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
