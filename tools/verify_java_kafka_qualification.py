#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from tmf.git import GitRepo
from tmf.freshness import check_freshness
from tmf.ids import stable_java_node_claim_id, stable_topic_pub_edge_claim_id, stable_topic_sub_edge_claim_id
from tmf.store import Store
from tmf.warm import warm_repo

def run(args,cwd): subprocess.run(args,cwd=cwd,check=True,capture_output=True)
def produce():
  with tempfile.TemporaryDirectory() as td:
    repo=Path(td)/"repo"; shutil.copytree(ROOT/"fixtures/java-kafka-heldout",repo)
    run(["git","init"],repo); run(["git","config","user.email","heldout@example.invalid"],repo); run(["git","config","user.name","TMF heldout"],repo); run(["git","add","."],repo); run(["git","commit","-m","fixture"],repo)
    warm_repo(repo); store=Store(repo); path="src/main/java/heldout/kafka/Messaging.java"
    pid=stable_java_node_claim_id(path,"Publisher.publish","method"); did=stable_java_node_claim_id(path,"Publisher.dynamic","method"); sid=stable_java_node_claim_id(path,"Subscriber.receive","method")
    pub=store.get_claim(stable_topic_pub_edge_claim_id(pid,"heldout.orders")); sub=store.get_claim(stable_topic_sub_edge_claim_id(sid,"heldout.orders")); dynamic=store.get_claim(did)
    checks={"publisher":pub and pub.body["payload_type"]=="Order" and pub.body["source_anchor"]["line_start"]==7,"subscriber":sub and sub.body["group_id"]=="heldout-billing" and sub.body["payload_type"]=="Order","dynamic_unresolved":dynamic.body["graph"]["publishes_to_unresolved"][0]["reason"]=="kafka_topic_not_literal","decoy_absent":store.get_claim(stable_topic_pub_edge_claim_id(stable_java_node_claim_id("src/main/java/heldout/kafka/Decoy.java","Decoy.send","method"),"decoy")) is None,"fresh":check_freshness(GitRepo(repo),pub).fresh and check_freshness(GitRepo(repo),sub).fresh}
    old=pub; f=repo/path; f.write_text(f.read_text().replace('"heldout.orders"','"heldout.orders.v2"',1)); checks["mutation_stales"]=not check_freshness(GitRepo(repo),old).fresh; warm_repo(repo); checks["mutation_reconciles"]=Store(repo).get_claim(pub.id) is None
    f.unlink(); run(["git","add","-A"],repo); run(["git","commit","-m","delete"],repo); warm_repo(repo); checks["deletion_reconciles"]=Store(repo).get_claim(sub.id) is None
    return checks

def main():
  a=produce(); b=produce(); report={"format":"tmf.java-kafka-qualification.v1","checks":a,"deterministic":a==b,"limitations":["source-only exact imports and literal topics","no runtime delivery, broker, serializer, partition/key/header semantics"]}; out=ROOT/"reports/java-kafka-qualification"; out.mkdir(parents=True,exist_ok=True); (out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); ok=all(a.values()) and a==b; (out/"report.md").write_text(f"# Java Kafka qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(bool(v) for v in a.values())}/{len(a)}\n- Deterministic repeat: {a==b}\n- Scope: bounded source evidence only.\n"); print(f"JAVA KAFKA QUALIFICATION: {'PASS' if ok else 'FAIL'} ({sum(bool(v) for v in a.values())}/{len(a)})"); return 0 if ok else 1
if __name__=="__main__": raise SystemExit(main())
