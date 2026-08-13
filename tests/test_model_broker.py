import ast,importlib.util,json,logging,os,socket,threading,time,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'ops/tmf_model_broker/broker.py'; s=importlib.util.spec_from_file_location('broker',P); b=importlib.util.module_from_spec(s); s.loader.exec_module(b)
CLIENT=P.with_name('client.py')
class T(unittest.TestCase):
 def test_rebuildable_timeout_hierarchy(self):
  tree=ast.parse(CLIENT.read_text())
  defaults=[n.args[1].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='get' and len(n.args)>=2 and isinstance(n.args[0],ast.Constant) and n.args[0].value=='TMF_BROKER_CLIENT_TIMEOUT']
  self.assertEqual(defaults,['100'])
  self.assertLess(b.UPSTREAM_TIMEOUT,float(defaults[0]))
  self.assertLess(float(defaults[0]),120.0)
 def test_validation(self):
  self.assertEqual(b.validate({'protocol':b.PROTOCOL,'op':'preflight'})[0],'preflight')
  good={'protocol':b.PROTOCOL,'op':'complete','model':b.MODEL,'prompt':'x','budget':1}; self.assertEqual(b.validate(good)[1],'x')
  cases=[({**good,'evil':1},'illegal_field'),({**good,'model':'other'},'model_drift'),({**good,'budget':0},'invalid_budget'),({**good,'budget':5},'invalid_budget'),({**good,'prompt':'x'*(b.MAX_PROMPT+1)},'oversize_prompt')]
  for obj,msg in cases:
   with self.subTest(msg=msg),self.assertRaisesRegex(ValueError,msg): b.validate(obj)
 def test_missing_key_upstream_error_timeout_and_audit_redaction(self):
  old=b.upstream; records=[]
  class H(logging.Handler):
   def emit(self,r): records.append(r.getMessage())
  h=H(); b.LOG.addHandler(h); b.LOG.setLevel(logging.INFO)
  try:
   for exc,code in [(RuntimeError('upstream_error'),'upstream_error'),(socket.timeout(),'timeout')]:
    b.upstream=lambda p,k,e=exc: (_ for _ in ()).throw(e)
    os.environ['AISZ_API_KEY']='SUPERSECRET'; out=self.call({'protocol':b.PROTOCOL,'op':'complete','model':b.MODEL,'prompt':'PRIVATEPROMPT','budget':1}); self.assertEqual(out['error'],code)
   del os.environ['AISZ_API_KEY']; self.assertEqual(self.call({'protocol':b.PROTOCOL,'op':'complete','model':b.MODEL,'prompt':'PRIVATEPROMPT','budget':1})['error'],'missing_key')
   text=' '.join(records); self.assertNotIn('PRIVATEPROMPT',text); self.assertNotIn('SUPERSECRET',text)
  finally: b.upstream=old; b.LOG.removeHandler(h); os.environ.pop('AISZ_API_KEY',None)
 def call(self,obj):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   path=d+'/s'; srv=b.Server(path,b.Handler); t=threading.Thread(target=srv.handle_request); t.start()
   with socket.socket(socket.AF_UNIX) as c: c.connect(path); c.sendall(json.dumps(obj).encode()+b'\n'); out=c.makefile('rb').readline()
   t.join(); srv.server_close(); return json.loads(out)
 def test_preflight_and_oversize_wire(self):
  self.assertEqual(self.call({'protocol':b.PROTOCOL,'op':'preflight'})['tools'],[])
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   path=d+'/s'; srv=b.Server(path,b.Handler); t=threading.Thread(target=srv.handle_request);t.start()
   with socket.socket(socket.AF_UNIX) as c: c.connect(path);c.sendall(b'x'*(b.MAX_REQUEST+1)+b'\n');out=json.loads(c.makefile('rb').readline())
   t.join();srv.server_close();self.assertEqual(out['error'],'oversize_request')
if __name__=='__main__': unittest.main()
