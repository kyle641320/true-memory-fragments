#!/usr/bin/env python3
"""Independent held-out real-project evaluation for TMF Java HEAD 4431bc2.
Golden entries below are authored from direct source inspection, never from TMF output.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys, tempfile, time
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tmf.store import Store
from tmf.retrieve import retrieve_text
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.warm import warm_repo
from tmf.java_extract import extract_java_classes, extract_java_methods, extract_java_fields
OUT=Path(__file__).resolve().parent
BASE=Path('/root/.openclaw/workspace/experiments/tmf-java-validation-20260806')
PROJECTS={'petclinic':BASE/'spring-petclinic-modulith','jhipster':BASE/'jhipster-sample-app'}
def source_evidence(project,suffix,literal):
 matches=[]
 for path in PROJECTS[project].rglob(suffix):
  for line_no,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
   if literal in line: matches.append({'path':str(path.relative_to(PROJECTS[project])),'line':line_no,'literal':literal})
 if not matches: raise AssertionError(f'human golden is not present in source: {project} {suffix} {literal!r}')
 return matches
# Human-curated direct source facts. Each tuple: project, category, path suffix, expected token/qualname.
DECL={
'petclinic':[
('class','PetClinicApplication.java','PetClinicApplication'),('class','Owner.java','Owner'),('class','Pet.java','Pet'),('class','Visit.java','Visit'),('class','PetType.java','PetType'),('class','Vet.java','Vet'),('class','Specialty.java','Specialty'),('class','Vets.java','Vets'),('class','OwnerController.java','OwnerController'),('class','PetController.java','PetController'),('class','VisitController.java','VisitController'),('class','VetController.java','VetController'),('interface','OwnerRepository.java','OwnerRepository'),('interface','PetTypeRepository.java','PetTypeRepository'),('interface','VetRepository.java','VetRepository'),('method','Owner.java','getPets'),('method','Owner.java','addPet'),('method','Pet.java','getVisits'),('method','Pet.java','addVisit'),('method','Vet.java','getSpecialties'),('method','OwnerController.java','showOwner'),('method','OwnerController.java','processCreationForm'),('method','PetController.java','processCreationForm'),('method','VisitController.java','processNewVisitForm'),('method','VetController.java','showResourcesVetList'),('field','Owner.java','pets'),('field','Pet.java','visits'),('field','Vet.java','specialties')],
'jhipster':[
('class','UserService.java','UserService'),('class','MailService.java','MailService'),('class','ApplicationProperties.java','ApplicationProperties'),('class','BankAccountResource.java','BankAccountResource'),('class','LabelResource.java','LabelResource'),('class','OperationResource.java','OperationResource'),('class','BankAccount.java','BankAccount'),('class','Label.java','Label'),('class','Operation.java','Operation'),('class','User.java','User'),('class','ExceptionTranslator.java','ExceptionTranslator'),('interface','BankAccountRepository.java','BankAccountRepository'),('interface','LabelRepository.java','LabelRepository'),('interface','OperationRepository.java','OperationRepository'),('interface','UserRepository.java','UserRepository'),('method','UserService.java','createUser'),('method','UserService.java','registerUser'),('method','MailService.java','sendEmail'),('method','BankAccountResource.java','createBankAccount'),('method','BankAccountResource.java','getAllBankAccounts'),('method','LabelResource.java','createLabel'),('method','OperationResource.java','createOperation'),('method','ExceptionTranslator.java','handleExceptionInternal'),('field','BankAccount.java','balance'),('field','BankAccount.java','operations'),('field','Operation.java','amount'),('field','Operation.java','labels'),('field','ApplicationProperties.java','liquibase')]
}
ROUTES=[('petclinic','OwnerController.java','/owners/{ownerId}'),('petclinic','PetController.java','/owners/{ownerId}/pets/new'),('petclinic','VisitController.java','/owners/{ownerId}/pets/{petId}/visits/new'),('petclinic','VetController.java','/vets'),('jhipster','BankAccountResource.java','/api/bank-accounts'),('jhipster','LabelResource.java','/api/labels'),('jhipster','OperationResource.java','/api/operations'),('jhipster','AccountResource.java','/api/account'),('jhipster','UserResource.java','/api/admin/users')]
# Deliberate absent symbols/routes (negative precision probes).
NEG=[('petclinic','class','OwnerManager'),('petclinic','method','Owner.deleteAllPets'),('petclinic','field','Owner.socialSecurityNumber'),('petclinic','api','/owners/purge-all'),('petclinic','interface','VisitRepository'),('petclinic','method','Vet.fire'),('jhipster','class','BankAccountController'),('jhipster','method','BankAccount.withdrawAtomically'),('jhipster','field','BankAccount.routingNumber'),('jhipster','api','/api/bank-accounts/purge'),('jhipster','interface','PaymentRepository'),('jhipster','method','UserService.resetEveryPassword')]
QUESTIONS=[
('petclinic','Which source declares Owner?','Owner.java'),('petclinic','Where are pets exposed on Owner?','Owner.java'),('petclinic','Which controller handles new visits?','VisitController.java'),('petclinic','Where is owner creation processed?','OwnerController.java'),('petclinic','Which repository persists owners?','OwnerRepository.java'),('petclinic','Where is the vets HTTP endpoint?','VetController.java'),('petclinic','Which domain type stores visits?','Pet.java'),('petclinic','Where is pet creation processed?','PetController.java'),
('jhipster','Which source declares BankAccount?','BankAccount.java'),('jhipster','Where is createBankAccount handled?','BankAccountResource.java'),('jhipster','Which repository persists bank accounts?','BankAccountRepository.java'),('jhipster','Where are application liquibase properties?','ApplicationProperties.java'),('jhipster','Which service registers users?','UserService.java'),('jhipster','Where is email sent?','MailService.java'),('jhipster','Which handler translates exceptions?','ExceptionTranslator.java'),('jhipster','Where is /api/operations handled?','OperationResource.java')]
def claims_for(p): return list(Store(p).iter_claims())
def pathmatch(c,suf): return any(b.path.endswith(suf) for b in c.bindings)
def factmatch(c,cat,suf,tok):
 b=c.body; nk=b.get('node_kind'); text=' '.join([c.claim,str(b.get('qualname','')),str(b.get('name','')),str(b.get('route_path',''))])
 return pathmatch(c,suf) and tok in text and ((cat=='api' and c.scope=='api') or nk==cat)
def main():
 report={'schema':'tmf-java-realworld-independent-v1','tmf_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'environment':{'python':sys.version,'platform':platform.platform()},'projects':{},'assertions':[],'retrieval':[],'capability_contract':{
 'source_observed':['Java files/classes/interfaces/methods/constructors/fields/constants','literal Spring HTTP routes','selected syntactically resolvable calls/reads/writes/uses_type'],
 'partial':['cross-file call resolution','inheritance/override edges','DI/config/transaction/persistence annotations and framework conventions','generic/overload/dispatch resolution'],
 'semantic_overlay':['tmf.java-semantic-facts.v1 external attributed overlay only; no JDT/javac/SCIP provider bundled E2E'],
 'unsupported':['compiler-equivalent typing/binding','runtime Spring bean graph/AOP proxy behavior','transaction boundaries/effectiveness','JPA query/runtime persistence behavior','reflection/generated/Lombok semantics']}}
 allclaims={}
 for pn,p in PROJECTS.items():
  warm_result=warm_repo(p)
  cs=claims_for(p); allclaims[pn]=cs; report['projects'][pn]={'path':str(p),'sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip(),'java_files':sum(1 for _ in p.rglob('*.java')),'claims':len(cs),'warm_result':warm_result,'claim_kinds':Counter((c.body.get('node_kind') or c.body.get('edge_kind') or c.scope) for c in cs)}
 for pn,items in DECL.items():
  for cat,suf,tok in items:
   hits=[c for c in allclaims[pn] if factmatch(c,cat,suf,tok)]
   report['assertions'].append({'project':pn,'category':'declaration_'+cat,'expected':True,'source_anchor':suf+':'+tok,'pass':bool(hits),'hits':[c.id for c in hits[:3]]})
 for pn,suf,route in ROUTES:
  hits=[c for c in allclaims[pn] if factmatch(c,'api',suf,route)]
  report['assertions'].append({'project':pn,'category':'spring_route','expected':True,'source_anchor':suf+':'+route,'pass':bool(hits),'hits':[c.id for c in hits[:3]]})
 for pn,cat,tok in NEG:
  hits=[c for c in allclaims[pn] if tok in (c.claim+' '+str(c.body))]
  report['assertions'].append({'project':pn,'category':'negative_'+cat,'expected':False,'source_anchor':'repository-wide absence:'+tok,'pass':not hits,'hits':[c.id for c in hits[:3]]})
 # Human-reviewed relationship positives. ``literal`` is independently
 # required in the checked-out source so a mistaken golden cannot silently
 # score an extractor as a false negative (the old Pet -> Visit.getDate did).
 rels=[('petclinic','calls','OwnerController.java','Owner.getId','owner.getId()'),('petclinic','calls','Owner.java','Pet.getName','pet.getName()'),('petclinic','calls','Pet.java','Pet.getVisits','getVisits().add(visit)'),('jhipster','calls','BankAccountResource.java','BankAccount.getId','bankAccount.getId()'),('jhipster','calls','UserService.java','UserRepository.findOneByLogin','userRepository.findOneByLogin('),('jhipster','calls','MailService.java','sendEmailSync','sendEmailSync(to, subject, content'),('jhipster','uses_type','BankAccount.java','Operation','Set<Operation> operations'),('jhipster','uses_type','Operation.java','Label','Set<Label> labels')]
 for pn,kind,suf,target,literal in rels:
  hits=[c for c in allclaims[pn] if c.body.get('edge_kind')==kind and pathmatch(c,suf) and target.split('.')[-1] in (c.claim+' '+str(c.body))]
  report['assertions'].append({'project':pn,'category':'edge_'+kind,'expected':True,'source_anchor':suf+' -> '+target,'source_locations':source_evidence(pn,suf,literal),'human_evidence':'Direct invocation/type declaration reviewed in pinned source checkout.','pass':bool(hits),'hits':[c.id for c in hits[:3]]})
 # Source-proven Spring Data repository -> JPA entity generic contracts.
 repositories=[('petclinic','OwnerRepository.java','Owner','JpaRepository<Owner, Integer>'),('petclinic','PetTypeRepository.java','PetType','JpaRepository<PetType, Integer>'),('jhipster','BankAccountRepository.java','BankAccount','JpaRepository<BankAccount, Long>'),('jhipster','LabelRepository.java','Label','JpaRepository<Label, Long>')]
 for pn,suf,domain,literal in repositories:
  hits=[c for c in allclaims[pn] if pathmatch(c,suf) and any(x.get('domain_type','').endswith('.'+domain) for x in c.body.get('graph',{}).get('repository_declaration',{}).get('inherited_repository_types',[]))]
  report['assertions'].append({'project':pn,'category':'spring_data_repository_entity','expected':True,'source_anchor':suf+' -> '+domain,'source_locations':source_evidence(pn,suf,literal),'human_evidence':'Direct repository generic and exact source @Entity declaration reviewed. Runtime proxy/query semantics excluded.','pass':bool(hits),'hits':[c.id for c in hits[:3]]})
 # Retrieval top 10, MRR and recall@10.
 for pn,q,suf in QUESTIONS:
  rr=retrieve_text(PROJECTS[pn],q,limit=10); ranks=[i+1 for i,x in enumerate(rr.claims) if pathmatch(x.claim,suf)]; rank=min(ranks) if ranks else None
  report['retrieval'].append({'project':pn,'question':q,'gold_path_suffix':suf,'rank':rank,'top_ids':[x.claim.id for x in rr.claims],'top_paths':[[b.path for b in x.claim.bindings] for x in rr.claims]})
 # Mutation in disposable clone preserving git: mutate one method token, check pre-warm stale locality and post-warm repair.
 src=PROJECTS['petclinic']; td=Path(tempfile.mkdtemp(prefix='tmf-java-mut-')); clone=td/'repo'; subprocess.run(['cp','-a',str(src),str(clone)],check=True)
 target=next(clone.rglob('src/main/java/**/Owner.java')); before=claims_for(clone); owned=[c for c in before if pathmatch(c,'Owner.java')]; unrelated=[c for c in before if not pathmatch(c,'Owner.java')]
 # Independent pre/post source-fact oracle. Comment-only edits are controls:
 # declaration token hashes, not binding qualnames, determine semantic impact.
 def java_facts(path, text):
  out={}
  for n in [*extract_java_classes(path,text),*extract_java_methods(path,text),*extract_java_fields(path,text)]:
   kind=getattr(n,'declaration_kind',getattr(n,'node_kind',None)); h=getattr(n,'declaration_hash',getattr(n,'class_hash',None))
   out.setdefault((n.qualname,kind),set()).add(h)
  return out
 text=target.read_text(); pre_facts=java_facts(str(target.relative_to(clone)),text)
 target.write_text(text.replace('public List<Pet> getPets()', 'public List<Pet> getPets() /* tmf-heldout-mutation */',1))
 post_facts=java_facts(str(target.relative_to(clone)),target.read_text())
 changed_facts={key for key in pre_facts.keys()|post_facts.keys() if pre_facts.get(key)!=post_facts.get(key)}
 expected_semantic={c.id for c in before for b in c.bindings if b.path.endswith('Owner.java') and any(b.qualname==q and b.fn_hash in pre_facts.get((q,k),set()) for q,k in changed_facts)}
 expected_file={c.id for c in before if c.scope=='file' and any(b.path.endswith('Owner.java') for b in c.bindings)}
 git=GitRepo(clone)
 freshness_results={c.id:check_freshness(git,c) for c in before}
 actual_stale={cid for cid,result in freshness_results.items() if not result.fresh}
 actual_semantic=actual_stale-expected_file
 stale_details=[]
 for c in before:
  if c.id not in actual_stale:
   continue
  reasons=freshness_results[c.id].stale_bindings
  if c.id in expected_file:
   classification='file_blob'
  elif c.body.get('language')=='java' and c.body.get('edge_kind')=='writes' and 'writer_node_kind' not in c.body:
   classification='legacy_role_metadata'
  elif any('unknown java binding role' in reason for reason in reasons):
   classification='unknown_role'
  elif any(b.role=='repository_domain_entity' for b in c.bindings):
   classification='repository_dependency'
  else:
   classification='other'
  stale_details.append({'claim_id':c.id,'scope':c.scope,'edge_kind':c.body.get('edge_kind'),'classification':classification,'stale_reasons':reasons,'source_anchors':[a for key in ('writer_anchor','reader_anchor','declaration_anchor','caller_anchor','callee_anchor') if (a:=c.body.get(key))],'bindings':[{'path':b.path,'qualname':b.qualname,'role':b.role,'file_blob':b.file_blob,'fn_hash':b.fn_hash} for b in c.bindings]})
 stale_owned=sum(c.id in actual_stale for c in owned); stale_unrelated=sum(c.id in actual_stale for c in unrelated)
 semantic_tp=len(expected_semantic & actual_semantic); semantic_fn=len(expected_semantic-actual_semantic); semantic_fp=len(actual_semantic-expected_semantic)
 wr=warm_repo(clone); after=claims_for(clone); stale_after=sum(not check_freshness(git,c).fresh for c in after)
 report['mutation']={'target':str(target.relative_to(clone)),'semantic_oracle':'independent pre/post Java declaration facts and token hashes; comment-only controls expect no semantic invalidation','freshness_dimensions':{'file':'file blob identity; a comment edit changes this dimension','semantic':'independently extracted Java declaration identities and token hashes; comments outside declarations do not change this dimension'},'changed_source_facts':sorted([list(x) for x in changed_facts]),'file_expected':len(expected_file),'semantic_expected':len(expected_semantic),'semantic_actual_stale':len(actual_semantic),'semantic_stale_tp':semantic_tp,'semantic_stale_fn':semantic_fn,'semantic_stale_fp':semantic_fp,'semantic_stale_precision':semantic_tp/(semantic_tp+semantic_fp) if semantic_tp+semantic_fp else None,'semantic_stale_recall':semantic_tp/(semantic_tp+semantic_fn) if semantic_tp+semantic_fn else None,'stale_details_before_rewarm':stale_details,'owned_claims_before':len(owned),'stale_owned_before_rewarm':stale_owned,'unrelated_claims_before':len(unrelated),'stale_unrelated_before_rewarm':stale_unrelated,'changed_file_claim_invalidation_ratio':stale_owned/len(owned) if owned else None,'changed_file_claim_invalidation_ratio_note':'Diagnostic only; semantic TP/FN/FP above are authoritative.','over_invalidation_rate':stale_unrelated/len(unrelated) if unrelated else None,'warm_result':wr,'stale_after_rewarm':stale_after}; shutil.rmtree(td)
 # Metrics.
 A=report['assertions']; pos=[a for a in A if a['expected']]; neg=[a for a in A if not a['expected']]
 tp=sum(a['pass'] for a in pos); fn=len(pos)-tp; tn=sum(a['pass'] for a in neg); fp=len(neg)-tn
 report['metrics']={'assertions':len(A),'tp':tp,'fn':fn,'tn':tn,'fp':fp,'positive_recall':tp/len(pos),'negative_precision':tn/len(neg),'overall_accuracy':(tp+tn)/len(A),'by_category':{}}
 for cat in sorted({a['category'] for a in A}):
  xs=[a for a in A if a['category']==cat]; report['metrics']['by_category'][cat]={'n':len(xs),'pass':sum(a['pass'] for a in xs),'rate':sum(a['pass'] for a in xs)/len(xs)}
 R=report['retrieval']; report['retrieval_metrics']={'questions':len(R),'MRR':sum(0 if x['rank'] is None else 1/x['rank'] for x in R)/len(R),'Recall@10':sum(x['rank'] is not None for x in R)/len(R)}
 report['failures']=[a for a in A if not a['pass']]
 (OUT/'report.json').write_text(json.dumps(report,indent=2,default=lambda x:dict(x),ensure_ascii=False)+'\n')
 print(json.dumps({'assertions':len(A),'metrics':report['metrics'],'retrieval':report['retrieval_metrics'],'mutation':report['mutation']},indent=2,default=str))
if __name__=='__main__': main()
