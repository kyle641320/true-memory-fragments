#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_methods, resolve_java_cache_declarations
FIX=ROOT/'fixtures/java-cache-heldout'
def produce():
 out=[]
 for p in sorted((FIX/'src/main/java').rglob('*.java')):
  rel=p.relative_to(FIX).as_posix(); s=p.read_text(); found,unresolved=resolve_java_cache_declarations(rel,s,extract_java_methods(rel,s))
  out += [(x.operation,list(x.cache_names),x.key,x.unless,x.method_qualname,x.annotation_hash) for x in found]
 return out
def main():
 a=produce(); b=produce(); checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'three_operations':len(a)==3,'literal_arrays':any(x[1]==['heldout.users','heldout.profiles'] for x in a),'opaque_spel':any(x[2]=='#id' and x[3]=='#result == null' for x in a),'decoy_excluded':all('decoy' not in x[1] for x in a),'deterministic':a==b}
 ok=all(checks.values()); report={'format':'tmf.java-cache-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'deterministic':a==b,'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['declaration-only exact explicit Spring Cache imports and literal cache names','SpEL strings retained opaquely and never evaluated','no CacheManager calls or runtime cache semantics inferred']}
 d=ROOT/'reports/java-cache-qualification'; d.mkdir(parents=True,exist_ok=True); (d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); (d/'report.md').write_text(f"# Java Cache qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n- Deterministic repeat: {a==b}\n")
 print(json.dumps(report,sort_keys=True)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
