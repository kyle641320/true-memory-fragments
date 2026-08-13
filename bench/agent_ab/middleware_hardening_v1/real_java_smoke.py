import importlib.util,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('hardening',H/'middleware.py');m=importlib.util.module_from_spec(sp);sys.modules['hardening']=m;sp.loader.exec_module(m)
root=H.parents[2];paths=['fixtures/java-retry-heldout/src/main/java/example/RetryService.java','fixtures/java-cache-heldout/src/main/java/example/CacheService.java'];rows=[]
for i,rel in enumerate(paths):
 p=root/rel
 if not p.exists():
  matches=list((root/rel.split('/src/')[0]).rglob('*.java'));p=matches[0];rel=p.relative_to(root).as_posix()
 data=p.read_bytes();t=m.Target('tmf-current','readonly-head',rel,'real-smoke','agent',None,None,str(i));c=m.Claim('real'+str(i),'tmf-current','readonly-head',rel,'real-smoke','agent',None,None,m.digest(data),1);fresh,_=m.before_read(t,t,[c],data);wrong,_=m.before_read(m.Target('tmf-current','readonly-head',rel+'x','real-smoke','agent'),t,[c],b'');stale,_=m.before_read(t,t,[c],data+b'\n// changed')
 rows.append({'path':rel,'tool_target_gate':fresh['kind'],'wrong_target':wrong['kind'],'stale':stale['kind'],'stale_old_fact_leak':'fact' in json.dumps(stale)})
out={'read_only':True,'tasks':rows,'pass':all(r['tool_target_gate']=='FRESH' and r['wrong_target']=='MISS' and r['stale']=='STALE' and not r['stale_old_fact_leak'] for r in rows)};(H/'results'/'real-java-smoke.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
