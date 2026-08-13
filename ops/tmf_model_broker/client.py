#!/usr/bin/env python3
"""stdin/stdout adapter for tmf-agent-broker-v1."""
import json, os, socket, sys
MAX=65536

def main():
 raw=sys.stdin.buffer.readline(MAX+1)
 if len(raw)>MAX or not raw.endswith(b'\n'): return 2
 try: obj=json.loads(raw)
 except Exception: return 2
 data=json.dumps(obj,separators=(',',':')).encode()+b'\n'
 try:
  with socket.socket(socket.AF_UNIX) as s:
   s.settimeout(float(os.environ.get('TMF_BROKER_CLIENT_TIMEOUT','100'))); s.connect(os.environ.get('TMF_BROKER_SOCKET','/run/tmf-model-broker/broker.sock')); s.sendall(data)
   f=s.makefile('rb'); out=f.readline(1048577)
  if not out or len(out)>1048576: return 3
  resp=json.loads(out)
 except Exception: return 3
 sys.stdout.write(json.dumps(resp,separators=(',',':'))+'\n')
 return 0 if 'error' not in resp else 4
if __name__=='__main__': raise SystemExit(main())
