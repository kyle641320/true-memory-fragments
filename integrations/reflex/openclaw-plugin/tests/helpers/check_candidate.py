import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from integrations.reflex.cognition.bridge import CognitionIdentity, ObservationContext, submit_candidate, validate_candidate
from integrations.reflex.cognition.prototype import Store, Denied
repo,ticket,mode=sys.argv[1:]
s=Store(repo,Path(repo).parent/'cognition')
root=Path(repo).parent
context=ObservationContext(str(Path(repo)),str(root/'external'/'.tmf'),str(root/'cognition'),str(root),None,'r','fix')
assert s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==0
assert s.retrieve('anything')['items']==[]
if mode in ('drift-target','drift-dependency'):
 p=Path(repo)/('app.py' if mode=='drift-target' else 'dep.py');p.write_text(p.read_text()+'# drift\n')
 try:submit_candidate(s,ticket,context=context,identity=CognitionIdentity('quote-required-currency','quote-recovery'),path='dep.py',function='quote',parameter='currency',producer='explicit-fixture')
 except Denied as e:assert 'drift' in str(e)
 else:raise AssertionError('drift accepted')
 assert s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==0
else:
 r=submit_candidate(s,ticket,context=context,identity=CognitionIdentity('quote-required-currency','quote-recovery'),path='dep.py',function='quote',parameter='absent' if mode=='wrong-predicate' else 'currency',producer='explicit-fixture')
 assert s.state(r)['review_state']=='candidate' and s.state(r)['adoption_state']=='not_adopted'
 if mode=='drift-before-validation':
  p=Path(repo)/'app.py';p.write_text(p.read_text()+'# drift\n')
  try:validate_candidate(s,ticket,r,context=context,identity=CognitionIdentity('quote-required-currency','quote-recovery'),event_id='v1',expected_seq=1)
  except Denied:pass
  else:raise AssertionError('stale validation accepted')
 else:
  v=validate_candidate(s,ticket,r,context=context,identity=CognitionIdentity('quote-required-currency','quote-recovery'),event_id='v1',expected_seq=1)
  assert v['result']==('failed' if mode=='wrong-predicate' else 'passed')
  state=s.state(r);assert state['review_state']==('contested' if mode=='wrong-predicate' else 'supported')
  assert state['adoption_state']=='not_adopted' and state['activations']==0
s.close()
print(mode+': passed')
