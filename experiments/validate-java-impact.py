#!/usr/bin/env python3
"""
Validate TMF's Java impact analysis capability.

Given a class name (e.g., OwnerService), find all methods that read fields of that type.
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import Set, List, Tuple

def find_type_readers(db_path: str, tmf_root: Path, target_class: str) -> List[dict]:
    """
    Find all methods that read fields typed as target_class.
    
    Algorithm:
    1. Find the class claim for target_class
    2. Find all fields with uses_type → target_class
    3. Find all methods with reads → those fields
    4. Return method details
    """
    db = sqlite3.connect(db_path)
    results = []
    
    try:
        # Step 1: Find target class claim
        print(f"[1/3] Looking for class: {target_class}")
        class_claim_id = None
        
        for row in db.execute("""
            SELECT id 
            FROM claims 
            WHERE search_text LIKE ?
              AND (scope = 'class' OR scope = 'declaration')
            LIMIT 5
        """, (f'%{target_class}%',)):
            claim_path = tmf_root / 'claims' / f'{row[0]}.json'
            if claim_path.exists():
                with open(claim_path) as f:
                    claim = json.load(f)
                qualname = claim['body'].get('qualname', '')
                if qualname == target_class or qualname.endswith(f'.{target_class}'):
                    class_claim_id = row[0]
                    print(f"  ✓ Found: {qualname} ({class_claim_id})")
                    break
        
        if not class_claim_id:
            print(f"  ✗ Class {target_class} not found in TMF index")
            return results
        
        # Step 2: Find all fields typed as this class
        print(f"\n[2/3] Finding fields with type {target_class}")
        field_ids = set()
        
        for row in db.execute("""
            SELECT endpoint
            FROM edge_endpoints 
            WHERE relation_kind = 'uses_type'
              AND endpoint_role = 'type_id'
              AND edge_id IN (
                SELECT edge_id 
                FROM edge_endpoints
                WHERE endpoint = ?
                  AND relation_kind = 'uses_type'
              )
        """, (class_claim_id,)):
            # Get the user_id (field) from the edge
            for edge_row in db.execute("""
                SELECT endpoint
                FROM edge_endpoints
                WHERE edge_id IN (
                  SELECT edge_id
                  FROM edge_endpoints
                  WHERE endpoint = ?
                    AND relation_kind = 'uses_type'
                    AND endpoint_role = 'type_id'
                )
                AND endpoint_role = 'user_id'
                AND relation_kind = 'uses_type'
            """, (class_claim_id,)):
                field_id = edge_row[0]
                field_ids.add(field_id)
                
                # Get field details
                field_claim_path = tmf_root / 'claims' / f'{field_id}.json'
                if field_claim_path.exists():
                    with open(field_claim_path) as f:
                        field_claim = json.load(f)
                    field_qualname = field_claim['body'].get('qualname', 'unknown')
                    print(f"  • {field_qualname}")
        
        print(f"  Found {len(field_ids)} fields")
        
        if not field_ids:
            print(f"  ✗ No fields found with type {target_class}")
            return results
        
        # Step 3: Find all methods that read these fields
        print(f"\n[3/3] Finding methods that read these fields")
        seen_methods = set()
        
        for field_id in field_ids:
            for row in db.execute("""
                SELECT endpoint
                FROM edge_endpoints
                WHERE edge_id IN (
                  SELECT edge_id
                  FROM edge_endpoints
                  WHERE endpoint = ?
                    AND relation_kind = 'reads'
                    AND endpoint_role = 'declaration_id'
                )
                AND endpoint_role = 'reader_id'
                AND relation_kind = 'reads'
            """, (field_id,)):
                method_id = row[0]
                
                if method_id in seen_methods:
                    continue
                seen_methods.add(method_id)
                
                # Get method details
                method_claim_path = tmf_root / 'claims' / f'{method_id}.json'
                if method_claim_path.exists():
                    with open(method_claim_path) as f:
                        method_claim = json.load(f)
                    
                    qualname = method_claim['body'].get('qualname', 'unknown')
                    binding = method_claim['bindings'][0] if method_claim['bindings'] else {}
                    path = binding.get('path', 'unknown')
                    line_start = binding.get('line_start', 0)
                    line_end = binding.get('line_end', 0)
                    
                    results.append({
                        'claim_id': method_id,
                        'qualname': qualname,
                        'path': path,
                        'line_start': line_start,
                        'line_end': line_end,
                    })
                    
                    print(f"  → {qualname}")
                    print(f"     {path}:{line_start}-{line_end}")
        
    finally:
        db.close()
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-java-impact.py <ClassName>")
        print("Example: validate-java-impact.py OwnerService")
        sys.exit(1)
    
    target_class = sys.argv[1]
    
    # Paths
    db_path = '/tmp/spring-petclinic/.tmf/index/claims.sqlite3'
    tmf_root = Path('/tmp/spring-petclinic/.tmf')
    
    if not Path(db_path).exists():
        print(f"✗ TMF database not found: {db_path}")
        print("Run: cd /tmp/spring-petclinic && python3 /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/tmf/index.py")
        sys.exit(1)
    
    print(f"=== TMF Java Impact Analysis ===")
    print(f"Target class: {target_class}")
    print(f"Database: {db_path}\n")
    
    results = find_type_readers(db_path, tmf_root, target_class)
    
    print(f"\n=== Summary ===")
    print(f"Total methods affected: {len(results)}")
    
    if results:
        print("\n=== Blast Radius ===")
        for r in results:
            print(f"  {r['qualname']}")
            print(f"    {r['path']}:{r['line_start']}-{r['line_end']}")


if __name__ == '__main__':
    main()
