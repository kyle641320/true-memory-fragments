#!/usr/bin/env python3
"""Explicit, offline-only javac semantic provider; no wrapper/build execution."""
import argparse, hashlib, json, os, pathlib, subprocess, sys

def sha_file(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def canonical_cp(root, entries):
 rows=[]
 for raw in entries:
  p=pathlib.Path(raw).expanduser().resolve()
  if not p.exists(): raise SystemExit(f"unknown: classpath entry missing: {p}")
  if p.is_dir():
   h=hashlib.sha256()
   for f in sorted(x for x in p.rglob('*') if x.is_file()): h.update(f.relative_to(p).as_posix().encode()+b'\0'+bytes.fromhex(sha_file(f)))
   digest=h.hexdigest()
  else: digest=sha_file(p)
  rows.append({'path':str(p),'sha256':digest})
 rows.sort(key=lambda x:x['path'])
 identity='sha256:'+hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return os.pathsep.join(x['path'] for x in rows),rows,identity

def discover(root,module):
 root=root.resolve(); module=(root/module).resolve()
 if root not in (module,*module.parents): raise SystemExit('module escapes repo')
 kind='maven' if (module/'pom.xml').is_file() else 'gradle' if any((module/x).is_file() for x in ('build.gradle','build.gradle.kts')) else None
 if not kind: return {'status':'unknown','reason':'no_supported_build_file','module':str(module.relative_to(root))}
 build=module/('pom.xml' if kind=='maven' else ('build.gradle' if (module/'build.gradle').exists() else 'build.gradle.kts'))
 wrappers=[x for x in (module/'mvnw',module/'gradlew') if x.exists()]
 cache=pathlib.Path.home()/('.m2/repository' if kind=='maven' else '.gradle/caches/modules-2/files-2.1')
 # Deliberately conservative: build files cannot be safely evaluated without executing build logic.
 return {'status':'partial','reason':'offline_static_discovery_does_not_guess_dependency_graph','kind':kind,'module':str(module.relative_to(root)) or '.', 'build_file':str(build.relative_to(root)),'build_sha256':sha_file(build),'wrapper_present':bool(wrappers),'local_cache_present':cache.is_dir(),'annotation_processing':'disabled'}

a=argparse.ArgumentParser(); a.add_argument('repo'); a.add_argument('paths',nargs='*'); a.add_argument('--classpath',action='append',default=[]); a.add_argument('--module'); a.add_argument('--discover-only',action='store_true'); a.add_argument('-o','--output'); ns=a.parse_args(); root=pathlib.Path(ns.repo).resolve()
if ns.module is not None and not ns.discover_only: a.error('--module is only valid with --discover-only')
meta=discover(root,pathlib.Path(ns.module or '.')) if ns.discover_only else {'status':'explicit','kind':'none','module':'.','build_sha256':'none','annotation_processing':'disabled'}
if ns.discover_only:
 text=json.dumps(meta,sort_keys=True,indent=2)+'\n'; pathlib.Path(ns.output).write_text(text) if ns.output else sys.stdout.write(text); raise SystemExit(0)
if not ns.paths: raise SystemExit('at least one source path is required')
cp,cp_entries,cpid=canonical_cp(root,[e for group in ns.classpath for e in group.split(os.pathsep) if e])
base=pathlib.Path(__file__).resolve().parent; build=base/'.javac-helper-build'; build.mkdir(exist_ok=True); src=base/'javac-helper/TmfJavacFacts.java'; cls=build/'TmfJavacFacts.class'
if not cls.exists() or cls.stat().st_mtime<src.stat().st_mtime: subprocess.run(['javac','-d',str(build),str(src)],check=True)
cmd=['java','-cp',str(build),'TmfJavacFacts',str(root),cp,*ns.paths]; r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,check=True)
doc=json.loads(r.stdout); buildid='sha256:'+hashlib.sha256(json.dumps(meta,sort_keys=True,separators=(',',':')).encode()).hexdigest(); doc['classpath_fingerprint']=cpid; doc['classpath_entries']=cp_entries; doc['build_fingerprint']=buildid; doc['build_identity']=meta
for d in doc['documents']: d.update(classpath_fingerprint=cpid,classpath_entries=cp_entries,build_fingerprint=buildid,build_identity=meta,source_hashes=doc['source_hashes'])
if len(doc['documents']) == 1: doc=doc['documents'][0]
text=json.dumps(doc,sort_keys=True,separators=(',',':'))
pathlib.Path(ns.output).write_text(text,encoding='utf-8') if ns.output else sys.stdout.write(text)
