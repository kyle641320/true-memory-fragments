from __future__ import annotations
ENUM_SOURCE={'SOURCE','MEMORY','NONE'}; ENUM_HIT={'HIT','MISS','NOT_APPLICABLE'}
def score(answer,golden,arm):
 issues=[]
 if not isinstance(answer,dict): return {'valid':False,'correct':False,'citation_ok':False,'issues':['not_object']}
 if answer.get('evidence_source') not in ENUM_SOURCE: issues.append('bad_evidence_source')
 if answer.get('memory_hit') not in ENUM_HIT: issues.append('bad_memory_hit')
 if answer.get('evidence_source') != golden['expected_evidence_source'][arm]: issues.append('wrong_evidence_source')
 if answer.get('memory_hit') != golden['expected_memory_hit'][arm]: issues.append('wrong_memory_hit')
 for k,v in golden['expected_fields'].items():
  if k not in answer: issues.append('missing_'+k)
  elif type(answer[k]) is not type(v) or answer[k]!=v: issues.append('wrong_'+k)
 cites=answer.get('citations'); citation_ok=isinstance(cites,list) and any(isinstance(c,dict) and c.get('path')==golden['citation']['path'] and type(c.get('line')) is int and c['line'] in golden['citation']['lines'] for c in cites)
 if not citation_ok:issues.append('wrong_citation')
 valid=not any(x.startswith('bad_') or x.startswith('missing_') or x=='not_object' for x in issues) and isinstance(cites,list)
 return {'valid':valid,'correct':not issues,'citation_ok':citation_ok,'issues':issues}
