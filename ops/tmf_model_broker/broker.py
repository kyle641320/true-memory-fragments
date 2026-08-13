#!/usr/bin/env python3
"""Root-operated, stateless, narrow Unix-socket model broker."""
import hashlib, http.client, json, logging, os, socket, socketserver, threading, time, uuid

PROTOCOL='tmf-agent-broker-v1'; MODEL='gpt-5.6-sol'
MAX_REQUEST=65536; MAX_PROMPT=32768; MAX_BUDGET=4; MAX_OUTPUT=512; UPSTREAM_TIMEOUT=30.0; MAX_CONCURRENT=2
LOG=logging.getLogger('tmf-model-broker')

def response_error(code, rid=None): return {'protocol':PROTOCOL,'error':code,'request_id':rid or str(uuid.uuid4())}
def audit(rid,status,start,prompt=b'',usage=None,budget=0):
 LOG.info('request_id=%s model=%s budget=%d usage=%s duration_ms=%d status=%s content_sha256=%s',rid,MODEL,budget,json.dumps(usage or {},separators=(',',':')),int((time.monotonic()-start)*1000),status,hashlib.sha256(prompt).hexdigest())

def validate(obj):
 if not isinstance(obj,dict): raise ValueError('invalid_request')
 op=obj.get('op'); allowed={'protocol','op'} if op=='preflight' else {'protocol','op','model','prompt','budget'}
 if set(obj)-allowed: raise ValueError('illegal_field')
 if obj.get('protocol')!=PROTOCOL: raise ValueError('invalid_protocol')
 if op=='preflight': return op,None,0
 if op!='complete': raise ValueError('invalid_op')
 if obj.get('model')!=MODEL: raise ValueError('model_drift')
 p=obj.get('prompt'); b=obj.get('budget')
 if not isinstance(p,str) or not p.strip(): raise ValueError('invalid_prompt')
 raw=p.encode();
 if len(raw)>MAX_PROMPT: raise ValueError('oversize_prompt')
 if type(b) is not int or not 1<=b<=MAX_BUDGET: raise ValueError('invalid_budget')
 return op,p,b

def upstream(prompt,key):
 body=json.dumps({'model':MODEL,'messages':[{'role':'user','content':prompt}],'max_tokens':MAX_OUTPUT,'stream':False},separators=(',',':'))
 c=http.client.HTTPSConnection('api.aisz.mom',443,timeout=UPSTREAM_TIMEOUT)
 try:
  c.request('POST','/v1/chat/completions',body,{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  r=c.getresponse(); data=r.read(1048577)
  if len(data)>1048576: raise RuntimeError('upstream_oversize')
  if r.status<200 or r.status>=300: raise RuntimeError('upstream_error')
  obj=json.loads(data); answer=obj['choices'][0]['message']['content']; usage=obj.get('usage',{})
  if not isinstance(answer,str) or not answer.strip(): raise RuntimeError('upstream_invalid')
  return answer,usage
 finally: c.close()

class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer): daemon_threads=True
class Handler(socketserver.StreamRequestHandler):
 def handle(self):
  start=time.monotonic(); rid=str(uuid.uuid4()); prompt=b''; budget=0
  try:
   raw=self.rfile.readline(MAX_REQUEST+1)
   if len(raw)>MAX_REQUEST or not raw.endswith(b'\n'): raise ValueError('oversize_request')
   obj=json.loads(raw); op,p,budget=validate(obj)
   if op=='preflight': out={'protocol':PROTOCOL,'model':MODEL,'stateless':True,'tools':[],'network_owner':'broker','credential_owner':'broker'}; status='ok'
   else:
    prompt=p.encode(); key=os.environ.get('AISZ_API_KEY','')
    if not key: raise RuntimeError('missing_key')
    if not SEM.acquire(timeout=0.1): raise RuntimeError('busy')
    try: answer,usage=upstream(p,key)
    finally: SEM.release()
    out={'protocol':PROTOCOL,'model':MODEL,'answer':answer,'calls':1,'request_id':rid,'usage':usage}; status='ok'
  except (ValueError,json.JSONDecodeError) as e: status=str(e) if str(e) else 'invalid_json'; out=response_error(status,rid)
  except (TimeoutError,socket.timeout) : status='timeout'; out=response_error(status,rid)
  except Exception as e: status=str(e) if str(e) in {'missing_key','busy','upstream_error','upstream_oversize','upstream_invalid'} else 'upstream_failure'; out=response_error(status,rid)
  audit(rid,status,start,prompt,locals().get('usage'),budget)
  self.wfile.write(json.dumps(out,separators=(',',':')).encode()+b'\n')

SEM=threading.BoundedSemaphore(MAX_CONCURRENT)
def main():
 logging.basicConfig(level=logging.INFO,format='%(message)s')
 path=os.environ.get('TMF_BROKER_SOCKET','/run/tmf-model-broker/broker.sock')
 try: os.unlink(path)
 except FileNotFoundError: pass
 old=os.umask(0o117)
 try:
  with Server(path,Handler) as s:
   os.chmod(path,0o660); s.serve_forever()
 finally: os.umask(old)
if __name__=='__main__': main()
