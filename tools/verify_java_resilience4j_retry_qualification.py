from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,extract_java_methods,resolve_java_resilience4j_retry_declarations
from tmf.ids import stable_resilience4j_retry_declaration_claim_id
FIX=ROOT/'fixtures/java-resilience4j-retry-heldout'
def produce():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_resilience4j_retry_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s));out += [(x.owner_qualname,x.name,x.fallback_method,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=produce(),produce();src=(FIX/'src/main/java/heldout/rl/Client.java').read_text();rel='src/main/java/heldout/rl/Client.java'
def one(text):
 c=extract_java_classes(rel,text);m=extract_java_methods(rel,text);return resolve_java_resilience4j_retry_declarations(rel,text,c,m)[0]
before=one(src);mutated=one(src.replace('name="inventory"','name="stock"'));deleted=one(src.replace('@Retry(name="inventory", fallbackMethod="fallback") ',''));stable_ids=sorted(stable_resilience4j_retry_declaration_claim_id(x.owner_id) for x in before)==sorted(stable_resilience4j_retry_declaration_claim_id(x.owner_id) for x in mutated)
checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'two_direct_declarations':len(a)==2,'literal_metadata':any(x[1:3]==('inventory','fallback') for x in a),'overload_safe':len({x[3] for x in a if x[0]=='Client.fetch'})==2,'precise_anchors':all(x[4]>0 and x[5]>=x[4] for x in a),'stable_ids_under_literal_mutation':stable_ids,'mutation_changes_token_hash':sorted(x.annotation_hash for x in before)!=sorted(x.annotation_hash for x in mutated),'deletion_reconciles_declaration':len(deleted)==1,'dynamic_unresolved':any('not_literal' in x for x in u),'decoy_excluded':all(x[0]!='Decoy.fake' for x in a),'deterministic':(a,u)==(b,v)};ok=all(checks.values());report={'format':'tmf.java-resilience4j-retry-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['direct exact-import source @Retry metadata only','literal name/fallbackMethod retained opaquely','no runtime retries, backoff, exception matching, configuration, fallback dispatch, proxy/AOP, calls, inheritance, composition, or external symbols']};d=ROOT/'reports/java-resilience4j-retry-qualification';d.mkdir(parents=True,exist_ok=True);(d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');(d/'report.md').write_text(f"# Java Resilience4j Retry qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n");print(json.dumps(report,sort_keys=True));raise SystemExit(0 if ok else 1)
