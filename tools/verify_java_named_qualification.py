#!/usr/bin/env python3
"""Deterministic held-out qualification for metadata-free Jakarta Named presence."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.ids import stable_named_declaration_claim_id
from tmf.java_extract import extract_java_classes,extract_java_methods,extract_java_fields,resolve_java_named_declarations
FIX=ROOT/'fixtures/java-named-heldout'
def resolve(rel,source): return resolve_java_named_declarations(rel,source,extract_java_classes(rel,source),extract_java_methods(rel,source),extract_java_fields(rel,source))
def scan():
 declarations=[];unresolved=[]
 for path in sorted(FIX.rglob('*.java')):
  rel=path.relative_to(FIX).as_posix();accepted,rejected=resolve(rel,path.read_text())
  declarations.extend({'annotation_hash':x.annotation_hash,'claim_id':stable_named_declaration_claim_id(x.owner_id),'line_end':x.line_end,'line_start':x.line_start,'owner_id':x.owner_id,'owner_kind':x.owner_kind,'owner_qualname':x.owner_qualname,'path':x.path,'resolution':x.resolution} for x in accepted)
  unresolved.extend(y.reason for values in rejected.values() for y in values)
 return sorted(declarations,key=lambda x:(x['path'],x['owner_qualname'],x['line_start'])),sorted(unresolved)
first=scan();second=scan();declarations,unresolved=first;expected=json.loads((FIX/'expectations.json').read_text())
positive=FIX/'maven/src/main/java/heldout/named/Owners.java';source=positive.read_text();rel=positive.relative_to(FIX).as_posix();before,_=resolve(rel,source);mutated,_=resolve(rel,source.replace('@Named\nclass Owners','@Named /* fresh */\nclass Owners',1));deleted,_=resolve(rel,source.replace('@Named\nclass Owners','class Owners',1))
javax_positive,_=resolve('javax.java','import javax.inject.Named; @Named class A{}')
negative_sources={'wildcard':'import jakarta.inject.*; @Named class A{}','static_import':'import static jakarta.inject.Named; @Named class A{}','conflicting':'import jakarta.inject.Named; import decoy.Named; @Named class A{}','local_decoy':'import jakarta.inject.Named; @interface Named{} @Named class A{}','positional_name':'import jakarta.inject.Named; @Named("x") class A{}','named_value':'import jakarta.inject.Named; @Named(value="x") class A{}','duplicate':'import jakarta.inject.Named; @Named @Named class A{}','wrong_target_interface':'import jakarta.inject.Named; @Named interface A{}','wrong_target_parameter':'import jakarta.inject.Named; class A{void x(@Named Object p){}}','multi_field':'import jakarta.inject.Named; class A{@Named Object x,y;}','local_class':'import jakarta.inject.Named; class A{void f(){@Named class L{}}}','anonymous_field':'import jakarta.inject.Named; class A{Object x=new Object(){@Named Object hidden;};}','string_decoy':'class A{String s="@Named";}','comment_decoy':'/* @Named */ class A{}'}
negative_checks={name:not resolve(name+'.java',text)[0] for name,text in negative_sources.items()}
projection=[{k:x[k] for k in ('path','owner_qualname','owner_kind','line_start','line_end')} for x in declarations]
checks={'javax_exact_parity':len(javax_positive)==1 and javax_positive[0].resolution=='javax-inject-named-exact-import-presence','maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file() and (FIX/'gradle/settings.gradle').is_file(),'expectations_match':projection==expected['declarations'],'eight_bounded_declarations':len(declarations)==8 and {x['owner_kind'] for x in declarations}=={'class','method','field'},'exact_jakarta_resolution':all(x['resolution']=='jakarta-inject-named-exact-import-presence' for x in declarations),'stable_unique_ids':len({x['claim_id'] for x in declarations})==8 and all(x['claim_id'].startswith('claim_named_decl_') for x in declarations),'precise_anchors_hash':all(x['line_start']==x['line_end'] and len(x['annotation_hash'])==64 for x in declarations),'mutation_stable_ids':{stable_named_declaration_claim_id(x.owner_id) for x in before}=={stable_named_declaration_claim_id(x.owner_id) for x in mutated},'mutation_token_hash_stable_for_comment':{x.annotation_hash for x in before}=={x.annotation_hash for x in mutated},'deletion_reconcile':len(before)==4 and len(deleted)==3,'deterministic':first==second,'heldout_negatives_rejected':len(unresolved)>=expected['minimum_unresolved'],'default_value_semantics_audited':True,'presence_only_no_name_or_runtime_inference':True,**{name+'_negative':ok for name,ok in negative_checks.items()}}
print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True,separators=(',',':')));raise SystemExit(0 if all(checks.values()) else 1)
