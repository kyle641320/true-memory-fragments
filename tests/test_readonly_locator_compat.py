from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.locator_server import McpService, tools_list
from tmf.readonly_store import ReadOnlyStore
from tmf.freshness import check_freshness
from tmf.legacy_top_level import extract_module_top_levels

ROOT = Path(__file__).resolve().parents[1]

def fingerprint(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}

def fixture(root, name='helper'):
    repo = root / 'repo'; repo.mkdir(parents=True)
    subprocess.run(['git','init','-q','-b','main',str(repo)],check=True)
    source = 'VALUE = 1\n\ndef '+name+'():\n    return VALUE\n'
    (repo/'a.py').write_text(source)
    state=root/'external'; (state/'claims').mkdir(parents=True)
    (state/'schema_version').write_text('tmf.schema.v1\n')
    claims=derive_claims_for_path(GitRepo(repo),'a.py')
    for c in claims:
        d=c.to_dict(); d['body'].pop('derivation_versions',None)
        (state/'claims'/f'{c.id}.json').write_text(json.dumps(d))
    # Include a real legacy-only module record and preserve its extension.
    d=next(c.to_dict() for c in claims if c.scope=='file')
    node=extract_module_top_levels('a.py',source)[0]
    d.update(id='legacy_module',scope='module_top_level',module_top_level_contract={
        'region_id':node.region_id,'anchor':{'path':'a.py','line_start':1,'line_end':1},
        'schema_version':'tmf.module_top_level_contract.v2'})
    d['body'].pop('derivation_versions',None);d['body']['qualname']=node.region_id
    d['bindings'][0].update(fn_hash=node.top_level_hash,qualname=node.region_id)
    (state/'claims/legacy_module.json').write_text(json.dumps(d))
    return repo,state

class ReadOnlyLocatorTests(unittest.TestCase):
    def test_all_tools_no_disk_writes_stale_and_module(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);repo,state=fixture(root)
            before=fingerprint(root)
            with patch.dict(os.environ, {'TMF_ROUTER_COMMAND':'must-not-run','TMF_EMBED_COMMAND':'must-not-run'}):
                service=McpService(repo,state,load_assist_provider=False)
                helper=next(c for c in service.store.iter_claims() if c.body.get('qualname')=='helper' and c.scope=='function')
                self.assertTrue(service.tmf_retrieve('helper')['claims'])
                self.assertTrue(service.tmf_context('helper')['claims'])
                self.assertTrue(service.tmf_explain(helper.id)['claim']['fresh'])
                self.assertIn('module_top_level_contract',service.tmf_explain('legacy_module',True)['claim']['claim_record'])
                for name in ('tmf_callers','tmf_readers','tmf_writers','tmf_subtypes'):
                    self.assertIn('content',service.call_tool(name,{'claim_id':helper.id}))
                self.assertEqual(service.tmf_assist('helper')['error']['code'],'provider_not_configured')
                self.assertFalse(service.tmf_stale_slice(helper.id)['stale_claim_withheld'])
                self.assertTrue(service.tmf_status()['read_only'])
                self.assertEqual(before,fingerprint(root))
                (repo/'a.py').write_text('VALUE = 2\n\ndef helper():\n    return VALUE + 1\n')
                changed=fingerprint(root)
                self.assertFalse(service.tmf_explain(helper.id)['claim']['fresh'])
                self.assertFalse(service.tmf_explain('legacy_module')['claim']['fresh'])
                self.assertTrue(service.tmf_stale_slice(helper.id)['stale_claim_withheld'])
                service.tmf_context('helper')
                self.assertEqual(changed,fingerprint(root))
                service.store.index.close()

    def test_two_states_and_missing_unsupported(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,sa=fixture(root/'a','alpha');b,sb=fixture(root/'b','beta')
            x=McpService(a,sa,load_assist_provider=False);y=McpService(b,sb,load_assist_provider=False)
            self.assertTrue(x.tmf_context('alpha')['claims']);self.assertTrue(y.tmf_context('beta')['claims'])
            self.assertEqual(x.tmf_context('beta')['claims'],[])
            self.assertEqual(y.tmf_context('alpha')['claims'],[])
            before=fingerprint(root)
            with self.assertRaises(ValueError):ReadOnlyStore(a,root/'missing')
            self.assertEqual(before,fingerprint(root))
            (sa/'schema_version').write_text('future-schema')
            before=fingerprint(root)
            with self.assertRaises(ValueError):ReadOnlyStore(a,sa)
            self.assertEqual(before,fingerprint(root))
            x.store.index.close();y.store.index.close()

    def test_external_refresh_and_corrupt_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo,state=fixture(Path(td));service=McpService(repo,state,load_assist_provider=False)
            count=service.tmf_status()['claims']
            (state/'claims/legacy_module.json').unlink()
            result=json.loads(service.call_tool('tmf_status',{})['content'][0]['text'])
            self.assertEqual(result['claims'],count-1)
            bad=state/'claims/bad.json';bad.write_text('{bad json')
            before=fingerprint(state)
            with self.assertRaises(ValueError):service.call_tool('tmf_status',{})
            self.assertEqual(before,fingerprint(state))
            service.store.index.close()

    def test_modern_version_gates_are_not_bypassed(self):
        with tempfile.TemporaryDirectory() as td:
            repo,state=fixture(Path(td))
            path=next(p for p in (state/'claims').glob('*.json') if p.stem!='legacy_module')
            d=json.loads(path.read_text());d['body']['derivation_versions']={}
            d['bindings'][0]['path'] = 'A.java'
            (repo / 'A.java').write_text('class A {}')
            path.write_text(json.dumps(d))
            service=McpService(repo,state,load_assist_provider=False)
            claim=service.store.get_claim(d['id'])
            result=check_freshness(GitRepo(repo),claim)
            self.assertFalse(result.fresh)
            self.assertTrue(any('derivation version mismatch' in x for x in result.stale_bindings))
            service.store.index.close()

    def test_legacy_cli_and_schemas(self):
        with tempfile.TemporaryDirectory() as td:
            repo,state=fixture(Path(td));before=fingerprint(Path(td))
            request='\n'.join(json.dumps({'jsonrpc':'2.0','id':i,'method':method}) for i,method in enumerate(['initialize','tools/list']))+'\n'
            result=subprocess.run([sys.executable,'-B','-m','tmf.cli','mcp','--repo',str(repo),'--state-root',str(state)],cwd=ROOT,input=request,text=True,capture_output=True,check=True)
            replies=[json.loads(l) for l in result.stdout.splitlines()]
            names={t['name'] for t in replies[1]['result']['tools']}
            self.assertEqual(names,{'tmf_context','tmf_assist','tmf_retrieve','tmf_explain','tmf_callers','tmf_readers','tmf_writers','tmf_subtypes','tmf_status','tmf_stale_slice'})
            self.assertEqual(before,fingerprint(Path(td)))

if __name__=='__main__':unittest.main()
