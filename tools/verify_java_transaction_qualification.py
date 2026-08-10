#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,extract_java_methods,resolve_java_transaction_declarations
FIX=ROOT/'fixtures/java-transaction-heldout'
def produce():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_transaction_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s));out += [(x.owner_qualname,x.owner_kind,x.propagation,x.timeout,x.transaction_manager,x.rollback_for,x.no_rollback_for_class_name,x.annotation_hash) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=produce(),produce();checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'two_direct_declarations':len(a)==2,'method_literal_metadata':any(x[0]=='Services.save' and x[2]=='REQUIRES_NEW' and x[3]=='30' for x in a),'class_manager':any(x[0]=='Services' and x[4]=='main' for x in a),'dynamic_unresolved':'spring_transaction_timeout_not_literal_int' in u,'decoy_excluded':all(x[0]!='Decoy.fake' for x in a),'deterministic':(a,u)==(b,v)};ok=all(checks.values());report={'format':'tmf.java-transaction-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['direct exact-import source annotation metadata only','literal values retained opaquely','no transaction boundary, database effect, rollback behavior, proxying, propagation execution, manager resolution, call graph, inheritance, composition, or runtime semantics']};d=ROOT/'reports/java-transaction-qualification';d.mkdir(parents=True,exist_ok=True);(d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');(d/'report.md').write_text(f"# Java transaction qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n");print(json.dumps(report,sort_keys=True));raise SystemExit(0 if ok else 1)
