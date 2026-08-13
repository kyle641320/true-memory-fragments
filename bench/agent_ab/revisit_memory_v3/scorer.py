from __future__ import annotations

ENUM_SOURCE={'SOURCE','MEMORY','NONE'}; ENUM_HIT={'HIT','MISS','NOT_APPLICABLE'}

def structural_errors(answer, requested_field):
    issues=[]
    if not isinstance(answer,dict): return ['not_object']
    required={'evidence_source','memory_hit',requested_field,'citations'}
    for key in sorted(required-set(answer)): issues.append('missing_'+key)
    if answer.get('evidence_source') not in ENUM_SOURCE: issues.append('bad_evidence_source')
    if answer.get('memory_hit') not in ENUM_HIT: issues.append('bad_memory_hit')
    if requested_field=='value' and type(answer.get(requested_field)) is not int: issues.append('bad_value_type')
    if requested_field=='exists' and type(answer.get(requested_field)) is not bool: issues.append('bad_exists_type')
    cites=answer.get('citations')
    if not isinstance(cites,list): issues.append('bad_citations_type')
    elif not cites: issues.append('empty_citations')
    elif any(not isinstance(c,dict) or set(c)!={'path','line'} or not isinstance(c.get('path'),str) or type(c.get('line')) is not int for c in cites): issues.append('bad_citation_item')
    extra=set(answer)-required
    if extra: issues.append('extra_fields:'+','.join(sorted(extra)))
    return issues

def score(answer,golden,arm):
    field=next(iter(golden['expected_fields'])); issues=structural_errors(answer,field)
    if not isinstance(answer,dict): return {'valid':False,'correct':False,'citation_ok':False,'issues':issues}
    if answer.get('evidence_source') != golden['expected_evidence_source'][arm]: issues.append('wrong_evidence_source')
    if answer.get('memory_hit') != golden['expected_memory_hit'][arm]: issues.append('wrong_memory_hit')
    value=golden['expected_fields'][field]
    if field in answer and (type(answer[field]) is not type(value) or answer[field]!=value): issues.append('wrong_'+field)
    cites=answer.get('citations'); citation_ok=isinstance(cites,list) and any(isinstance(c,dict) and c.get('path')==golden['citation']['path'] and type(c.get('line')) is int and c['line'] in golden['citation']['lines'] for c in cites)
    if not citation_ok: issues.append('wrong_citation')
    return {'valid':not structural_errors(answer,field),'correct':not issues,'citation_ok':citation_ok,'issues':issues}
