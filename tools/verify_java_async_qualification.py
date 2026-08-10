from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,extract_java_methods,resolve_java_async_declarations
FIX=ROOT/'fixtures/java-async-heldout'
def produce():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_async_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s));out += [(x.owner_qualname,x.owner_kind,x.executor_qualifier,x.annotation_hash) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=produce(),produce();checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'three_direct_declarations':len(a)==3,'class_literal':any(x[:3]==('Workers','class','bulkPool') for x in a),'overload_safe':len({x[3] for x in a if x[0]=='Workers.refresh'})==2,'dynamic_unresolved':any(x in u for x in {'spring_async_value_not_literal_string','spring_async_executor_not_literal_string'}),'decoy_excluded':all(x[0]!='Decoy.fake' for x in a),'deterministic':(a,u)==(b,v)};ok=all(checks.values());report={'format':'tmf.java-async-qualification.v1','checks':checks,'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['direct exact-import source @Async metadata only','literal executor qualifier retained opaquely','no runtime calls, executor resolution, threads, scheduling, proxy, exception, ordering, EnableAsync, inheritance, composition, or external symbols']};d=ROOT/'reports/java-async-qualification';d.mkdir(parents=True,exist_ok=True);(d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');(d/'report.md').write_text(f"# Java Async qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n");print(json.dumps(report,sort_keys=True));raise SystemExit(0 if ok else 1)
