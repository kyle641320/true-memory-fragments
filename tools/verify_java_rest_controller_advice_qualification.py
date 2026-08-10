from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_classes,resolve_java_rest_controller_advice_declarations
from tmf.ids import stable_rest_controller_advice_declaration_claim_id
FIX=ROOT/'fixtures/java-rest-controller-advice-heldout'
def resolve(rel,source): return resolve_java_rest_controller_advice_declarations(rel,source,extract_java_classes(rel,source))
def scan():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();a,u=resolve(rel,p.read_text());out += [(x.owner_qualname,x.owner_kind,x.owner_id,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=scan(),scan();p=FIX/'maven/src/main/java/heldout/web/Advice.java';s=p.read_text();rel=p.relative_to(FIX).as_posix()
def one(x):return resolve(rel,x)[0]
before=one(s);mut=one(s.replace('@RestControllerAdvice class GlobalAdvice {}','@RestControllerAdvice( ) class GlobalAdvice {}'));deleted=one(s.replace('@RestControllerAdvice class GlobalAdvice {}\n',''))
negatives={
 'wildcard':'package x; import org.springframework.web.bind.annotation.*; @RestControllerAdvice class A{}',
 'static':'package x; import static org.springframework.web.bind.annotation.RestControllerAdvice; @RestControllerAdvice class A{}',
 'conflicting':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; import decoy.RestControllerAdvice; @RestControllerAdvice class A{}',
 'local_decoy':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; class RestControllerAdvice{} @RestControllerAdvice class A{}',
 'metadata':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; @RestControllerAdvice("x") class A{}',
 'wrong_method':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; class A{@RestControllerAdvice void x(){}}',
 'wrong_record':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; @RestControllerAdvice record A(){}',
 'local':'package x; import org.springframework.web.bind.annotation.RestControllerAdvice; class A{void x(){@RestControllerAdvice class L{}}}',
 'decoy':'package x; @interface RestControllerAdvice{} @RestControllerAdvice class A{}'
}
neg_ok={k:not resolve(k+'.java',text)[0] for k,text in negatives.items()}
before_by={x.owner_qualname:x for x in before};mut_by={x.owner_qualname:x for x in mut}
checks={'maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file() and (FIX/'gradle/settings.gradle').is_file(),'four_direct_declarations':len(a)==4,'class_and_interface':{x[1] for x in a}=={'class','interface'},'precise_anchors_hash':all(x[4]>0 and x[5]==x[4] and len(x[3])==64 for x in a),'stable_ids':stable_rest_controller_advice_declaration_claim_id(before_by['GlobalAdvice'].owner_id)==stable_rest_controller_advice_declaration_claim_id(mut_by['GlobalAdvice'].owner_id),'mutation_freshness':before_by['GlobalAdvice'].annotation_hash!=mut_by['GlobalAdvice'].annotation_hash,'deletion_reconcile':len(deleted)==1 and deleted[0].owner_qualname=='AdviceContract','wildcard_fixture_negative':any('not_exact' in x for x in u),'deterministic':(a,u)==(b,v),**{k+'_negative':ok for k,ok in neg_ok.items()}}
ok=all(checks.values());print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True));raise SystemExit(0 if ok else 1)
