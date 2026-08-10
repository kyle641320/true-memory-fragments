#!/usr/bin/env python3
"""Deterministic held-out qualification for Spring ConfigurationProperties metadata."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from tmf.ids import stable_configuration_properties_edge_claim_id
from tmf.java_extract import extract_java_classes, extract_java_methods, resolve_java_configuration_properties
FIX=ROOT/'fixtures/java-configuration-properties-heldout'
def resolve(rel,source): return resolve_java_configuration_properties(rel,source,extract_java_classes(rel,source),extract_java_methods(rel,source))
def scan():
 bindings=[]; unresolved=[]
 for path in sorted(FIX.rglob('*.java')):
  rel=path.relative_to(FIX).as_posix(); accepted,rejected=resolve(rel,path.read_text())
  bindings += [{'claim_id':stable_configuration_properties_edge_claim_id(x.source_id,x.prefix),'path':x.source_path,'qualname':x.source_qualname,'target_kind':x.target_kind,'prefix':x.prefix,'resolution':x.resolution,'source_hash':x.source_hash} for x in accepted]
  unresolved += [x.reason for values in rejected.values() for x in values]
 return sorted(bindings,key=lambda x:(x['path'],x['qualname'])),sorted(unresolved)
first=scan(); second=scan(); bindings,unresolved=first; expected=json.loads((FIX/'expectations.json').read_text())
positive=FIX/'maven/src/main/java/heldout/configprops/Owners.java'; rel=positive.relative_to(FIX).as_posix(); source=positive.read_text(); before,_=resolve(rel,source)
mutated,_=resolve(rel,source.replace('class HttpProperties {}','class HttpProperties { String host; }'))
deleted,_=resolve(rel,source.replace('@ConfigurationProperties("app.db") record DatabaseProperties(String url) {}\n',''))
negatives={'wildcard':'import org.springframework.boot.context.properties.*; @ConfigurationProperties("x") class A{}','static':'import static org.springframework.boot.context.properties.ConfigurationProperties; @ConfigurationProperties("x") class A{}','conflicting':'import fake.ConfigurationProperties; import org.springframework.boot.context.properties.ConfigurationProperties; @ConfigurationProperties("x") class A{}','decoy':'import fake.ConfigurationProperties; @ConfigurationProperties("x") class A{}','field':'import org.springframework.boot.context.properties.ConfigurationProperties; class A{@ConfigurationProperties("x") String x;}','nonbean_factory':'import org.springframework.boot.context.properties.ConfigurationProperties; class A{@ConfigurationProperties("x") Object x(){return null;}}'}
negative_checks={k:not resolve(k+'.java',v)[0] for k,v in negatives.items()}
projection=[{k:x[k] for k in ('path','qualname','target_kind','prefix','resolution')} for x in bindings]
checks={'maven_heldout':(FIX/'maven/pom.xml').is_file(),'gradle_heldout':(FIX/'gradle/build.gradle').is_file() and (FIX/'gradle/settings.gradle').is_file(),'expectations_match':projection==sorted(expected['bindings'],key=lambda x:(x['path'],x['qualname'])),'literal_metadata_existing_support':len(bindings)==6 and {x['prefix'] for x in bindings}=={'app.http','app.db','app.worker'},'exact_fqn':all('literal' in x['resolution'] for x in bindings),'stable_ids':len({x['claim_id'] for x in bindings})==6 and all(x['claim_id'].startswith('claim_configuration_properties_edge_') for x in bindings),'anchors_hash':all(len(x['source_hash'])==64 for x in bindings),'freshness':{x.source_hash for x in before}!={x.source_hash for x in mutated} and {stable_configuration_properties_edge_claim_id(x.source_id,x.prefix) for x in before}=={stable_configuration_properties_edge_claim_id(x.source_id,x.prefix) for x in mutated},'deletion':len(before)==3 and len(deleted)==2,'deterministic':first==second,'unresolved_reasons':set(expected['unresolved_reasons'])<=set(unresolved),'no_runtime_binding_semantics':all(x.target_kind in {'class','factory_method'} for x in before),**{k+'_negative':v for k,v in negative_checks.items()}}
result={'checks':checks,'passed':sum(checks.values()),'total':len(checks)}; print(json.dumps(result,sort_keys=True,separators=(',',':'))); raise SystemExit(0 if all(checks.values()) else 1)
