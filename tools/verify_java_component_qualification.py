#!/usr/bin/env python3
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.ids import stable_component_declaration_claim_id
from tmf.java_extract import extract_java_classes,resolve_java_component_declarations
def one(s):return resolve_java_component_declarations('A.java',s,extract_java_classes('A.java',s))[0]
def fixture_evidence():
 root=ROOT/'fixtures/java-component-heldout';positive=[];negative=[]
 for path in sorted(root.rglob('*.java')):
  rel=path.relative_to(root).as_posix();source=path.read_text();found=resolve_java_component_declarations(rel,source,extract_java_classes(rel,source))[0]
  (negative if '/testFixtures/' in rel else positive).extend(found)
 return positive,negative
pos='import org.springframework.stereotype.Component;\n@Component class A{}\n@Component interface B{}'
a=one(pos);b=one(pos);mut=one(pos.replace('@Component class','@Component( ) class'));deleted=one(pos.replace('@Component interface B{}',''))
negs=['@interface Component{} @Component class A{}','import org.springframework.web.bind.annotation.*; @Component class A{}','import static org.springframework.stereotype.Component; @Component class A{}','import org.springframework.stereotype.Component; import x.Component; @Component class A{}','import org.springframework.stereotype.Component; class Component{} @Component class A{}','import org.springframework.stereotype.Component; @Component("x") class A{}','import org.springframework.stereotype.Component; @Component record A(){}','import org.springframework.stereotype.Component; class A{@Component void x(){}}']
fixture_positive,fixture_negative=fixture_evidence()
checks={'fixture_positive_evidence':len(fixture_positive)==4,'fixture_negative_evidence':not fixture_negative,'maven_gradle_shapes':Path('fixtures/java-component-heldout/maven/pom.xml').is_file() and Path('fixtures/java-component-heldout/gradle/build.gradle').is_file(),'fixture_targeted_source':Path('fixtures/java-component-heldout/maven/src/main/java/heldout/component/ComponentOwners.java').is_file(),'accepted':len(a)==2,'exact_fqn':all(x.resolution=='spring-stereotype-component-exact-import-presence' for x in a),'stable_ids':len({stable_component_declaration_claim_id(x.owner_id) for x in a})==2,'anchors_hash':all(x.line_start==x.line_end and len(x.annotation_hash)==64 for x in a),'freshness':{x.owner_id for x in a}=={x.owner_id for x in mut} and {x.annotation_hash for x in a}!={x.annotation_hash for x in mut},'deletion':len(deleted)==1,'deterministic':a==b,'negatives':all(not one(x) for x in negs)}
print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True));raise SystemExit(not all(checks.values()))
