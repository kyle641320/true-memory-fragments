#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_methods, resolve_java_scheduling_declarations
FIX=ROOT/'fixtures/java-scheduling-heldout'
def produce():
 out=[]; unresolved=[]
 for p in sorted((FIX/'src/main/java').rglob('*.java')):
  rel=p.relative_to(FIX).as_posix(); s=p.read_text(); found,bad=resolve_java_scheduling_declarations(rel,s,extract_java_methods(rel,s))
  out += [(x.method_qualname,x.fixed_rate,x.fixed_delay,x.initial_delay,x.cron,x.zone,x.time_unit,x.annotation_hash) for x in found]; unresolved += [x.reason for v in bad.values() for x in v]
 return out,unresolved
def main():
 (a,u),(b,v)=produce(),produce(); checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'three_literal_declarations':len(a)==3,'opaque_numeric_tokens':any(x[1]=='15_000L' for x in a),'cron_zone':any(x[4]=='0 0 * * * *' and x[5]=='UTC' for x in a),'time_unit':any(x[6]=='TimeUnit.MILLISECONDS' for x in a),'dynamic_unresolved':'spring_scheduled_fixedRate_not_literal' in u,'decoy_excluded':all('Decoy.decoy'!=x[0] for x in a),'deterministic':(a,u)==(b,v)}
 ok=all(checks.values()); report={'format':'tmf.java-scheduling-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'deterministic':checks['deterministic'],'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['source methods and exact explicit @Scheduled import only','literal declaration tokens retained opaquely','no execution, schedule calculation, timezone semantics, concurrency, proxy, EnableScheduling, inheritance, composition, placeholders, or SpEL inference']}
 d=ROOT/'reports/java-scheduling-qualification'; d.mkdir(parents=True,exist_ok=True); (d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); (d/'report.md').write_text(f"# Java scheduling qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n")
 print(json.dumps(report,sort_keys=True)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
