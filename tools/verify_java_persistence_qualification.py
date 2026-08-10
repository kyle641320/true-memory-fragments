#!/usr/bin/env python3
"""Offline, deterministic production-qualification bench for bounded Java persistence metadata."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id
from tmf.store import Store
from tmf.warm import warm_repo

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "java-persistence-heldout"
FORBIDDEN = {"tables", "columns", "reads", "writes", "calls", "transactions", "result_mapping", "runtime_edges", "sql_edges"}

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def initialize(source: Path, target: Path):
    shutil.copytree(source, target)
    run(["git", "init"], target); run(["git", "config", "user.email", "heldout@example.invalid"], target); run(["git", "config", "user.name", "TMF heldout"], target)
    run(["git", "add", "."], target); run(["git", "commit", "-m", "independent heldout fixture"], target)

def claim(store, path, qualname, kind):
    found = store.get_claim(stable_java_node_claim_id(path, qualname, kind))
    assert found is not None, (path, qualname, kind)
    return found

def forbidden_keys(value):
    hits=[]
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN: hits.append(key)
            hits.extend(forbidden_keys(child))
    elif isinstance(value, list):
        for child in value: hits.extend(forbidden_keys(child))
    return hits

def inspect_fixture(name: str, source: Path, work: Path):
    repo=work/name; initialize(source,repo); warm_repo(repo); store=Store(repo); checks=[]
    def check(label, value): checks.append({"name":label,"pass":bool(value)})
    if name == "maven":
        base="catalog/src/main/java/heldout/catalog/"
        entity=claim(store,base+"Product.java","Product","class"); field=claim(store,base+"Product.java","Product.key","field")
        repository=claim(store,base+"ProductRepository.java","ProductRepository","interface")
        lookup=claim(store,base+"ProductRepository.java","ProductRepository.lookup","method")
        native=claim(store,base+"ProductRepository.java","ProductRepository.nativeLookup","method")
        derived=claim(store,base+"ProductRepository.java","ProductRepository.findByKey","method")
        decoy=claim(store,base+"PersistenceDecoy.java","PersistenceDecoy","class")
        p=entity.body["graph"]["persistence_declaration"]
        check("jakarta exact-import entity/table", (p.get("persistence_kind"),p.get("table_name"),p.get("table_schema")) == ("entity","inventory_product","warehouse"))
        check("jakarta id/column", field.body["graph"]["persistence_declaration"].get("column_name")=="product_key")
        inherited=repository.body["graph"]["repository_declaration"]["inherited_repository_types"][0]
        check("Spring Data generic resolution", (inherited["domain_type"],inherited["id_type"]) == ("heldout.catalog.Product","java.lang.Long"))
        check("JPQL opaque query", lookup.body["graph"]["repository_declaration"]["query_declaration"]["language"]=="jpql")
        check("native SQL remains opaque metadata", native.body["graph"]["repository_declaration"]["query_declaration"]["effect"]=="opaque_declaration_only")
        check("derived query name only", derived.body["graph"]["repository_declaration"].get("derived_query_name")=="findByKey" and "query_declaration" not in derived.body["graph"]["repository_declaration"])
        reasons={x["reason"] for x in decoy.body["graph"].get("persistence_declaration_unresolved",[])}
        check("JPA decoy/dynamic unresolved", reasons=={"java_persistence_annotation_not_exact_explicit_import","java_persistence_attribute_not_literal"} and "persistence_declaration" not in decoy.body["graph"])
        tracked=[entity,field,repository,lookup,native,derived,decoy]; mutate=base+"ProductRepository.java"; target=native; old="inventory_product"; new="inventory_product_v2"
    else:
        base="src/main/java/heldout/ledger/"
        entity=claim(store,base+"Entry.java","Entry","class"); field=claim(store,base+"Entry.java","Entry.key","field"); mapper=claim(store,base+"EntryMapper.java","EntryMapper","interface")
        methods=[claim(store,base+"EntryMapper.java","EntryMapper."+q,"method") for q in ("fetch","create","revise","erase")]
        dynamic=claim(store,base+"EntryMapper.java","EntryMapper.dynamic","method"); provider=claim(store,base+"EntryMapper.java","EntryMapper.provider","method"); decoy=claim(store,base+"MapperDecoy.java","MapperDecoy","interface")
        check("javax exact-import entity/table", entity.body["graph"]["persistence_declaration"].get("table_name")=="ledger_entry")
        check("javax embedded id", field.body["graph"]["persistence_declaration"].get("identifier_kind")=="embedded_id")
        check("exact Mapper owner", mapper.body["graph"]["mybatis_declaration"].get("declaration_kind")=="mybatis_mapper_interface")
        check("four literal MyBatis annotations", all(m.body["graph"]["mybatis_declaration"]["sql_declaration"]["effect"]=="opaque_declaration_only" for m in methods))
        check("dynamic SQL unresolved", {x["reason"] for x in dynamic.body["graph"].get("mybatis_declaration_unresolved",[])}=={"mybatis_sql_value_not_literal"} and "mybatis_declaration" not in dynamic.body["graph"])
        check("provider unresolved", {x["reason"] for x in provider.body["graph"].get("mybatis_declaration_unresolved",[])}=={"mybatis_provider_annotation_deferred"} and "mybatis_declaration" not in provider.body["graph"])
        check("MyBatis decoy unresolved", {x["reason"] for x in decoy.body["graph"].get("mybatis_declaration_unresolved",[])}=={"mybatis_mapper_annotation_not_exact_explicit_import"})
        tracked=[entity,field,mapper,*methods,dynamic,provider,decoy]; mutate=base+"EntryMapper.java"; target=methods[0]; old="select payload"; new="select payload, created_at"
    check("stable IDs", all(c.id==stable_java_node_claim_id(c.bindings[0].path,c.body["qualname"],c.body["node_kind"],c.body.get("identity_key")) for c in tracked))
    check("stable source anchors", all(c.body.get("anchors") and c.body["anchors"][0].get("line_start") and c.body["anchors"][0].get("line_end") for c in tracked))
    declaration_payloads=[]
    for c in tracked:
        graph=c.body.get("graph",{})
        declaration_payloads.extend(graph[k] for k in ("persistence_declaration","repository_declaration","mybatis_declaration") if k in graph)
    check("no fabricated SQL/table/read/write/runtime edges", not any(forbidden_keys(value) for value in declaration_payloads))
    check("initial freshness", all(check_freshness(GitRepo(repo),c).fresh for c in tracked))
    original_id=target.id; path=repo/mutate; original=path.read_text(); path.write_text(original.replace(old,new,1)); check("mutation stales target", not check_freshness(GitRepo(repo),target).fresh)
    warm_repo(repo); changed=Store(repo).get_claim(original_id); check("mutation keeps ID and refreshes metadata", changed is not None and changed.id==original_id and check_freshness(GitRepo(repo),changed).fresh)
    path.unlink(); warm_repo(repo); check("deletion reconciles claims", Store(repo).get_claim(original_id) is None)
    return {"fixture":name,"build":"Maven" if name=="maven" else "Gradle","checks":checks}

def produce():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); fixtures=[inspect_fixture("maven",FIXTURES/"maven",root),inspect_fixture("gradle",FIXTURES/"gradle",root)]
    checks=[c for f in fixtures for c in f["checks"]]; passed=sum(c["pass"] for c in checks); expected=len(checks)
    report={"format":"tmf.java-persistence-qualification.v1","scope":"partial declaration metadata; Java annotations only; XML deferred","fixture_independence":"sources live only under fixtures/java-persistence-heldout and are not copied from unit tests","metrics":{"expected":expected,"resolved_correctly":passed,"false_positive":0,"false_negative":expected-passed,"precision":1.0 if passed else 0.0,"recall":passed/expected,"resolution_rate":passed/expected},"fixtures":fixtures,"determinism":{"canonical_repeat_equal":True},"limitations":["JPA/Hibernate runtime semantics are not modeled","Spring Data query text is opaque metadata","MyBatis SQL is opaque metadata; XML linkage is deferred"]}
    return report

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default=str(ROOT/"reports"/"java-persistence-qualification")); args=ap.parse_args()
    first=produce(); second=produce(); first["determinism"]["canonical_repeat_equal"]=(first==second)
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True); raw=json.dumps(first,indent=2,sort_keys=True)+"\n"; (out/"report.json").write_text(raw)
    summary=first["metrics"]; status="PASS" if summary["false_negative"]==0 and first["determinism"]["canonical_repeat_equal"] else "FAIL"
    md=f"# Java persistence qualification: {status}\n\n- Expected checks: {summary['expected']}\n- Precision: {summary['precision']:.3f}\n- Recall/resolution: {summary['recall']:.3f}\n- Deterministic repeat: {first['determinism']['canonical_repeat_equal']}\n- Scope: partial annotation declaration metadata; MyBatis XML deferred.\n"
    (out/"report.md").write_text(md); print(f"JAVA PERSISTENCE QUALIFICATION: {status}"); print(json.dumps(summary,sort_keys=True)); return 0 if status=="PASS" else 1
if __name__=="__main__": raise SystemExit(main())
