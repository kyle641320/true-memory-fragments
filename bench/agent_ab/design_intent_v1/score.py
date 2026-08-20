#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def human_template(result):
    lines=['# design_intent_v1 Human Audit Template','', 'Machine scoring is primary for freshness/read telemetry; humans audit design-intent score (0/1/2).','']
    for t in result['tasks']:
        lines += [f"## {t['task_id']}", '']
        for r in t['rows']:
            ans=((r.get('answer') or {}).get('answer') or '').replace('\n',' ')
            lines += [f"### {r['arm']}", f"- Machine design score: {r['score']['design_score_machine']}", f"- Chain completeness: {r['score']['chain_completeness']:.2f}", f"- Source bytes read: {r['telemetry']['source_bytes']}", f"- Human score (0/1/2): TBD", f"- Answer excerpt: {ans[:700]}", '']
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('result',nargs='?',default=str(HERE/'results'/'smoke-n2.json')); args=ap.parse_args()
    p=Path(args.result); data=json.loads(p.read_text())
    out=p.with_suffix('.human_audit.md'); out.write_text(human_template(data))
    print('wrote',out)
if __name__=='__main__': main()
