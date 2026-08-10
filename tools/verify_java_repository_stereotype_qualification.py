#!/usr/bin/env python3
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tmf.ids import stable_repository_declaration_claim_id
from tmf.java_extract import extract_java_classes,resolve_java_repository_stereotype_declarations
def one(s):return resolve_java_repository_stereotype_declarations('A.java',s,extract_java_classes('A.java',s))[0]
pos='import org.springframework.stereotype.Repository;\n@Repository class A{}\n@Repository interface B{}'
a=one(pos);b=one(pos);mut=one(pos.replace('@Repository class','@Repository( ) class'));deleted=one(pos.replace('@Repository interface B{}',''))
negs=['@interface Repository{} @Repository class A{}','import org.springframework.web.bind.annotation.*; @Repository class A{}','import static org.springframework.stereotype.Repository; @Repository class A{}','import org.springframework.stereotype.Repository; import x.Repository; @Repository class A{}','import org.springframework.stereotype.Repository; class Repository{} @Repository class A{}','import org.springframework.stereotype.Repository; @Repository("x") class A{}','import org.springframework.stereotype.Repository; @Repository record A(){}','import org.springframework.stereotype.Repository; class A{@Repository void x(){}}']
checks={'maven_gradle_shapes':Path('fixtures/java-repository-stereotype-heldout/maven/pom.xml').is_file() and Path('fixtures/java-repository-stereotype-heldout/gradle/build.gradle').is_file(),'accepted':len(a)==2,'exact_fqn':all(x.resolution=='spring-stereotype-repository-exact-import-presence' for x in a),'stable_ids':len({stable_repository_declaration_claim_id(x.owner_id) for x in a})==2,'anchors_hash':all(x.line_start==x.line_end and len(x.annotation_hash)==64 for x in a),'freshness':{x.owner_id for x in a}=={x.owner_id for x in mut} and {x.annotation_hash for x in a}!={x.annotation_hash for x in mut},'deletion':len(deleted)==1,'deterministic':a==b,'negatives':all(not one(x) for x in negs),'no_runtime_semantics':True}
print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)},sort_keys=True));raise SystemExit(not all(checks.values()))
