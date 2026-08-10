from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,resolve_java_controller_advice_declarations
from tmf.ids import stable_controller_advice_declaration_claim_id
FIX=ROOT/'fixtures/java-controller-advice-heldout'
def scan():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();s=p.read_text();a,u=resolve_java_controller_advice_declarations(rel,s,extract_java_classes(rel,s));out += [(x.owner_qualname,x.owner_kind,x.owner_id,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=scan(),scan();p=FIX/'maven/src/main/java/heldout/web/Advice.java';s=p.read_text();rel=p.relative_to(FIX).as_posix()
def one(x):return resolve_java_controller_advice_declarations(rel,x,extract_java_classes(rel,x))[0]
before=one(s);mut=one(s.replace('@ControllerAdvice class GlobalAdvice {}','@ControllerAdvice("dynamic") class GlobalAdvice {}'));deleted=one(s.replace('@ControllerAdvice class GlobalAdvice {}\n',''))
checks={'maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file(),'four_direct_declarations':len(a)==4,'class_and_interface':{x[1] for x in a}=={'class','interface'},'precise_anchors':all(x[4]>0 and x[5]>=x[4] for x in a),'stable_ids':stable_controller_advice_declaration_claim_id(next(x.owner_id for x in before if x.owner_qualname=='AdviceContract'))==stable_controller_advice_declaration_claim_id(mut[0].owner_id),'mutation_freshness':len(mut)==1,'deletion_reconcile':len(deleted)==1,'wildcard_negative':any('not_exact' in x for x in u),'deterministic':(a,u)==(b,v)}
ok=all(checks.values());print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True));raise SystemExit(0 if ok else 1)
