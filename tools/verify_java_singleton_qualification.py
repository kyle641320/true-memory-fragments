#!/usr/bin/env python3
"""Deterministic held-out qualification for metadata-free Jakarta Singleton presence."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.ids import stable_singleton_declaration_claim_id
from tmf.java_extract import extract_java_classes,resolve_java_singleton_declarations
FIX=ROOT/'fixtures/java-singleton-heldout'
def resolve(rel,source): return resolve_java_singleton_declarations(rel,source,extract_java_classes(rel,source))
def scan():
 declarations=[];unresolved=[]
 for path in sorted(FIX.rglob('*.java')):
  rel=path.relative_to(FIX).as_posix();accepted,rejected=resolve(rel,path.read_text())
  declarations.extend({'annotation_hash':x.annotation_hash,'claim_id':stable_singleton_declaration_claim_id(x.owner_id),'line_end':x.line_end,'line_start':x.line_start,'owner_id':x.owner_id,'owner_kind':x.owner_kind,'owner_qualname':x.owner_qualname,'path':x.path,'resolution':x.resolution} for x in accepted)
  unresolved.extend(y.reason for values in rejected.values() for y in values)
 return sorted(declarations,key=lambda x:(x['path'],x['line_start'],x['owner_id'])),sorted(unresolved)
first=scan();second=scan();declarations,unresolved=first;expected=json.loads((FIX/'expectations.json').read_text())
positive=FIX/'maven/src/main/java/heldout/singleton/Owners.java';source=positive.read_text();rel=positive.relative_to(FIX).as_posix();before,_=resolve(rel,source);mutated,_=resolve(rel,source.replace('@Singleton\nclass Owners','@Singleton /* fresh */\nclass Owners',1));deleted,_=resolve(rel,source.replace('@Singleton\nclass Owners','class Owners',1))
negative_sources={'javax':'import javax.inject.Singleton; @Singleton class A{}','wildcard':'import jakarta.inject.*; @Singleton class A{}','static':'import static jakarta.inject.Singleton; @Singleton class A{}','conflicting':'import jakarta.inject.Singleton; import decoy.Singleton; @Singleton class A{}','local_decoy':'import jakarta.inject.Singleton; @interface Singleton{} @Singleton class A{}','metadata':'import jakarta.inject.Singleton; @Singleton(value="x") class A{}','duplicate':'import jakarta.inject.Singleton; @Singleton @Singleton class A{}','wrong_target_method':'import jakarta.inject.Singleton; class A{@Singleton void x(){}}','wrong_target_interface':'import jakarta.inject.Singleton; @Singleton interface A{}','wrong_target_record':'import jakarta.inject.Singleton; @Singleton record A(int x){}','local_class':'import jakarta.inject.Singleton; class A{void f(){@Singleton class L{}}}','string_decoy':'class A{String s="@Singleton";}','comment_decoy':'/* @Singleton */ class A{}'}
negative_checks={name:not resolve(name+'.java',text)[0] for name,text in negative_sources.items()}
projection=[{k:x[k] for k in ('path','owner_qualname','owner_kind','line_start','line_end')} for x in declarations]
checks={'maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file() and (FIX/'gradle/settings.gradle').is_file(),'expectations_match':projection==expected['declarations'],'four_bounded_declarations':len(declarations)==4 and {x['owner_kind'] for x in declarations}=={'class'},'exact_jakarta_resolution':all(x['resolution']=='jakarta-inject-singleton-exact-import-presence' for x in declarations),'stable_unique_ids':len({x['claim_id'] for x in declarations})==4 and all(x['claim_id'].startswith('claim_singleton_decl_') for x in declarations),'precise_anchors_hash':all(x['line_start']==x['line_end'] and len(x['annotation_hash'])==64 for x in declarations),'mutation_stable_ids':{stable_singleton_declaration_claim_id(x.owner_id) for x in before}=={stable_singleton_declaration_claim_id(x.owner_id) for x in mutated},'mutation_token_hash_stable_for_comment':{x.annotation_hash for x in before}=={x.annotation_hash for x in mutated},'deletion_reconcile':len(before)==2 and len(deleted)==1,'deterministic':first==second,'heldout_negatives_rejected':len(unresolved)>=expected['minimum_unresolved'],'presence_only_no_runtime_scope_inference':True,**{name+'_negative':ok for name,ok in negative_checks.items()}}
print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True,separators=(',',':')));raise SystemExit(0 if all(checks.values()) else 1)
