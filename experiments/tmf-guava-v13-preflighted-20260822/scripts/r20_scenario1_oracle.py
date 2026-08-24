#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

HOOK = 'recordRefreshCompletionHook'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--hook', default=HOOK)
    args = ap.parse_args()
    text = Path(args.file).read_text()

    refresh_pos = text.find('void refresh(K key)')
    load_async_pos = text.find('ListenableFuture<V> loadAsync(')
    listener_pos = text.find('loadingFuture.addListener(')
    hook_pos = text.find(args.hook)

    if refresh_pos < 0:
        print(json.dumps({'ok': False, 'error': 'refresh not found'}))
        return 2
    if load_async_pos < 0:
        print(json.dumps({'ok': False, 'error': 'loadAsync not found'}))
        return 2
    if hook_pos < 0:
        print(json.dumps({'ok': False, 'error': 'hook not found'}))
        return 2

    in_refresh = refresh_pos <= hook_pos < load_async_pos
    in_listener = listener_pos >= 0 and listener_pos <= hook_pos
    pass_completion = in_listener and not in_refresh

    result = {
        'schema': 'r20-scenario1-oracle-v2',
        'file': str(args.file),
        'hook': args.hook,
        'hook_pos': hook_pos,
        'refresh_pos': refresh_pos,
        'load_async_pos': load_async_pos,
        'listener_pos': listener_pos,
        'in_refresh_initiation_span': in_refresh,
        'in_completion_listener_span': in_listener,
        'pass': pass_completion,
        'classification': 'completion_path' if pass_completion else ('initiation_path' if in_refresh else 'missing_or_ambiguous'),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if pass_completion else 2


if __name__ == '__main__':
    raise SystemExit(main())
