#!/usr/bin/env python3
"""Deterministic held-out qualification for Spring Lazy declarations."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tmf.ids import stable_lazy_declaration_claim_id
from tmf.java_extract import extract_java_classes, extract_java_methods, resolve_java_lazy_declarations

FIX = ROOT / "fixtures/java-lazy-heldout"


def resolve(rel, source):
    return resolve_java_lazy_declarations(rel, source, extract_java_classes(rel, source), extract_java_methods(rel, source))


def scan():
    declarations, unresolved = [], []
    for path in sorted(FIX.rglob("*.java")):
        rel = path.relative_to(FIX).as_posix()
        accepted, rejected = resolve(rel, path.read_text())
        declarations.extend(
            {
                "annotation_hash": item.annotation_hash,
                "claim_id": stable_lazy_declaration_claim_id(item.owner_id),
                "line_end": item.line_end,
                "line_start": item.line_start,
                "owner_id": item.owner_id,
                "owner_kind": item.owner_kind,
                "owner_qualname": item.owner_qualname,
                "path": item.path,
                "resolution": item.resolution,
            }
            for item in accepted
        )
        unresolved.extend(reason.reason for values in rejected.values() for reason in values)
    return sorted(declarations, key=lambda x: (x["path"], x["owner_qualname"])), sorted(unresolved)


first, second = scan(), scan()
declarations, unresolved = first
expected = json.loads((FIX / "expectations.json").read_text())
positive = FIX / "maven/src/main/java/heldout/lazy/LazyOwners.java"
source = positive.read_text()
rel = positive.relative_to(FIX).as_posix()
before, _ = resolve(rel, source)
mutated, _ = resolve(rel, source.replace("@Lazy\nclass", "@Lazy( )\nclass", 1))
deleted, _ = resolve(rel, source.replace("@Lazy\ninterface LazyContract {}\n", ""))

negative_sources = {
    "wildcard": "package x; import org.springframework.context.annotation.*; @Lazy class A{}",
    "static": "package x; import static org.springframework.context.annotation.Lazy; @Lazy class A{}",
    "conflicting": "package x; import org.springframework.context.annotation.Lazy; import decoy.Lazy; @Lazy class A{}",
    "local_decoy": "package x; import org.springframework.context.annotation.Lazy; class Lazy{} @Lazy class A{}",
    "metadata": "package x; import org.springframework.context.annotation.Lazy; @Lazy(names=\"cart\") class A{}",
    "wrong_target_field": "package x; import org.springframework.context.annotation.Lazy; class A{@Lazy int x;}",
    "wrong_target_record": "package x; import org.springframework.context.annotation.Lazy; @Lazy record A(){}",
    "local_type": "package x; import org.springframework.context.annotation.Lazy; class A{void x(){@Lazy class L{}}}",
    "string_decoy": "package x; class A{String value=\"@Lazy\";}",
}
negative_checks = {name: not resolve(name + ".java", text)[0] for name, text in negative_sources.items()}

expected_projection = [
    {key: item[key] for key in ("path", "owner_qualname", "owner_kind", "line_start", "line_end")}
    for item in declarations
]
checks = {
    "maven_heldout": (FIX / "maven/pom.xml").is_file(),
    "gradle_heldout": (FIX / "gradle/build.gradle").is_file(),
    "expectations_match": expected_projection == expected["declarations"],
    "type_method_direct_declarations": len(declarations) == 8 and {x["owner_kind"] for x in declarations} == {"class", "interface", "method"},
    "exact_fqn_resolution": all(x["resolution"] == "spring-context-lazy-exact-import-presence" for x in declarations),
    "stable_ids": len({x["claim_id"] for x in declarations}) == 8 and all(x["claim_id"].startswith("claim_lazy_decl_") for x in declarations),
    "precise_anchors_hash": all(x["line_start"] == x["line_end"] and len(x["annotation_hash"]) == 64 for x in declarations),
    "mutation_stable_ids": {stable_lazy_declaration_claim_id(x.owner_id) for x in before} == {stable_lazy_declaration_claim_id(x.owner_id) for x in mutated},
    "mutation_freshness": len(mutated) == 4 and {x.annotation_hash for x in before} != {x.annotation_hash for x in mutated},
    "deletion_reconcile": len(before) == 4 and len(deleted) == 3,
    "deterministic": first == second,
    "heldout_negatives_rejected": len(unresolved) >= expected["minimum_unresolved"],
    **{name + "_negative": passed for name, passed in negative_checks.items()},
}
result = {"checks": checks, "passed": sum(checks.values()), "total": len(checks)}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if all(checks.values()) else 1)
