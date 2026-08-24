#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

repo = Path(sys.argv[1])
cm = repo/'guava/src/com/google/common/collect/CompactHashMap.java'
ch = repo/'guava/src/com/google/common/collect/CompactHashing.java'
text = cm.read_text()
cht = ch.read_text()
res = {'repo': str(repo)}
res['phase_b_floor_8'] = 'MIN_HASH_TABLE_SIZE = 8' in cht
m = re.search(r'static\s+int\s+estimateSmallTableBucketsForUi\s*\(\s*int\s+expectedSize\s*\)\s*\{(?P<body>.*?)\n\s*\}', text, re.S)
res['helper_exists'] = bool(m)
body = m.group('body') if m else ''
res['body'] = body.strip()
res['forbidden_calls'] = [x for x in ['CompactHashing.tableSize','allocArrays','new CompactHashMap','createWithExpectedSize'] if x in body]
res['contains_8'] = re.search(r'\b8\b', body) is not None
res['contains_4'] = re.search(r'\b4\b', body) is not None
# direct/simple: accept explicit return 8 or max(8,...), reject 4 and forbidden calls.
res['hidden_pass'] = bool(res['phase_b_floor_8'] and res['helper_exists'] and not res['forbidden_calls'] and res['contains_8'] and not res['contains_4'])
print(json.dumps(res, ensure_ascii=False, indent=2))
sys.exit(0 if res['hidden_pass'] else 1)
