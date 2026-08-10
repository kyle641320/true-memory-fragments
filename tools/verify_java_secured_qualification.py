from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,extract_java_methods,resolve_java_secured_declarations
from tmf.ids import stable_secured_declaration_claim_id
FIX=ROOT/'fixtures/java-secured-heldout'
def produce():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_secured_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s));out += [(x.owner_qualname,x.roles,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=produce(),produce();src=(FIX/'src/main/java/heldout/security/Service.java').read_text();rel='src/main/java/heldout/security/Service.java'
def one(text):return resolve_java_secured_declarations(rel,text,extract_java_classes(rel,text),extract_java_methods(rel,text))[0]
before=one(src);mutated=one(src.replace('ROLE_ADMIN','ROLE_ROOT'));deleted=one(src.replace(' @Secured("ROLE_ADMIN") void fetch() {}\n',''))
checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'two_direct_declarations':len(a)==2,'literal_metadata':any(x[1]==('ROLE_USER','ROLE_AUDITOR') for x in a),'overload_safe':len({x[2] for x in a})==2,'precise_anchors':all(x[3]>0 and x[4]>=x[3] for x in a),'stable_ids_under_literal_mutation':sorted(stable_secured_declaration_claim_id(x.owner_id) for x in before)==sorted(stable_secured_declaration_claim_id(x.owner_id) for x in mutated),'mutation_changes_token_hash':sorted(x.annotation_hash for x in before)!=sorted(x.annotation_hash for x in mutated),'deletion_reconciles_declaration':len(deleted)==1,'dynamic_unresolved':any('not_literal' in x for x in u),'decoy_excluded':all(x[0]!='Decoy.fake' for x in a),'deterministic':(a,u)==(b,v)};ok=all(checks.values());report={'format':'tmf.java-secured-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['direct exact-import source @Secured metadata only','literal role strings retained opaquely','no role hierarchy, authorization decisions, proxy/AOP, configuration, calls, inheritance, composition, aliases, meta-annotations, or runtime enforcement']};d=ROOT/'reports/java-secured-qualification';d.mkdir(parents=True,exist_ok=True);(d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');(d/'report.md').write_text(f"# Java Secured qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n");print(json.dumps(report,sort_keys=True));raise SystemExit(0 if ok else 1)
