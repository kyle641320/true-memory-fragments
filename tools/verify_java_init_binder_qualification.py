from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.java_extract import extract_java_methods,resolve_java_init_binder_declarations
from tmf.ids import stable_init_binder_declaration_claim_id
FIX=ROOT/'fixtures/java-init-binder-heldout'
def resolve(rel,source): return resolve_java_init_binder_declarations(rel,source,extract_java_methods(rel,source))
def scan():
 out=[];bad=[]
 for p in sorted(FIX.rglob('*.java')):
  rel=p.relative_to(FIX).as_posix();a,u=resolve(rel,p.read_text());out += [(x.owner_qualname,x.owner_id,x.annotation_hash,x.line_start,x.line_end) for x in a];bad += [z.reason for v in u.values() for z in v]
 return out,bad
(a,u),(b,v)=scan(),scan();p=FIX/'maven/src/main/java/heldout/web/Binder.java';s=p.read_text();rel=p.relative_to(FIX).as_posix()
before,_=resolve(rel,s);mut,_=resolve(rel,s.replace('@InitBinder void bind()','@InitBinder( ) void bind()'));deleted,_=resolve(rel,s.replace(' @InitBinder void bind() {}\n',''))
negatives={
'wildcard':'package x; import org.springframework.web.bind.annotation.*; class A{@InitBinder void x(){}}',
'static':'package x; import static org.springframework.web.bind.annotation.InitBinder; class A{@InitBinder void x(){}}',
'conflicting':'package x; import org.springframework.web.bind.annotation.InitBinder; import decoy.InitBinder; class A{@InitBinder void x(){}}',
'local_decoy':'package x; import org.springframework.web.bind.annotation.InitBinder; class InitBinder{} class A{@InitBinder void x(){}}',
'parameter':'package x; import org.springframework.web.bind.annotation.InitBinder; class A{void x(@InitBinder String p){}}',
'nonmethod':'package x; import org.springframework.web.bind.annotation.InitBinder; @InitBinder class A{}',
}
neg_ok={k:not resolve(k+'.java',text)[0] for k,text in negatives.items()}
checks={'maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file(),'four_direct_declarations':len(a)==4,'precise_anchors':all(x[3]>0 and x[4]>=x[3] for x in a),'stable_ids':{stable_init_binder_declaration_claim_id(x.owner_id) for x in before}=={stable_init_binder_declaration_claim_id(x.owner_id) for x in mut},'mutation_freshness':len(mut)==2 and {x.annotation_hash for x in before}!={x.annotation_hash for x in mut},'deletion_reconcile':len(deleted)==1,'deterministic':(a,u)==(b,v),**{k+'_negative':ok for k,ok in neg_ok.items()}}
ok=all(checks.values());print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True));raise SystemExit(0 if ok else 1)
