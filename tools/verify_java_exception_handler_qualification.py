from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,extract_java_methods,resolve_java_exception_handler_declarations
from tmf.ids import stable_exception_handler_declaration_claim_id
FIX=ROOT/'fixtures/java-exception-handler-heldout'
def produce():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_exception_handler_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s));out += [(x.owner_qualname,x.exception_types,x.owner_id,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=produce(),produce();p=FIX/'src/main/java/heldout/web/Advice.java';src=p.read_text();rel=p.relative_to(FIX).as_posix()
def one(s):return resolve_java_exception_handler_declarations(rel,s,extract_java_classes(rel,s),extract_java_methods(rel,s))[0]
before=one(src);mutated=one(src.replace('IllegalArgumentException','ArithmeticException'));deleted=one(src.replace(' @ExceptionHandler(IllegalArgumentException.class) void handle() {}\n',''))
checks={'maven_fixture':(FIX/'pom.xml').is_file(),'gradle_fixture':(FIX/'build.gradle').is_file(),'three_direct_declarations':len(a)==3,'literal_metadata':any(x[1]==('IllegalStateException','java.io.IOException') for x in a),'empty_metadata_retained':any(x[1]==() for x in a),'overload_safe':len({x[2] for x in a})==3,'precise_anchors':all(x[4]>0 and x[5]>=x[4] for x in a),'stable_ids_under_literal_mutation':sorted(stable_exception_handler_declaration_claim_id(x.owner_id) for x in before)==sorted(stable_exception_handler_declaration_claim_id(x.owner_id) for x in mutated),'mutation_changes_token_hash':sorted(x.annotation_hash for x in before)!=sorted(x.annotation_hash for x in mutated),'deletion_reconciles_declaration':len(deleted)==2,'dynamic_unresolved':any('not_class_literals' in x for x in u),'decoy_excluded':all(x[0]!='Decoy.fake' for x in a),'deterministic':(a,u)==(b,v)};ok=all(checks.values());report={'format':'tmf.java-exception-handler-qualification.v1','checks':checks,'passed':sum(checks.values()),'total':len(checks),'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['direct exact-import method annotation metadata only','class literals retained opaquely; empty metadata retained','no dispatch, matching, response mapping, advice scope, inheritance, aliases, calls, or runtime behavior']};d=ROOT/'reports/java-exception-handler-qualification';d.mkdir(parents=True,exist_ok=True);(d/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');(d/'report.md').write_text(f"# Java ExceptionHandler qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(checks.values())}/{len(checks)}\n");print(json.dumps(report,sort_keys=True));raise SystemExit(0 if ok else 1)
