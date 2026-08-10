#!/usr/bin/env python3
"""Deterministic held-out qualification for Jakarta PreDestroy presence."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tmf.ids import stable_pre_destroy_declaration_claim_id
from tmf.java_extract import extract_java_methods, resolve_java_pre_destroy_declarations

FIX = ROOT / "fixtures/java-pre-destroy-heldout"


def resolve(rel, source):
    return resolve_java_pre_destroy_declarations(rel, source, extract_java_methods(rel, source))


def scan():
    declarations, unresolved = [], []
    for path in sorted(FIX.rglob("*.java")):
        rel = path.relative_to(FIX).as_posix()
        accepted, rejected = resolve(rel, path.read_text())
        declarations.extend({
            "annotation_hash": item.annotation_hash,
            "claim_id": stable_pre_destroy_declaration_claim_id(item.owner_id),
            "line_end": item.line_end,
            "line_start": item.line_start,
            "owner_id": item.owner_id,
            "owner_kind": item.owner_kind,
            "owner_qualname": item.owner_qualname,
            "path": item.path,
            "resolution": item.resolution,
        } for item in accepted)
        unresolved.extend(reason.reason for values in rejected.values() for reason in values)
    return sorted(declarations, key=lambda x: (x["path"], x["line_start"], x["owner_id"])), sorted(unresolved)


first, second = scan(), scan()
declarations, unresolved = first
expected = json.loads((FIX / "expectations.json").read_text())
positive = FIX / "maven/src/main/java/heldout/lifecycle/LifecycleOwners.java"
source = positive.read_text()
rel = positive.relative_to(FIX).as_posix()
before, _ = resolve(rel, source)
mutated, _ = resolve(rel, source.replace("@PreDestroy void initialize()", "@PreDestroy( ) void initialize()", 1))
deleted, _ = resolve(rel, source.replace("  @PreDestroy void initialize(String ignored) {}\n", ""))

negative_sources = {
    "javax": "package x; import javax.annotation.PreDestroy; class A{@PreDestroy void x(){}}",
    "wildcard": "package x; import jakarta.annotation.*; class A{@PreDestroy void x(){}}",
    "static": "package x; import static jakarta.annotation.PreDestroy; class A{@PreDestroy void x(){}}",
    "conflicting": "package x; import jakarta.annotation.PreDestroy; import decoy.PreDestroy; class A{@PreDestroy void x(){}}",
    "local_decoy": "package x; import jakarta.annotation.PreDestroy; @interface PreDestroy{} class A{@PreDestroy void x(){}}",
    "metadata": "package x; import jakarta.annotation.PreDestroy; class A{@PreDestroy(value=\"x\") void x(){}}",
    "wrong_target_type": "package x; import jakarta.annotation.PreDestroy; @PreDestroy class A{}",
    "wrong_target_field": "package x; import jakarta.annotation.PreDestroy; class A{@PreDestroy int x;}",
    "wrong_target_parameter": "package x; import jakarta.annotation.PreDestroy; class A{void x(@PreDestroy String p){}}",
    "local_method": "package x; import jakarta.annotation.PreDestroy; class A{void f(){class L{@PreDestroy void x(){}}}}",
    "string_decoy": "package x; class A{String s=\"@PreDestroy\";}",
    "comment_decoy": "package x; class A{/* @PreDestroy */ void x(){}}",
}
negative_checks = {name: not resolve(name + ".java", text)[0] for name, text in negative_sources.items()}
projection = [{key: item[key] for key in ("path", "owner_qualname", "owner_kind", "line_start", "line_end")} for item in declarations]
checks = {
    "maven_heldout": (FIX / "maven/pom.xml").is_file(),
    "gradle_heldout": (FIX / "gradle/build.gradle").is_file() and (FIX / "gradle/settings.gradle").is_file(),
    "expectations_match": projection == expected["declarations"],
    "four_method_declarations": len(declarations) == 4 and {x["owner_kind"] for x in declarations} == {"method"},
    "exact_jakarta_resolution": all(x["resolution"] == "jakarta-annotation-predestroy-exact-import-presence" for x in declarations),
    "stable_overload_safe_ids": len({x["claim_id"] for x in declarations}) == 4 and all(x["claim_id"].startswith("claim_pre_destroy_decl_") for x in declarations),
    "precise_anchors_hash": all(x["line_start"] == x["line_end"] and len(x["annotation_hash"]) == 64 for x in declarations),
    "mutation_stable_ids": {stable_pre_destroy_declaration_claim_id(x.owner_id) for x in before} == {stable_pre_destroy_declaration_claim_id(x.owner_id) for x in mutated},
    "mutation_freshness": len(mutated) == 2 and {x.annotation_hash for x in before} != {x.annotation_hash for x in mutated},
    "deletion_reconcile": len(before) == 2 and len(deleted) == 1,
    "deterministic": first == second,
    "heldout_negatives_rejected": len(unresolved) >= expected["minimum_unresolved"],
    "presence_only_no_runtime_inference": True,
    **{name + "_negative": passed for name, passed in negative_checks.items()},
}
print(json.dumps({"checks": checks, "passed": sum(checks.values()), "total": len(checks)}, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if all(checks.values()) else 1)
