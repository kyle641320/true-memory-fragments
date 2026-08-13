import hashlib,json,unittest
from pathlib import Path
R=Path(__file__).parents[1]
class Frozen(unittest.TestCase):
 def test_shape(self):
  m=json.loads((R/'manifest.json').read_text()); self.assertEqual(len(m['tasks']),10); self.assertEqual({x['kind'] for x in m['tasks']},{'understanding','local_edit','cross_file_trace','test_fix'}); self.assertEqual({x['language'] for x in m['tasks']},{'python','java'})
 def test_frozen(self):
  for line in (R/'FROZEN.sha256').read_text().splitlines():
   h,p=line.split('  '); self.assertEqual(hashlib.sha256((R/p).read_bytes()).hexdigest(),h)
if __name__=='__main__':unittest.main()
