import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path('/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0')
art = Path('/root/.openclaw/workspace/artifacts/tmf-java-nodes-step0-20260609T1748.tar.gz')
paths = ['tests/test_retrieve_thin.py', 'tests/test_embeddings.py', 'tests/test_calls_edges.py']
code = '''import dataclasses,json,sys\nfrom pathlib import Path\nfrom tmf.git import GitRepo\nfrom tmf.derive import derive_claims_for_path\nrepo=GitRepo(Path(sys.argv[1]))\nclaims=derive_claims_for_path(repo, sys.argv[2])\ndef norm(c):\n d=dataclasses.asdict(c); d.pop("last_verified",None)\n for b in d.get("bindings",[]):\n  b["commit"]="<normalized>"; b["file_blob"]="<normalized>"\n return d\nprint(json.dumps([norm(c) for c in claims if c.scope != "file"], sort_keys=True, ensure_ascii=False))'''
with tempfile.TemporaryDirectory() as td:
    subprocess.run(['tar', '-xzf', str(art), '-C', td, '--strip-components=1'], check=True)
    ok = True
    details = []
    for rel in paths:
        a = subprocess.check_output([sys.executable, '-c', code, str(root), rel], cwd=root, text=True)
        b = subprocess.check_output([sys.executable, '-c', code, td, rel], cwd=td, text=True)
        same = a == b
        details.append({'path': rel, 'byte_identical_normalized': same, 'claims': len(json.loads(a))})
        ok = ok and same
    print(json.dumps({'ok': ok, 'normalization': 'last_verified, binding.commit, binding.file_blob', 'details': details}, indent=2))
    if not ok:
        sys.exit(1)
