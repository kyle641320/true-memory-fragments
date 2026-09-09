import sys,json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from integrations.reflex.cognition.bridge import ObservationContext,CognitionIdentity,stored_provenance,submit_candidate,validate_candidate
from integrations.reflex.cognition.prototype import Store,Denied
repo,mechanical,cognition,ticket,phase,output=sys.argv[1:]
base=Path(output)
# Fixture caller arguments supplied independently of observation content.
ctx=ObservationContext(repo,mechanical,cognition,'fixture-session','fixture-session-id','fixture-run','fix-'+phase)
identity=CognitionIdentity('quote-required-currency','quote-callsite-recovery')
s=Store(repo,cognition)
out={}
if phase=='2':
 prior=json.loads((base/'cognition-1.json').read_text()); old=prior['revision']; old_scope=prior['stored']['scope']
 out['old_state_after_source_change']=s.state(old)
 assert out['old_state_after_source_change']['validity']=='stale'
 out['old_retrieval_after_source_change']=s.retrieve(old_scope)
 assert out['old_retrieval_after_source_change']['items']==[]
 oldctx=ObservationContext(repo,mechanical,cognition,'fixture-session','fixture-session-id','fixture-run','fix-1')
 try:validate_candidate(s,prior['ticket'],old,context=oldctx,identity=identity,event_id='old-revalidate',expected_seq=2)
 except Denied as e:out['old_bridge_validation_denied']=str(e)
 else:raise AssertionError('old observation was reusable')
r=submit_candidate(s,ticket,context=ctx,identity=identity,path='dep.py',function='quote',parameter='currency',producer='explicit-fixture-not-autonomous-agent',parent=old if phase=='2' else None)
out.update(revision=r,ticket=ticket,stored=s.revision(r),submitted_state=s.state(r))
assert out['stored']['proposition']=='dep.py::quote requires parameter currency'
assert out['stored']['predicate']==dict(kind='python_required_parameter',path='dep.py',function='quote',parameter='currency')
assert out['stored']['bindings']==s.capture(['app.py','dep.py'])
assert s.retrieve(out['stored']['scope'])['items']==[]
out['validation']=validate_candidate(s,ticket,r,context=ctx,identity=identity,event_id='validate-'+phase,expected_seq=1)
assert out['validation']['result']=='passed'
assert out['validation']['actual']==['currency','item','qty']
assert out['validation']['source_vector']==out['stored']['bindings']
assert s.state(r)['adoption_state']=='not_adopted' and s.state(r)['activations']==0
if phase=='2':
 assert r!=old and out['stored']['scope']==old_scope
 assert out['stored']['artifact']==prior['stored']['artifact']
 assert out['stored']['parent']==old
 assert stored_provenance(out['stored'])!=stored_provenance(prior['stored'])
 assert s.state(old)['superseded_by'] is None
 out['lineage']={'parent':old,'child':r,'same_scope':True,'same_artifact':True,'distinct_provenance':True}
s.close();s=Store(repo,cognition)
out['reopened_retrieval']=s.retrieve(out['stored']['scope'])
item=out['reopened_retrieval']['items'][0]
assert item['revision']==r and item['proposition']==out['stored']['proposition']
assert item['source_bindings']==out['stored']['bindings']
assert item['validation_event_refs']==['validate-'+phase]
out['reopened_state']=s.state(r)
s.close();(base/('cognition-'+phase+'.json')).write_text(json.dumps(out,indent=2))
print('cognition '+phase+' PASS; explicit lineage preserved')
