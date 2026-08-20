#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile, time
from dataclasses import dataclass
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from bench.agent_ab.adapter import JsonBrokerAdapter, AgentAdapterError
TASKS_DOC=json.loads((HERE/'tasks.json').read_text())
TASKS={t['id']:t for t in TASKS_DOC['tasks']}
ARMS=TASKS_DOC['arms']
MODEL='gpt-5.6-sol'
BROKER=['/opt/tmf-model-broker/client']
MAX_TURNS=12
TIMEOUT=180

def tok(s:str)->int: return (len(s)+3)//4

def safe(root:Path, rel:str):
    p=(root/rel).resolve()
    return p if (p==root or root in p.parents) and p.is_file() else None

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

@dataclass
class DesignClaim:
    claim_id:str; kind:str; anchors:list[str]; chain:list[str]; summary:str; rationale:str; constraints:list[str]; alternatives_considered:list[str]; source_sha256:dict[str,str]
    def to_dict(self): return self.__dict__.copy()

def build_claim(task:dict, base:Path)->DesignClaim:
    sh={a:sha(base/a) for a in task['anchors']}
    if task['id']=='B01':
        summary='EventBus broadcast fan-out dispatches one posted event to every matching Subscriber instead of stopping at the first match.'
        rationale='The chain EventBus.post -> SubscriberRegistry.getSubscribers -> Dispatcher.dispatch -> Subscriber.dispatchEvent -> invokeSubscriberMethod preserves publish/subscribe broadcast semantics and decouples independent subscribers; the tradeoff is O(N) dispatch work and ordering complexity rather than a cheap first-consumer path.'
        constraints=['deliver to all matching subscribers','subscriber isolation','preserve dispatch ordering while allowing executor policy below Subscriber']
        alts=['first matching subscriber only','central sequential handler']
    elif task['id']=='B02':
        summary='Subscriber.dispatchEvent is the boundary that lets Dispatcher know only about ordering/fan-out while Subscriber owns executor handoff and invocation details.'
        rationale='EventBus and Dispatcher can route events without depending on Executor mechanics; renaming/removing this boundary breaks all dispatcher implementations that call dispatchEvent and exposes a deliberate separation between routing order and subscriber execution.'
        constraints=['dispatcher/executor separation','all dispatchers call the same subscriber boundary','async handoff remains inside Subscriber']
        alts=['Dispatcher calls Executor directly','EventBus invokes subscriber methods directly']
    else:
        summary='AsyncEventBus keeps legacy queue drain in Dispatcher.legacyAsync on the posting thread; async handoff occurs in Subscriber.dispatchEvent via executor.execute.'
        rationale='This boundary preserves queue-drain/order behavior separately from actual subscriber invocation; moving async above dispatch makes post return before drain and weakens caller-visible ordering guarantees.'
        constraints=['legacy queue drain semantics','executor handoff at Subscriber','ordering before async invocation']
        alts=['make EventBus.post itself asynchronous','make Dispatcher own Executor']
    return DesignClaim('design_intent_v1:'+task['id'],'design_rationale',task['anchors'],task['entry_chain'],summary,rationale,constraints,alts,sh)

def freshness(claim:DesignClaim, root:Path):
    stale=[]; fresh=[]
    for rel,old in claim.source_sha256.items():
        cur=sha(root/rel)
        (fresh if cur==old else stale).append({'path':rel,'old_sha256':old,'current_sha256':cur})
    return {'fresh':fresh,'stale':stale,'stale_detected':bool(stale)}

def compile_check(root:Path):
    cp=(HERE.parent/'guava_cognitive_v1'/'classpath.txt')
    if not cp.exists(): return {'skipped':True,'reason':'classpath missing'}
    cmd=f'javac -nowarn -cp "$(cat {cp})" -d /tmp/design_intent_javac_{int(time.time()*1000)} {root}/*.java'
    r=subprocess.run(['bash','-lc',cmd],text=True,capture_output=True,timeout=40)
    return {'skipped':False,'exit':r.returncode,'stderr':r.stderr[-1000:]}

def changed_ranges(task:dict, root:Path):
    ranges=[]
    for m in task.get('mutations',[]):
        p=root/m['file']
        lines=p.read_text(errors='replace').splitlines()
        marker='design_intent_v1 mutation'
        idx=None
        for i,l in enumerate(lines,1):
            if marker in l or m['replace'].split('\n')[0].strip() in l:
                idx=i; break
        if idx is None:
            # Fallback: line containing the renamed/replaced symbol if present.
            token=m['replace'].split('(')[0].split()[-1] if '(' in m['replace'] else ''
            for i,l in enumerate(lines,1):
                if token and token in l: idx=i; break
        if idx is None: idx=1
        ranges.append({'path':m['file'],'start':max(1,idx-8),'end':min(len(lines),idx+14)})
    return ranges

def agent_loop(broker, task:dict, arm:str, root:Path, claim:DesignClaim|None, fresh:dict|None):
    injection=''
    if arm=='TMF_FRESH' and claim:
        injection='\nFRESH TMF design-intent claims (source-bound, may be used as memory):\n'+json.dumps(claim.to_dict(),ensure_ascii=False,indent=2)
    elif arm=='TMF_STALE' and claim and fresh:
        stale_paths=[x['path'] for x in fresh['stale']]
        ranges=changed_ranges(task,root)
        injection='\nTMF STALENESS GATE: prior design-intent claims exist but are withheld because these source anchors changed: '+json.dumps(stale_paths)+'. Precise changed ranges: '+json.dumps(ranges)+'. Use read_range on the changed range first; do not rely on old claim content. Read only adjacent chain files if the changed range is insufficient.'
    system=f'''You are a stateless coding-analysis agent in design_intent_v1 Phase B. Work only via one strict JSON object per response.
Arm: {arm}
Fixture root: {root}
Question: {task['phase_b_question']}
Available actions: {{"action":"list"}}, {{"action":"read","path":"relative.java"}}, {{"action":"read_range","path":"relative.java","start":1,"end":40}}, {{"action":"search","query":"text"}}, {{"action":"final","answer":"...","citations":["File.java:line"]}}.
Source is authoritative. Answer must explain design intent and name concrete methods in the chain.'''+injection
    hist=[]; met={'tool_calls':0,'source_reads':0,'source_files':[],'source_bytes':0,'source_lines':0,'localized_reread_bytes':0,'range_reads':0,'prompt_tokens':0,'completion_tokens':0,'injection_tokens':tok(injection),'invalid':0,'wall_seconds':0}
    final=None; start=time.time()
    changed=set(x['path'] for x in (fresh or {}).get('stale',[]))
    for _ in range(MAX_TURNS):
        prompt=system+'\n'+('\n'.join(hist) if hist else 'Begin.')
        met['prompt_tokens']+=tok(prompt)
        try: raw=broker.answer(prompt,budget=1)['answer']
        except Exception as e:
            hist.append('SYSTEM: broker_error '+str(e)); break
        met['completion_tokens']+=tok(raw)
        try: act=json.loads(raw)
        except Exception:
            met['invalid']+=1; hist += ['AGENT:'+raw,'SYSTEM: invalid JSON, respond with exactly one JSON object']; continue
        met['tool_calls']+=1; a=act.get('action')
        if a=='list':
            out={'files':sorted(p.name for p in root.glob('*.java'))}
        elif a=='search':
            q=str(act.get('query','')).lower(); hits=[]
            for p in sorted(root.glob('*.java')):
                for i,l in enumerate(p.read_text(errors='replace').splitlines(),1):
                    if q and q in l.lower(): hits.append(f'{p.name}:{i}:{l}')
            out={'hits':hits[:50]}
        elif a=='read':
            p=safe(root,str(act.get('path','')))
            if not p: out={'error':'invalid path'}
            else:
                data=p.read_bytes(); lines=p.read_text(errors='replace').splitlines(); rel=p.name
                met['source_reads']+=1; met['source_files'].append(rel); met['source_bytes']+=len(data); met['source_lines']+=len(lines)
                if rel in changed or rel in task['anchors']: met['localized_reread_bytes']+=len(data)
                out={'path':rel,'content':'\n'.join(f'{i}: {l}' for i,l in enumerate(lines,1))}
        elif a=='read_range':
            p=safe(root,str(act.get('path','')))
            if not p: out={'error':'invalid path'}
            else:
                lines=p.read_text(errors='replace').splitlines(); rel=p.name
                start=max(1,int(act.get('start',1))); end=min(len(lines),int(act.get('end',start+60)))
                if end < start: end=start
                chunk='\n'.join(f'{i}: {lines[i-1]}' for i in range(start,end+1))
                b=len(chunk.encode())
                met['source_reads']+=1; met['range_reads']+=1; met['source_files'].append(rel); met['source_bytes']+=b; met['source_lines']+=(end-start+1)
                if rel in changed or rel in task['anchors']: met['localized_reread_bytes']+=b
                out={'path':rel,'start':start,'end':end,'content':chunk}
        elif a=='final':
            if arm=='TMF_STALE' and changed and not (changed & set(met['source_files'])):
                out={'error':'staleness gate blocked final: read changed source first'}
            else:
                final=act; break
        else: out={'error':'unknown action'}
        hist += ['AGENT:'+raw,'TOOL:'+json.dumps(out,ensure_ascii=False)]
    met['wall_seconds']=time.time()-start; met['source_files']=sorted(set(met['source_files']))
    return final,met

def machine_score(task, arm, final, met, fresh):
    ans=((final or {}).get('answer') or '').lower(); cites=(final or {}).get('citations') or []
    kws=task['rubric']['design_keywords']; hits=[k for k in kws if k.lower() in ans]
    design_score=0
    if len(hits)>=6 and any(x in ans for x in ['tradeoff','trade-off','property','semantics','separation','boundary','isolation','ordering']): design_score=2
    elif len(hits)>=3: design_score=1
    stale_detected=bool((fresh or {}).get('stale_detected')) if arm=='TMF_STALE' else None
    read_changed=bool(set(met['source_files']) & set(x['path'] for x in (fresh or {}).get('stale',[]))) if arm=='TMF_STALE' else None
    forbidden=[p for p in task['rubric'].get('stale_forbidden_if_unread',[]) if p.lower() in ans]
    stale_trust_error=bool(arm=='TMF_STALE' and (not read_changed or forbidden))
    chain_hits=[c for c in task['entry_chain'] if c.lower() in ans]
    return {'design_score_machine':design_score,'keyword_hits':hits,'chain_hits':chain_hits,'chain_completeness':len(chain_hits)/len(task['entry_chain']),'has_citations':bool(cites),'stale_detected':stale_detected,'read_changed_anchor':read_changed,'stale_trust_error':stale_trust_error,'forbidden_phrases':forbidden}

def execute_task(broker, tid):
    task=TASKS[tid]
    base=HERE/'fixtures'/tid/'base'; mutated=HERE/'fixtures'/tid/'mutated'
    claim=build_claim(task,base)
    phase_a={'question':task['phase_a_question'],'discarded_answer':True,'claim':claim.to_dict()}
    rows=[]
    for arm in ARMS:
        with tempfile.TemporaryDirectory(prefix='design-intent-') as td:
            root=Path(td)/'repo'
            shutil.copytree(mutated if arm=='TMF_STALE' else base, root)
            fr=freshness(claim,root)
            final,met=agent_loop(broker,task,arm,root,claim,fr)
            sc=machine_score(task,arm,final,met,fr)
            rows.append({'task_id':tid,'arm':arm,'valid':final is not None,'fixture':'mutated' if arm=='TMF_STALE' else 'base','freshness':fr if arm.startswith('TMF') else None,'answer':final,'telemetry':met,'score':sc,'compile':compile_check(root)})
            print(tid,arm,'valid',final is not None,'score',sc['design_score_machine'],'reads',met['source_bytes'],flush=True)
    return {'task_id':tid,'phase_a':phase_a,'rows':rows}

def summarize(results):
    gates=[]
    for t in results['tasks']:
        by={r['arm']:r for r in t['rows']}
        so=by['SOURCE_ONLY']; stale=by['TMF_STALE']; fresh=by['TMF_FRESH']
        gate={'task_id':t['task_id'],
              'stale_detected':stale['score']['stale_detected'] is True,
              'stale_reread_lt_50pct_source':stale['telemetry']['source_bytes'] < 0.5*max(1,so['telemetry']['source_bytes']),
              'zero_stale_trust_error':not stale['score']['stale_trust_error'],
              'fresh_chain_gt_source':fresh['score']['chain_completeness']>so['score']['chain_completeness'],
              'fresh_design_score':fresh['score']['design_score_machine'],
              'source_design_score':so['score']['design_score_machine']}
        gate['pass_mandatory']=gate['stale_detected'] and gate['stale_reread_lt_50pct_source'] and gate['zero_stale_trust_error']
        gates.append(gate)
    results['summary']={'gates':gates,'smoke_pass':all(g['pass_mandatory'] for g in gates),'stale_detection_rate':sum(g['stale_detected'] for g in gates)/len(gates),'stale_trust_errors':sum(not g['zero_stale_trust_error'] for g in gates)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--smoke',action='store_true'); ap.add_argument('--task'); ap.add_argument('--tag',default='smoke-n2'); args=ap.parse_args()
    subprocess.run([sys.executable,str(HERE/'make_fixtures.py'),'--check'],check=True)
    subprocess.run([sys.executable,str(HERE/'validate.py')],check=True)
    broker=JsonBrokerAdapter(BROKER,expected_model=MODEL,timeout_seconds=TIMEOUT)
    try: pre=broker.preflight().__dict__
    except AgentAdapterError as e: raise SystemExit(f'broker preflight failed: {e}')
    ids=[args.task] if args.task else (TASKS_DOC['smoke'] if args.smoke else [t['id'] for t in TASKS_DOC['tasks']])
    out={'schema':'design-intent-v1-results','tag':args.tag,'model':MODEL,'preflight':pre,'tasks':[]}
    for tid in ids: out['tasks'].append(execute_task(broker,tid))
    summarize(out)
    (HERE/'results').mkdir(exist_ok=True)
    p=HERE/'results'/(args.tag+'.json'); p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('wrote',p)
if __name__=='__main__': main()
