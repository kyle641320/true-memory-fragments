#!/usr/bin/env python3
"""Offline rebuild of TMF inverted index from existing claims."""
import sys
from pathlib import Path

# Add tmf to path
sys.path.insert(0, str(Path(__file__).parent))

from tmf.store import Store
from tmf.git import GitRepo

def rebuild_index(repo_root: str | Path):
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    
    print(f"Loading claims from {repo.root}/.tmf/claims/")
    all_claims = list(store.iter_claims())
    print(f"Found {len(all_claims)} claims")
    
    print("Rebuilding inverted index...")
    count = store.index.rebuild(all_claims, batch_size=10000)
    print(f"Indexed {count} claims")
    
    print("Verifying index...")
    snapshot = store.index.status_snapshot(10)
    if snapshot:
        print(f"Index contains {snapshot['claims']} claims")
        print(f"Edge counts: {snapshot.get('edge_counts', {})}")
    else:
        print("Warning: status_snapshot returned None")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Repository root")
    args = parser.parse_args()
    rebuild_index(args.repo)
