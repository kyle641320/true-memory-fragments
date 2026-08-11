#!/usr/bin/env python3
import json,re,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent; M=json.loads((R/'manifest.json').read_text()); G={x['id']:x for x in map(json.loads,(R/'goldens/goldens.jsonl').read_text().splitlines())}
def text_of(p):
 try:
  d=json.loads(p.read_text()); return '\n'.join(x.get('text','') for x in d.get('result',{}).get('payloads',[]))
 except Exception:return ''
rows=[]
for t in M['tasks']:
 for arm in M['arms']:
  k=f"{t['id']}_{arm}"; p=R/'raw'/f'{k}.agent.json'; meta=R/'raw'/f'{k}.runmeta.json'; text=text_of(p); valid=bool(text and meta.exists() and json.loads(meta.read_text())['exit_code']==0)
  cited=sorted(set(re.findall(r'(?:src/(?:main|test)/java/[^\s:),]+\.java)',text)))
  g=G[t['id']]; hits={s:any(s in c for c in cited) for s in g['must_cite']}; fact_hits=[any(w.lower() in text.lower() for w in re.findall(r'[A-Za-z]{5,}',f)[:5]) for f in g['facts']]
  mm=re.search(r'METRICS_JSON=(\{.*\})',text,re.S); metrics={}
  if mm:
   try: metrics=json.loads(mm.group(1).strip())
   except: pass
  fresh=t.get('freshness',False); stale_blocked=bool(metrics.get('stale_blocked')) or (fresh and 'stale' in text.lower() and any(w in text.lower() for w in ['block','reject','do not trust','not trust']))
  rows.append({'task_id':t['id'],'repo':t['repo'],'type':t['type'],'arm':arm,'valid':valid,'correct':valid and all(hits.values()) and all(fact_hits) and (not fresh or stale_blocked),'citation_correct':valid and all(hits.values()),'citation_hits':hits,'source_files':metrics.get('source_files',cited),'source_lines':metrics.get('source_lines'), 'tool_calls':metrics.get('tool_calls'),'wall_seconds':json.loads(meta.read_text()).get('wall_seconds') if meta.exists() else None,'stale_trusted':metrics.get('stale_trusted',False),'stale_blocked':stale_blocked,'local_reread_lines':metrics.get('local_reread_lines'),'response_sha256':hashlib.sha256(text.encode()).hexdigest() if text else None})
pairs=[]
for t in M['tasks']:
 x=[r for r in rows if r['task_id']==t['id']]; pairs.append({'task_id':t['id'],'valid_pair':len(x)==2 and all(r['valid'] for r in x),'arms':{r['arm']:{'correct':r['correct'],'citation_correct':r['citation_correct'],'wall_seconds':r['wall_seconds']} for r in x}})
summary={}
for a in M['arms']:
 x=[r for r in rows if r['arm']==a and r['valid']]; summary[a]={'n_valid':len(x),'accuracy':sum(r['correct'] for r in x)/len(x) if x else None,'citation_accuracy':sum(r['citation_correct'] for r in x)/len(x) if x else None,'mean_wall_seconds':sum(r['wall_seconds'] for r in x)/len(x) if x else None,'stale_block_rate':sum(r['stale_blocked'] for r in x if r['type'].startswith('freshness'))/max(1,sum(r['type'].startswith('freshness') for r in x))}
rep={'schema':'java-real-v2-report','execution_kind':'native_isolated_openclaw_agents','rows':rows,'pairs':pairs,'summary':summary,'ordinary_valid_pairs':sum(p['valid_pair'] and not next(t for t in M['tasks'] if t['id']==p['task_id']).get('freshness') for p in pairs),'freshness_valid_pairs':sum(p['valid_pair'] and next(t for t in M['tasks'] if t['id']==p['task_id']).get('freshness') for p in pairs),'pollution_test':json.loads((R/'artifacts/pollution-test.json').read_text()),'manifest_sha256':hashlib.sha256((R/'manifest.json').read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((R/'PROTOCOL.md').read_bytes()).hexdigest() if (R/'PROTOCOL.md').exists() else None}
(R/'REPORT.json').write_text(json.dumps(rep,indent=2)+'\n'); print(json.dumps({'ordinary_valid_pairs':rep['ordinary_valid_pairs'],'freshness_valid_pairs':rep['freshness_valid_pairs'],'summary':summary},indent=2))
