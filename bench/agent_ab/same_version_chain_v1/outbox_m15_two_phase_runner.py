#!/usr/bin/env python3
from __future__ import annotations
import argparse, difflib, json, re, shutil, subprocess, sys, textwrap, time
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from bench.agent_ab.adapter import JsonBrokerAdapter  # noqa:E402
from bench.agent_ab.same_version_chain_v1 import runner as base_runner  # noqa:E402
from tmf.freshness import check_freshness  # noqa:E402
from tmf.git import GitRepo  # noqa:E402
from tmf.ids import now_utc  # noqa:E402
from tmf.java_extract import extract_java_methods  # noqa:E402
from tmf.schema import Binding, Claim  # noqa:E402
MODEL=base_runner.MODEL; BROKER=base_runner.BROKER; TIMEOUT=base_runner.TIMEOUT
TAG='outbox_m15_two_phase_contract_shift'
ARMS=['SOURCE_ONLY','PREREAD_STALE_SOURCE','STALE_DOC_CONTROL','TMF_STALE_GATED']
SERVICE='src/main/java/com/example/order/OrderService.java'
PUBLISHER='src/main/java/com/example/order/EventPublisher.java'
TEST='src/test/java/com/example/order/OrderServiceContractTest.java'
HIDDEN_TEST='.m15_post_contracts/OrderServiceContractTest.java'
POM='''<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd"><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>outbox-m15</artifactId><version>1.0-SNAPSHOT</version><properties><maven.compiler.source>17</maven.compiler.source><maven.compiler.target>17</maven.compiler.target><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><dependencies><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.10.2</version><scope>test</scope></dependency></dependencies><build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version></plugin></plugins></build></project>'''
ORDER_REPO='''package com.example.order;\n\npublic interface OrderRepository {\n    void save(Order order);\n}\n'''
ORDER='''package com.example.order;\n\npublic final class Order {\n    private final long id;\n    public Order(long id) { this.id = id; }\n    public long getId() { return id; }\n}\n'''
TX='''package com.example.order;\n\nimport java.lang.annotation.ElementType;\nimport java.lang.annotation.Retention;\nimport java.lang.annotation.RetentionPolicy;\nimport java.lang.annotation.Target;\n\n@Retention(RetentionPolicy.RUNTIME)\n@Target({ElementType.METHOD, ElementType.TYPE})\npublic @interface Transactional {}\n'''
OLD_PUBLISHER='''package com.example.order;\n\npublic interface EventPublisher {\n    void publish(String event);\n}\n'''
OLD_SERVICE='''package com.example.order;\n\npublic class OrderService {\n    private final OrderRepository repository;\n    private final EventPublisher publisher;\n\n    public OrderService(OrderRepository repository, EventPublisher publisher) {\n        this.repository = repository;\n        this.publisher = publisher;\n    }\n\n    @Transactional\n    public void createOrder(Order order) {\n        repository.save(order);\n        publisher.publish("ORDER_CREATED:" + order.getId());\n    }\n}\n'''
POST_PUBLISHER='''package com.example.order;\n\npublic interface EventPublisher {\n    /**\n     * Legacy immediate publication. Still available for non-transactional maintenance flows only.\n     * Order creation events must be scheduled after commit.\n     */\n    void publish(String event);\n\n    void publishAfterCommit(String event);\n}\n'''
POST_SERVICE='''package com.example.order;\n\npublic class OrderService {\n    private final OrderRepository repository;\n    private final EventPublisher publisher;\n\n    public OrderService(OrderRepository repository, EventPublisher publisher) {\n        this.repository = repository;\n        this.publisher = publisher;\n    }\n\n    @Transactional\n    public void createOrder(Order order) {\n        persistAndPublish(order);\n    }\n\n    private void persistAndPublish(Order order) {\n        repository.save(order);\n        publisher.publish("ORDER_CREATED:" + order.getId());\n    }\n}\n'''
POST_TEST='''package com.example.order;\n\nimport static org.junit.jupiter.api.Assertions.*;\nimport java.util.ArrayList;\nimport java.util.List;\nimport org.junit.jupiter.api.Test;\n\nclass OrderServiceContractTest {\n    @Test\n    void createOrderSchedulesEventAfterCommit() {\n        FakeRepository repository = new FakeRepository();\n        FakePublisher publisher = new FakePublisher();\n        OrderService service = new OrderService(repository, publisher);\n\n        service.createOrder(new Order(42L));\n\n        assertEquals(List.of(42L), repository.saved);\n        assertEquals(List.of("ORDER_CREATED:42"), publisher.afterCommitEvents);\n        assertTrue(publisher.immediateEvents.isEmpty(), "order-created event must not publish immediately inside transaction");\n    }\n\n    static final class FakeRepository implements OrderRepository {\n        final List<Long> saved = new ArrayList<>();\n        public void save(Order order) { saved.add(order.getId()); }\n    }\n\n    static final class FakePublisher implements EventPublisher {\n        final List<String> immediateEvents = new ArrayList<>();\n        final List<String> afterCommitEvents = new ArrayList<>();\n        public void publish(String event) { immediateEvents.add(event); }\n        public void publishAfterCommit(String event) { afterCommitEvents.add(event); }\n    }\n}\n'''

def write_file(root:Path, rel:str, text:str):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
def make_repo(root:Path):
    if root.exists(): shutil.rmtree(root)
    write_file(root,'pom.xml',POM); write_file(root,'src/main/java/com/example/order/OrderRepository.java',ORDER_REPO); write_file(root,'src/main/java/com/example/order/Order.java',ORDER); write_file(root,'src/main/java/com/example/order/Transactional.java',TX); write_file(root,PUBLISHER,OLD_PUBLISHER); write_file(root,SERVICE,OLD_SERVICE); write_file(root,HIDDEN_TEST,POST_TEST); (root/'.tmf').mkdir(exist_ok=True)
    return {'fixture':'synthetic bounded Maven order-outbox contract shift','phase_a':'old publisher contract publish(event) is correct','phase_b':'publisher gains publishAfterCommit; order creation must use it'}
def mutate_to_phase_b(root:Path):
    write_file(root,PUBLISHER,POST_PUBLISHER); write_file(root,SERVICE,POST_SERVICE)
    hidden=root/HIDDEN_TEST; dst=root/TEST; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(hidden.read_text(encoding='utf-8'),encoding='utf-8')
def mvn(root:Path,args:list[str],timeout:int=120):
    r=subprocess.run(['mvn','-q',*args],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return {'ok':r.returncode==0,'exit':r.returncode,'stdout':r.stdout[-4000:],'stderr':r.stderr[-4000:]}
def mvn_compile(root): return mvn(root,['-DskipTests','compile'],90)
def mvn_test(root): return mvn(root,['test'],120)
def safe(root,rel): return base_runner.safe(root,rel)
def read_numbered(p,start=1,end=None): return base_runner.read_numbered(p,start,end)
def find_symbol_range(p,symbol): return base_runner.find_symbol_range(p,symbol)
def parse_actions(raw): return base_runner.parse_actions(raw)
def list_files(root): return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and 'target' not in p.parts and '.m15_post_contracts' not in p.parts)[:400]
def search(root,q):
    q=q.lower(); hits=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or 'target' in p.parts or '.m15_post_contracts' in p.parts or p.suffix not in {'.java','.xml','.md'}: continue
        for i,l in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1):
            if q and q in l.lower(): hits.append(f'{p.relative_to(root)}:{i}:{l}')
    return hits[:160]
def apply_edit(root,act):
    p=safe(root,str(act.get('path','')))
    if not p: return {'error':'invalid path'}
    old=str(act.get('old','')); new=str(act.get('new','')); text=p.read_text(encoding='utf-8')
    if not old: return {'error':'empty old'}
    n=text.count(old)
    if n!=1: return {'error':f'old text occurrences={n}'}
    p.write_text(text.replace(old,new),encoding='utf-8'); return {'ok':True,'path':str(p.relative_to(root)),'bytes':len(new.encode())}
def snapshot(root): return {str(p.relative_to(root)):p.read_text(encoding='utf-8',errors='replace') for p in sorted(root.rglob('*.java')) if 'target' not in p.parts and '.m15_post_contracts' not in p.parts}
def diff_files(before,root):
    out={}; files=set(before)|{str(p.relative_to(root)) for p in root.rglob('*.java') if 'target' not in p.parts and '.m15_post_contracts' not in p.parts}
    for f in sorted(files):
        old=before.get(f,''); p=root/f; new=p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''
        if old!=new: out[f]='\n'.join(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=f'a/{f}',tofile=f'b/{f}',lineterm=''))
    return out
def build_claim(root,orientation):
    src=root/SERVICE; text=src.read_text(encoding='utf-8'); method=next(m for m in extract_java_methods(SERVICE,text) if m.qualname.endswith('OrderService.createOrder'))
    blob=subprocess.check_output(['git','hash-object',str(src)],text=True).strip(); summ=(orientation or {}).get('summary') or 'createOrder saves then publishes ORDER_CREATED immediately via EventPublisher.publish.'
    return Claim(id='outbox_m15:old:OrderService.createOrder', claim='Verified old order creation workflow: OrderService.createOrder is transactional, calls repository.save(order), then calls publisher.publish("ORDER_CREATED:" + id). Immediate publish is the known event boundary. Phase-A orientation: '+str(summ), kind='structure', scope='method', bindings=[Binding(path=SERVICE,file_blob=blob,fn_hash=method.class_hash,commit=None,qualname='OrderService.createOrder',role='method',line_start=method.line_start,line_end=method.line_end,hash_kind='java_node_hash')], provenance='synthetic Phase-A claim from pre-mutation outbox-m15 fixture', evidence='verified', confidence=0.96, endorsed_by=None, last_verified=now_utc(), model='deterministic-bench', body={'language':'java','qualname':'OrderService.createOrder','task_id':'OUTBOX_M15','mutation_expected_stale':True})
def placement(root):
    svc=(root/SERVICE).read_text(encoding='utf-8',errors='replace'); pub=(root/PUBLISHER).read_text(encoding='utf-8',errors='replace')
    return {'has_after_commit_api':'publishAfterCommit' in pub,'uses_after_commit':'publishAfterCommit(' in svc,'uses_immediate_publish':bool(re.search(r'publisher\.publish\(',svc)),'helper_present':'persistAndPublish' in svc,'create_order_transactional':bool(re.search(r'@Transactional\s+public\s+void\s+createOrder',svc))}
def deterministic_test(root):
    test=mvn_test(root); pl=placement(root); reasons=[]
    if not test.get('ok'): reasons.append('mvn test failed')
    if not pl['uses_after_commit']: reasons.append('service does not use publishAfterCommit')
    if pl['uses_immediate_publish']: reasons.append('service still uses immediate publish')
    return {'ok':bool(test.get('ok')),'placement':pl,'test':test,'message':'PASS' if test.get('ok') else '; '.join(reasons)}
def run_phase_a(broker,root,max_turns):
    tools='''Available actions (respond with exactly ONE JSON object per turn, no prose):\n{"action":"list"}\n{"action":"read_range","path":"relative file","start":1,"end":220}\n{"action":"read_symbol","path":"relative .java file","symbol":"symbol name"}\n{"action":"search","query":"text"}\n{"action":"compile"}\n{"action":"orientation","summary":"brief source-derived understanding of order creation event workflow"}\n'''
    system=f'''You are orienting on a small Java service before implementation work.\nFixture root: {root}\nTask: Take a quick look at the order creation workflow and understand how order-created events are currently emitted. Do not edit yet.\nEdits and finals are not allowed in this phase. Read enough source to form a concrete orientation, then return the orientation action.\n{tools}\nBegin now.'''
    hist=[]; transcript=[]; met={'tool_calls':0,'source_reads':0,'source_bytes':0,'source_files':[],'prompt_tokens':0,'completion_tokens':0,'invalid':0,'edits_rejected':0,'compile_calls':0}; orientation=None
    for turn in range(max_turns):
        prompt=system+'\n'+('\n'.join(hist[-12:]) if hist else ''); met['prompt_tokens']+=base_runner.tok(prompt); raw=broker.answer(prompt,budget=1)['answer']; met['completion_tokens']+=base_runner.tok(raw); acts=parse_actions(raw); transcript.append({'turn':turn,'raw':raw,'actions':acts})
        if not acts: met['invalid']+=1; hist+=['AGENT:'+raw,'SYSTEM: respond with exactly one JSON action, no prose.']; continue
        act=acts[0]; a=act.get('action'); met['tool_calls']+=1
        if a=='list': out={'files':list_files(root)}
        elif a=='search': out={'hits':search(root,str(act.get('query','')))}
        elif a=='read_range':
            p=safe(root,str(act.get('path','')))
            if not p: out={'error':'invalid path'}
            else:
                st=max(1,int(act.get('start',1))); en=int(act.get('end',st+120)); content=read_numbered(p,st,en); met['source_reads']+=1; met['source_bytes']+=len(content.encode()); met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'content':content}
        elif a=='read_symbol':
            p=safe(root,str(act.get('path',''))); sym=str(act.get('symbol',''))
            if not p: out={'error':'invalid path'}
            else:
                rng=find_symbol_range(p,sym)
                if not rng: out={'error':'symbol not found'}
                else:
                    content=read_numbered(p,rng[0],rng[1]); met['source_reads']+=1; met['source_bytes']+=len(content.encode()); met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'symbol':sym,'content':content}
        elif a=='compile': met['compile_calls']+=1; out=mvn_compile(root)
        elif a=='orientation':
            if met['source_reads']<1: out={'error':'orientation rejected: read source first'}
            else: orientation=act; out={'ok':True}; transcript[-1]['tool_outputs']=[{'action':act,'tool_output':out}]; break
        elif a in {'edit','final'}: met['edits_rejected']+=1; out={'error':f'{a} rejected: Phase A is read-only'}
        else: out={'error':'unknown action'}
        transcript[-1]['tool_outputs']=[{'action':act,'tool_output':out}]; hist+=['AGENT:'+raw,'TOOL:'+json.dumps([{'action':act,'tool_output':out}],ensure_ascii=False)[:12000]]
    met['source_files']=sorted(set(met['source_files'])); return orientation,met,transcript
def injection(arm,phase_a,claim,fresh):
    if arm=='PREREAD_STALE_SOURCE':
        compact=[{'turn':t.get('turn'),'action':(t.get('actions') or [{}])[0],'tool_outputs':t.get('tool_outputs')} for t in phase_a]
        return '\nEarlier in this same task you already oriented on the source. Continue with that remembered Phase-A context; do not assume a full restart. Your Phase-A transcript was:\n```json\n'+json.dumps(compact,ensure_ascii=False,indent=2)[:9000]+'\n```\n'
    if arm=='STALE_DOC_CONTROL': return '\nMaintenance note from the order service handbook (not freshness-bound): order creation is simple and synchronous. `createOrder` saves the order and immediately calls `EventPublisher.publish` for `ORDER_CREATED`; keep this event emission path direct so downstream listeners observe the same call path.\n'
    if arm=='TMF_STALE_GATED':
        if fresh.fresh: return '\nFresh TMF claim injected below:\n'+json.dumps(claim.to_dict(),ensure_ascii=False,indent=2)
        return '\nTMF freshness warning: a previously verified claim about the old `OrderService.createOrder` event workflow was WITHHELD because its source binding is stale. Withheld claim id: '+claim.id+'. Stale bindings: '+json.dumps(fresh.stale_bindings,ensure_ascii=False)+'. Do not rely on hidden old workflow notes; solve from the current task/source/contracts.\n'
    return ''
def run_phase_b(broker,arm,root,phase_a,claim,fresh,final_gate,max_turns):
    task='线上偶尔出现订单创建成功了，但后续事件处理状态不一致。帮我把订单创建这块的事件触发逻辑修稳一点，别影响原来的保存流程。'
    tools='''Available actions (respond with exactly ONE JSON object per turn, no prose, no arrays, no multiple JSON objects):\n{"action":"list"}\n{"action":"read_range","path":"relative file","start":1,"end":220}\n{"action":"read_symbol","path":"relative .java file","symbol":"symbol name"}\n{"action":"search","query":"text"}\n{"action":"edit","path":"relative file","old":"exact text copied from latest read output","new":"replacement text"}\n{"action":"compile"}\n{"action":"final","answer":"what changed","files":["relative files"]}\n'''
    system=f'''You are a stateless Java coding agent in outbox_m15_two_phase_contract_shift.\nArm: {arm}\nFixture root: {root}\nTask from user: {task}\nMake the smallest compiling change that satisfies the current project contracts.\nWhen editing, copy exact old text from latest read output. If an edit fails, re-read current source and retry with exact text.\nFinal gate mode: {final_gate}\nRespond with exactly one JSON action per turn. You must perform at least one successful edit before final. Run compile before final. After compile succeeds, next turn send final.\n{tools}\n{injection(arm,phase_a,claim,fresh)}\nBegin now.'''
    hist=[]; transcript=[]; met={'tool_calls':0,'source_bytes':0,'source_reads':0,'source_files':[],'prompt_tokens':0,'completion_tokens':0,'invalid':0,'wall_seconds':0.0,'successful_edits':0,'rejected_finals':0,'extra_actions_ignored':0}; final=None; start=time.time()
    for turn in range(max_turns):
        prompt=system+'\n'+('\n'.join(hist[-18:]) if hist else ''); met['prompt_tokens']+=base_runner.tok(prompt); raw=broker.answer(prompt,budget=1)['answer']; met['completion_tokens']+=base_runner.tok(raw); acts=parse_actions(raw); transcript.append({'turn':turn,'raw':raw,'actions':acts})
        if len(acts)==1 and acts[0].get('action') is None and any(k in acts[0] for k in ('files','answer','message')): acts=[{'action':'final',**acts[0]}]
        if not acts: met['invalid']+=1; hist+=['AGENT:'+raw,'SYSTEM: respond with exactly one JSON action, no prose.']; continue
        if len(acts)>1: met['extra_actions_ignored']+=len(acts)-1; acts=acts[:1]
        act=acts[0]; a=act.get('action'); met['tool_calls']+=1; stop=False
        if a=='list': out={'files':list_files(root)}
        elif a=='search': out={'hits':search(root,str(act.get('query','')))}
        elif a=='read_range':
            p=safe(root,str(act.get('path','')))
            if not p: out={'error':'invalid path'}
            else:
                st=max(1,int(act.get('start',1))); en=int(act.get('end',st+120)); content=read_numbered(p,st,en); met['source_bytes']+=len(content.encode()); met['source_reads']+=1; met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'content':content}
        elif a=='read_symbol':
            p=safe(root,str(act.get('path',''))); sym=str(act.get('symbol',''))
            if not p: out={'error':'invalid path'}
            else:
                rng=find_symbol_range(p,sym)
                if not rng: out={'error':'symbol not found'}
                else:
                    content=read_numbered(p,rng[0],rng[1]); met['source_bytes']+=len(content.encode()); met['source_reads']+=1; met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'symbol':sym,'content':content}
        elif a=='edit': out=apply_edit(root,act); met['successful_edits']+=1 if out.get('ok') else 0
        elif a=='compile': out=mvn_test(root)
        elif a=='final':
            if final_gate=='hard' and met['successful_edits']<1: out={'error':'final rejected: no successful edit'}; met['rejected_finals']+=1
            else: final=act; stop=True; break
        else: out={'error':'unknown action'}
        transcript[-1]['tool_outputs']=[{'action':act,'tool_output':out}]
        tool_text=json.dumps([{'action':act,'tool_output':out}],ensure_ascii=False)[:14000]
        if a=='compile' and out.get('ok'): tool_text+='\nSYSTEM: compile succeeded. Next turn respond with exactly one final JSON action and no prose.'
        hist+=['AGENT:'+raw,'TOOL:'+tool_text]
        if stop: break
    met['wall_seconds']=round(time.time()-start,3); met['source_files']=sorted(set(met['source_files'])); return final,met,transcript
def audit(diffs,final,root):
    post=deterministic_test(root); valid=final is not None and bool(diffs) and post['test'].get('ok') is True; sem=valid and post['ok']; return {'valid_answer':valid,'compile_ok':bool(post['test'].get('ok')),'trap_pass':sem,'semantic_pass':sem,'trap_reason':post['placement']|{'post_message':post['message']}}
def classify(raw):
    cls=base_runner.classify_run_failure(raw); cats=list(cls.get('categories',[])); tel=raw.get('telemetry',{}); post=raw.get('post_test') or {}
    if raw.get('final') is None and post.get('ok') and raw.get('diffs'):
        if 'no_final_after_success' not in cats: cats.insert(0,'no_final_after_success')
        cats=[c for c in cats if c!='no_final']
    if tel.get('extra_actions_ignored'): cats.append('extra_actions_ignored')
    passed=bool(cls.get('pass')); out=dict(cls); out['categories']=cats; out['primary']='pass' if passed else (cats[0] if cats else cls.get('primary','uncategorized_fail')); out['extra_actions_ignored']=int(tel.get('extra_actions_ignored',0)); out['result_ok_but_raw_failed']=bool((not passed) and post.get('ok') and raw.get('diffs')); return out
def metrics(raw):
    aud=raw['audit']; cats=set(raw.get('failure_classification',{}).get('categories',[])); post=raw.get('post_test') or {}; raw_pass=bool(aud['valid_answer'] and aud['compile_ok'] and aud['trap_pass']); clean=not bool(cats & {'compile_fail','parse_or_invalid_action_noise'}) and aud['valid_answer'] and aud['compile_ok'] and bool(raw.get('diffs')); return {'raw_pass':raw_pass,'protocol_clean':clean,'semantic_evaluable':clean,'semantic_pass':bool(aud['semantic_pass']) if clean else None,'task_result_pass':bool(post.get('ok') and raw.get('diffs')),'post_test_ok':bool(post.get('ok'))}
def run_one(broker,arm,rep,raw_dir,work_dir,final_gate,pa_turns,pb_turns):
    root=work_dir/f'OUTBOX_M15__{arm}__r{rep}'; meta=make_repo(root); orientation,pa_met,pa_trans=run_phase_a(broker,root,pa_turns); claim=build_claim(root,orientation); pre_excerpt=(root/SERVICE).read_text(encoding='utf-8'); mutate_to_phase_b(root); fresh=check_freshness(GitRepo(root),claim); before=snapshot(root); final,met,trans=run_phase_b(broker,arm,root,pa_trans,claim,fresh,final_gate,pb_turns); post=deterministic_test(root); diffs=diff_files(before,root); raw={'task_id':'OUTBOX_M15','arm':arm,'rep':rep,'fixture_meta':meta,'phase_a_orientation':orientation,'phase_a_telemetry':pa_met,'phase_a_transcript':pa_trans,'phase_a_old_source_excerpt':pre_excerpt,'stale_claim_present':arm in {'PREREAD_STALE_SOURCE','STALE_DOC_CONTROL','TMF_STALE_GATED'},'stale_claim_fresh':fresh.fresh,'stale_claim_withheld':bool(arm=='TMF_STALE_GATED' and not fresh.fresh),'withheld_claim_id':claim.id if arm=='TMF_STALE_GATED' and not fresh.fresh else None,'freshness':{'fresh':fresh.fresh,'stale_bindings':fresh.stale_bindings},'final':final,'telemetry':met,'post_test':post,'diffs':diffs,'audit':audit(diffs,final,root),'transcript':trans,'final_gate':final_gate,'phase_a_max_turns':pa_turns,'phase_b_max_turns':pb_turns}
    raw['failure_classification']=classify(raw); raw['metrics']=metrics(raw); rp=raw_dir/f'OUTBOX_M15__{arm}__r{rep}.raw.json'; rp.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n'); keep=['task_id','arm','rep','final_gate','phase_a_max_turns','phase_b_max_turns','phase_a_orientation','phase_a_telemetry','stale_claim_present','stale_claim_fresh','stale_claim_withheld','withheld_claim_id','freshness','final','telemetry','post_test','audit','failure_classification','metrics']; return {k:raw[k] for k in keep}|{'raw_path':str(rp.relative_to(HERE)),'diff_bytes':sum(len(d.encode()) for d in diffs.values())}
def summarize(rows):
    by={}
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm]; by[arm]={'runs':len(rs),'raw_pass':sum(r['metrics']['raw_pass'] for r in rs),'task_result_pass':sum(r['metrics']['task_result_pass'] for r in rs),'post_test_ok':sum(r['metrics']['post_test_ok'] for r in rs),'semantic_evaluable':sum(r['metrics']['semantic_evaluable'] for r in rs),'semantic_adjusted_pass':sum(1 for r in rs if r['metrics']['semantic_pass'] is True),'stale_claim_withheld':sum(1 for r in rs if r.get('stale_claim_withheld')),'uses_after_commit':sum(1 for r in rs if r.get('post_test',{}).get('placement',{}).get('uses_after_commit')),'uses_immediate_publish':sum(1 for r in rs if r.get('post_test',{}).get('placement',{}).get('uses_immediate_publish')),'primary':{}}
        for r in rs:
            p=r['failure_classification'].get('primary','unknown'); by[arm]['primary'][p]=by[arm]['primary'].get(p,0)+1
    return {'mode':TAG,'runs':len(rows),'by_arm':by}
def write_report(out,path):
    lines=['# Outbox M15 Two-Phase Contract Shift Report','','Fixture: synthetic bounded Maven order-outbox contract shift. Phase A old behavior is valid: createOrder saves and immediately publishes. Phase B changes EventPublisher contract so order-created events must use publishAfterCommit; the human task is vague and does not name methods/APIs.','', '```json',json.dumps(out['summary'],ensure_ascii=False,indent=2),'```','','## Rows']
    for r in out['rows']: lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} task={r['metrics']['task_result_pass']} semantic={r['metrics']['semantic_pass']} post={r['post_test']['ok']} withheld={r.get('stale_claim_withheld')} failure={r['failure_classification']['primary']} placement={json.dumps(r['post_test']['placement'],ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text('\n'.join(lines)+'\n')
def setup_check():
    tmp=HERE/'results'/'work'/'_outbox_m15_setup_check'; make_repo(tmp); pre=mvn_compile(tmp); claim=build_claim(tmp,{'summary':'setup'}); mutate_to_phase_b(tmp); fresh=check_freshness(GitRepo(tmp),claim); post=mvn_test(tmp); out={'pre_compile_ok':pre.get('ok'),'freshness_after_mutation':{'fresh':fresh.fresh,'stale_bindings':fresh.stale_bindings},'post_baseline_tests_ok_expected_false':post.get('ok'),'post_placement':placement(tmp)}; out['ok']=bool(pre.get('ok') and fresh.fresh is False and post.get('ok') is False); print(json.dumps(out,ensure_ascii=False,indent=2)); return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repeats',type=int,default=1); ap.add_argument('--tag',default=TAG); ap.add_argument('--final-gate',choices=['hard'],default='hard'); ap.add_argument('--phase-a-turns',type=int,default=6); ap.add_argument('--phase-b-turns',type=int,default=16); ap.add_argument('--setup-check',action='store_true'); args=ap.parse_args()
    if args.setup_check: setup_check(); return
    results=HERE/'results'; raw_dir=results/'raw'/args.tag; work_dir=results/'work'/args.tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True); broker=JsonBrokerAdapter(BROKER,expected_model=MODEL,timeout_seconds=TIMEOUT); preflight=broker.preflight().__dict__; rows=[]
    for rep in range(1,args.repeats+1):
        for arm in ARMS:
            print(f'RUN rep={rep} arm={arm}',flush=True); row=run_one(broker,arm,rep,raw_dir,work_dir,args.final_gate,args.phase_a_turns,args.phase_b_turns); rows.append(row); print(f"DONE rep={rep} arm={arm} raw={row['metrics']['raw_pass']} task={row['metrics']['task_result_pass']} failure={row['failure_classification']['primary']}",flush=True); out={'schema':TAG,'model':MODEL,'preflight':preflight,'rows':rows,'summary':summarize(rows)}; (results/f'{args.tag}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    out={'schema':TAG,'model':MODEL,'preflight':preflight,'rows':rows,'summary':summarize(rows)}; jp=results/f'{args.tag}.json'; rp=results/f'{args.tag.upper()}_REPORT.md'; jp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); write_report(out,rp); print('WROTE',jp,rp); print(json.dumps(out['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
