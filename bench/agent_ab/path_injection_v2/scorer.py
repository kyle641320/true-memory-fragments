def structural_errors(a,field):
 if not isinstance(a,dict): return ['not_object']
 e=[]
 if set(a)!={'answer','citations'}:e.append('fields')
 if type(a.get('answer')) is not (bool if field=='exists' else int):e.append('answer_type')
 c=a.get('citations')
 if not isinstance(c,list) or not c:e.append('citations')
 elif any(not isinstance(x,dict) or set(x)!={'path','line'} or not isinstance(x['path'],str) or type(x['line']) is not int for x in c):e.append('citation_item')
 return e
def score(a,g):
 field=next(iter(g['expected_fields']));e=structural_errors(a,field);v=g['expected_fields'][field];correct=not e and a['answer']==v and type(a['answer']) is type(v);cite=not e and any(x['path']==g['citation']['path'] and x['line'] in g['citation']['lines'] for x in a['citations']);return {'valid':not e,'correct':correct,'citation_ok':cite,'issues':e+([] if correct else ['wrong_answer'])+([] if cite else ['wrong_citation'])}
