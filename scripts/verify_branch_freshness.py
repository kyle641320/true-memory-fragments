import os, sys, json, subprocess, hashlib, shutil, time
from pathlib import Path
from dataclasses import asdict
import argparse
parser = argparse.ArgumentParser(description='Offline multi-worktree freshness acceptance')
parser.add_argument('--output', type=Path, required=True, help='New evidence directory (must not exist)')
args = parser.parse_args()
ROOT=args.output.resolve()
ROOT.mkdir(parents=True, exist_ok=False)
ENGINE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ENGINE))
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode = True
# This acceptance must remain offline even in a model-enabled host shell.
os.environ.pop('TMF_MODEL_COMMAND', None)
from tmf.mcp_server import McpService
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.store import Store
from tmf.java_extract import java_status
out={'scope':'deterministic actual TMF API, not agent/write enforcement','commands':[],'cases':[],'api':{},'snapshots':{},'java_status':str(java_status())}
def save(): (ROOT/'result.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
def git(p,*args):
 r=subprocess.run(['git',*args],cwd=p,capture_output=True,text=True);out['commands'].append({'cwd':str(p),'argv':['git',*args],'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});save();r.check_returncode();return r.stdout.strip()
def snap(label,p):
 out['snapshots'][label]={'root':str(p),'head':git(p,'rev-parse','HEAD'),'branch':git(p,'branch','--show-current'),'blobs':{x.name:GitRepo(p).blob_sha(x.name) for x in p.glob('*.java')}};save()
def check(name,actual,expected):out['cases'].append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected});save()
def claims(p):return list(Store(p).iter_claims())
def pick(p,q):return next(c for c in claims(p) if c.body.get('qualname')==q and not c.body.get('edge_kind'))
def fresh(p,c):return asdict(check_freshness(GitRepo(p),c))
def api(label,p,tool,**args):
 val=McpService(p).call_tool(tool,args);out['api'][label]=val;save();return val
# Engine source hashes, avoiding modifying engine through pycache.
out['engine_before']={str(p.relative_to(ENGINE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ENGINE/'tmf').rglob('*.py')};save()
a=ROOT/'repo-a';b=ROOT/'repo-b';a.mkdir()
git(a,'init','-b','main');git(a,'config','user.name','TMF bounded validation');git(a,'config','user.email','tmf-validation@example.invalid')
files={'Base.java':'class Base { int value(){ return 1; } }\n','Child.java':'class Child extends Base { int read(){ return value(); } }\n','Other.java':'class Other { int stable(){ return 7; } }\n','.gitignore':'.tmf/\n'}
for f,v in files.items():(a/f).write_text(v)
git(a,'add','.');git(a,'commit','-m','base fixture');snap('base',a)
api('warm_base',a,'tmf_warm');old=pick(a,'Base.value');other=pick(a,'Other.stable');edge=next(c for c in claims(a) if c.body.get('edge_kind')=='inherits');out['bound_edge']=asdict(edge);save()
check('unchanged_fresh',fresh(a,old)['fresh'],True)
git(a,'worktree','add','-b','feature',str(b));shutil.copytree(a/'.tmf',b/'.tmf')
(b/'Base.java').write_text(files['Base.java'].replace('return 1','return 2'));git(b,'add','Base.java');git(b,'commit','-m','feature changes same path');snap('feature',b)
check('other_branch_same_path_old_claim_stale',fresh(b,old)['fresh'],False)
check('origin_branch_still_fresh',fresh(a,old)['fresh'],True)
check('bound_dependency_edge_stale',fresh(b,edge)['fresh'],False)
check('unrelated_content_fresh',fresh(b,other)['fresh'],True)
api('stale_explain_feature',b,'tmf_explain',claim_id=old.id)
api('stale_slice_feature',b,'tmf_stale_slice',claim_id=edge.id)
api('warm_feature',b,'tmf_warm');feature=pick(b,'Base.value');check('refresh_feature_fresh',fresh(b,feature)['fresh'],True);check('old_claim_remains_stale_after_refresh',fresh(b,old)['fresh'],False)
(b/'Base.java').write_text(files['Base.java'].replace('return 1','return 3'));snap('dirty_feature',b);check('dirty_worktree_invalidates_feature_claim',fresh(b,feature)['fresh'],False);api('dirty_explain',b,'tmf_explain',claim_id=feature.id)
# Commit dirty update, then switch to the older base while retaining worktree-local cache.
git(b,'add','Base.java');git(b,'commit','-m','feature second source update');api('warm_feature_v3',b,'tmf_warm');v3=pick(b,'Base.value');git(b,'switch','--detach',out['snapshots']['base']['head']);snap('switch_base',b)
check('switch_back_rejects_v3_claim',fresh(b,v3)['fresh'],False);check('switch_back_original_claim_fresh',fresh(b,old)['fresh'],True);api('warm_switched_base',b,'tmf_warm');check('switch_refresh_recovers',fresh(b,pick(b,'Base.value'))['fresh'],True)
git(a,'merge','--ff-only','feature');snap('merged_main',a);check('merge_rejects_premerge_claim',fresh(a,old)['fresh'],False);api('merge_stale_explain',a,'tmf_explain',claim_id=old.id);api('warm_merged',a,'tmf_warm');check('merge_refresh_recovers',fresh(a,pick(a,'Base.value'))['fresh'],True)
check('merged_main_matches_feature_v3',fresh(a,v3)['fresh'],True)
out['engine_after']={str(p.relative_to(ENGINE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ENGINE/'tmf').rglob('*.py')};check('engine_unchanged',out['engine_before'],out['engine_after'])
for label in ('stale_explain_feature', 'dirty_explain', 'merge_stale_explain'):
 check(label + '_api_stale', json.loads(out['api'][label]['content'][0]['text'])['claim']['fresh'], False)
check('stale_slice_api_withheld', json.loads(out['api']['stale_slice_feature']['content'][0]['text'])['stale_claim_withheld'], True)
out['status']='passed' if all(c['passed'] for c in out['cases']) else 'failed';save();print(json.dumps({'status':out['status'],'checks':len(out['cases']),'failed':[x['name'] for x in out['cases'] if not x['passed']]}))

raise SystemExit(0 if out["status"] == "passed" else 1)
