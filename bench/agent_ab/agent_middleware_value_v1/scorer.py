"""Frozen mechanical scorer helpers."""
from pathlib import Path

def citations_valid(answer, work):
    cites=answer.get('citations',[]) if isinstance(answer,dict) else []
    return bool(cites) and all(isinstance(c,str) and ':' in c and (work/c.split(':')[0]).exists() for c in cites)

def diff_valid(task_id, work):
    text='\n'.join(p.read_text(errors='replace') for p in work.iterdir() if p.is_file())
    checks={'A03':'.strip().lower()','A04':'Math.min(n, 80)','A07':'n + 1','A08':'n % 2 == 0'}
    return checks.get(task_id,'') in text
