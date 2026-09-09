import sys,json,tempfile,hashlib,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from integrations.reflex.cognition.bridge import ObservationContext,CognitionIdentity,submit_candidate,validate_candidate
from integrations.reflex.cognition.prototype import Store,Denied
IDENTITY=CognitionIdentity('quote-required-currency','quote-recovery')
class Scope(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir();(self.repo/'dep.py').write_text('def quote(item, qty, currency):\n    return item\n');(self.repo/'app.py').write_text("quote('pen',2,'USD')\n")
  self.store=Store(self.repo,self.root/'cognition');self.ctx=ObservationContext(str(self.repo),str(self.root/'mechanical'),str(self.root/'cognition'),'session-key','session-uuid','run','call')
  v=[]
  for name in ['app.py','dep.py']:
   b=(self.repo/name).read_bytes();v.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest(),snippet=b.decode(),git_blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
  self.o=dict(schema='tmf.recovery-observation.v1',id='fixture-observation',status='recovery_released_without_consolidation',canonical_repo_root=str(self.repo),canonical_state_root=self.ctx.mechanical_state_root,identity=dict(sessionKey='session-key',sessionId='session-uuid',runId='run',toolCallId='call'),receipt_key=json.dumps(['session-key','run','call']),postmutation_vector=v,observed_dependencies=[dict(path='dep.py',qualname='quote',read_observed=True,observed_git_blob=v[1]['git_blob'])],mutation=dict(target='app.py'))
  self.ticket=self.root/'ticket.json';self.save()
 def save(self):self.ticket.write_text(json.dumps(self.o))
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def counts(self):return tuple(self.store.db.execute('select count(*) from '+t).fetchone()[0] for t in ['revisions','events'])
 def submit(self,c=None):return submit_candidate(self.store,self.ticket,context=c or self.ctx,identity=IDENTITY,path='dep.py',function='quote',parameter='currency',producer='synthetic-scope-fixture')
 def denied(self,fn):
  before=self.counts()
  with self.assertRaises((Denied,TypeError,ValueError)):fn()
  self.assertEqual(before,self.counts())
 def test_distinct_roots_and_idempotence(self):
  r=self.submit();self.assertEqual(r,self.submit());self.assertEqual(self.counts(),(1,1));self.assertEqual(validate_candidate(self.store,self.ticket,r,context=self.ctx,identity=IDENTITY,event_id='v',expected_seq=1)['result'],'passed');self.assertEqual(self.store.state(r)['adoption_state'],'not_adopted')
 def test_wrong_mechanical(self):self.denied(lambda:self.submit(replace(self.ctx,mechanical_state_root=str(self.root/'wrong'))))
 def test_wrong_cognition(self):self.denied(lambda:self.submit(replace(self.ctx,cognition_state_root=str(self.root/'wrong'))))
 def test_wrong_repo(self):self.denied(lambda:self.submit(replace(self.ctx,repo_root=str(self.root/'wrong'))))
 def test_alias_not_canonical(self):self.denied(lambda:self.submit(replace(self.ctx,mechanical_state_root=str(self.root/'x/../mechanical'))))
 def test_each_identity(self):
  for field in ['session_key','session_id','run','tool_call']:
   with self.subTest(field=field):self.denied(lambda:self.submit(replace(self.ctx,**{field:'other'})))
 def test_missing_bad_context(self):
  for field in ['run','tool_call']:
   for value in [None,'', ' ',42]:
    with self.subTest(field=field,value=value):self.denied(lambda:self.submit(replace(self.ctx,**{field:value})))
  self.denied(lambda:self.submit(replace(self.ctx,session_key=None,session_id=None)))
 def test_receipt_mismatch(self):self.o['receipt_key']=json.dumps(['other','run','call']);self.save();self.denied(self.submit)
 def test_identity_missing(self):self.o['identity']['runId']=None;self.save();self.denied(self.submit)
 def test_revision_cannot_change_identity(self):
  r=self.submit();self.o['identity']['runId']='new';self.o['receipt_key']=json.dumps(['session-key','new','call']);self.save();self.denied(lambda:validate_candidate(self.store,self.ticket,r,context=replace(self.ctx,run='new'),identity=IDENTITY,event_id='v',expected_seq=1))
 def test_revision_cannot_change_mechanical(self):
  r=self.submit();new=str(self.root/'other-mechanical');self.o['canonical_state_root']=new;self.save();self.denied(lambda:validate_candidate(self.store,self.ticket,r,context=replace(self.ctx,mechanical_state_root=new),identity=IDENTITY,event_id='v',expected_seq=1))
 def test_revision_cannot_change_optional_session_id(self):
  r=self.submit();self.o['identity']['sessionId']='new';self.save();self.denied(lambda:validate_candidate(self.store,self.ticket,r,context=replace(self.ctx,session_id='new'),identity=IDENTITY,event_id='v',expected_seq=1))
 def test_wrong_parent_identity_no_write(self):
  parent=self.submit()
  for identity in [CognitionIdentity('different','quote-recovery'),CognitionIdentity('quote-required-currency','different')]:
   self.denied(lambda:submit_candidate(self.store,self.ticket,context=self.ctx,identity=identity,path='dep.py',function='quote',parameter='currency',producer='fixture',parent=parent))
 def test_two_observations_same_source_parent_and_wrong_observation(self):
  parent=self.submit();self.o['id']='second-observation';self.save()
  child=submit_candidate(self.store,self.ticket,context=self.ctx,identity=IDENTITY,path='dep.py',function='quote',parameter='currency',producer='synthetic-scope-fixture',parent=parent)
  self.assertNotEqual(parent,child);self.assertEqual(self.store.revision(child)['parent'],parent)
  self.assertEqual(self.store.revision(child)['artifact'],self.store.revision(parent)['artifact'])
  self.denied(lambda:validate_candidate(self.store,self.ticket,parent,context=self.ctx,identity=IDENTITY,event_id='v',expected_seq=1))
  self.assertEqual(self.store.state(child)['adoption_state'],'not_adopted')
  self.assertIsNone(self.store.state(parent)['superseded_by'])
if __name__=='__main__':unittest.main(verbosity=2)
