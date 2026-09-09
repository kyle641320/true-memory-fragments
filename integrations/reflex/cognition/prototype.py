"""Isolated, trusted-local, offline cognition lifecycle experiment. No TMF imports."""
import ast
import hashlib
import json
import platform
import sqlite3
from pathlib import Path

MAX_SOURCE = 256 * 1024
MAX_PAYLOAD = 12 * 1024
MAX_EVENTS = 64


class Denied(ValueError):
    pass


class Gap(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, reason):
    if not condition:
        raise Denied(reason)


class Store:
    """One explicitly chosen state directory bound permanently to one canonical worktree.

    SQLite transactions commit revision+submitted event together, including CAS events.
    Public API assumes trusted local callers; this is not an authentication boundary.
    failure_hook is test-only and runs immediately before COMMIT (rollback on error).
    """
    def __init__(self, repo, state_root, *, failure_hook=None):
        self.repo = Path(repo).resolve(strict=True)
        require(self.repo.is_dir(), 'repo must be a directory')
        self.root = Path(state_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.failure_hook = failure_hook
        self.identity = {'repo_identity': str(self.repo),
                         'worktree_identity': str(self.repo),
                         'canonical_state_root': str(self.root)}
        self.db = sqlite3.connect(self.root / 'cognition.sqlite', timeout=5)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        try:
            exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone()
            if not exists:
                self.db.executescript('''
                BEGIN IMMEDIATE;
                CREATE TABLE metadata(identity TEXT NOT NULL);
                CREATE TABLE revisions(digest TEXT PRIMARY KEY, artifact TEXT NOT NULL,
                    scope TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX scope_lookup ON revisions(scope, digest);
                CREATE TABLE events(event_id TEXT PRIMARY KEY, revision TEXT NOT NULL
                    REFERENCES revisions(digest), seq INTEGER NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(revision,seq));
                CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions BEGIN
                    SELECT RAISE(ABORT,'immutable revision'); END;
                CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions BEGIN
                    SELECT RAISE(ABORT,'immutable revision'); END;
                CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN
                    SELECT RAISE(ABORT,'append only'); END;
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN
                    SELECT RAISE(ABORT,'append only'); END;
                ''')
                self.db.execute('INSERT INTO metadata VALUES (?)', (canonical(self.identity),))
                self.db.commit()
            identity = self.db.execute('SELECT identity FROM metadata').fetchall()
            require(identity == [(canonical(self.identity),)], 'foreign repo/worktree/state identity')
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _transaction(self, operation):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = operation()
            if self.failure_hook:
                self.failure_hook()
            self.db.commit()
            return result
        except BaseException:
            self.db.rollback()
            raise

    def _source(self, name):
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and p.as_posix() == name,
                'noncanonical source path')
        target = (self.repo / p).resolve(strict=True)
        require(target.is_relative_to(self.repo), 'source escapes repo')
        require(target.is_file(), 'not a regular source file')
        with target.open('rb') as f:
            raw = f.read(MAX_SOURCE + 1)
        require(len(raw) <= MAX_SOURCE, 'source budget exceeded')
        return raw

    def capture(self, paths):
        """Full-file SHA256, not HEAD or function-body freshness; no semantic claim."""
        require(0 < len(paths) <= 16 and len(set(paths)) == len(paths), 'binding budget/duplicates')
        return [{'path': p, 'sha256': digest(self._source(p))} for p in sorted(paths)]

    def _current(self, bindings):
        try:
            return self.capture([b['path'] for b in bindings]) == bindings
        except (OSError, Denied):
            return False

    def revision(self, revision):
        row = self.db.execute('SELECT payload FROM revisions WHERE digest=?', (revision,)).fetchone()
        if not row:
            raise Gap('missing revision')
        require(digest(row[0].encode()) == revision, 'revision integrity failure')
        data = json.loads(row[0])
        require(data['identity'] == self.identity, 'foreign revision')
        return data

    def events(self, revision):
        self.revision(revision)
        rows = self.db.execute('SELECT payload FROM events WHERE revision=? ORDER BY seq LIMIT ?',
                               (revision, MAX_EVENTS + 1)).fetchall()
        if not rows or len(rows) > MAX_EVENTS:
            raise Gap('missing submitted event or event budget exceeded')
        return [json.loads(row[0]) for row in rows]

    def state(self, revision):
        """Deterministic append-only replay. Freshness overlay is read-only."""
        data = self.revision(revision)
        state = dict(review_state='candidate', adoption_state='not_adopted', validity='current',
                     superseded_by=None, validations=[], activations=0, seq=0)
        for e in self.events(revision):
            require(e['expected_seq'] == state['seq'], 'broken event sequence')
            state['seq'] += 1
            kind, body = e['type'], e['body']
            if kind == 'validation':
                state['validations'].append(body)
                # Negative review is deliberately sticky: no implicit rehabilitation.
                if body['result'] == 'failed':
                    state['review_state'] = 'contested'
                elif state['review_state'] == 'candidate' and body['result'] == 'passed':
                    state['review_state'] = 'supported'
            elif kind == 'contest':
                state['review_state'] = 'contested'
            elif kind == 'invalidate':
                state['validity'] = 'invalidated'
            elif kind == 'stale':
                state['validity'] = 'stale'
            elif kind == 'supersede':
                state['validity'] = 'superseded'
                state['superseded_by'] = body['replacement']
            elif kind == 'adopt':
                state['adoption_state'] = 'adopted'
            elif kind == 'activate':
                state['activations'] += 1
            elif kind != 'submitted':
                raise Gap('unknown event')
        if state['validity'] == 'current' and not self._current(data['bindings']):
            state['validity'] = 'stale'
        return state

    def _put_event(self, revision, event_id, kind, body, expected_seq, actor):
        require(isinstance(event_id, str) and 0 < len(event_id) <= 128, 'event id required')
        require(isinstance(actor, str) and 0 < len(actor) <= 128, 'actor required')
        e = dict(event_id=event_id, revision=revision, type=kind, body=body,
                 expected_seq=expected_seq, actor=actor)
        payload = canonical(e)
        require(len(payload.encode()) <= MAX_PAYLOAD, 'event budget exceeded')
        old = self.db.execute('SELECT payload FROM events WHERE event_id=?', (event_id,)).fetchone()
        if old:
            require(old[0] == payload, 'event id reused with different content')
            return False
        count = self.db.execute('SELECT COUNT(*) FROM events WHERE revision=?', (revision,)).fetchone()[0]
        require(count == expected_seq, 'optimistic sequence conflict')
        require(count < MAX_EVENTS, 'event budget exceeded')
        self.db.execute('INSERT INTO events VALUES (?,?,?,?)',
                        (event_id, revision, count + 1, payload))
        return True

    def submit(self, *, artifact, scope, proposition, predicate, bindings, producer,
               limitations, parent=None):
        """Explicit caller-supplied fixture/candidate. No extraction of agent mental state."""
        require(all(isinstance(x, str) and 0 < len(x) <= 1024
                    for x in (artifact, scope, proposition, producer)), 'required candidate text')
        require(isinstance(limitations, list) and bool(limitations)
                and all(isinstance(x, str) for x in limitations), 'limitations required')
        require(set(predicate) == {'kind', 'path', 'function', 'parameter'}
                and predicate['kind'] == 'python_required_parameter'
                and all(isinstance(x, str) and x for x in predicate.values()), 'unsupported predicate')
        require(0 < len(bindings) <= 16 and self._current(bindings), 'stale/incomplete binding vector')
        require(predicate['path'] in {b['path'] for b in bindings}, 'predicate source unbound')
        if parent:
            old = self.revision(parent)
            require(old['artifact'] == artifact and old['scope'] == scope, 'foreign lineage')
        evidence_raw = self._source(predicate['path'])
        require(digest(evidence_raw) == next(b['sha256'] for b in bindings if b['path'] == predicate['path']),
                'evidence snapshot mismatch')
        # Keep one bounded, authoritative full-file snippet for this deliberately small slice.
        require(len(evidence_raw) <= 8 * 1024, 'evidence budget exceeded')
        evidence = dict(path=predicate['path'], sha256=digest(evidence_raw),
                        lines=[1, max(1, len(evidence_raw.splitlines()))],
                        snippet=evidence_raw.decode('utf-8'), kind='source_snapshot')
        data = dict(schema_version=1, artifact=artifact, scope=scope, proposition=proposition,
                    predicate=predicate, bindings=bindings, producer=producer, producer_version='explicit-v1',
                    limitations=limitations, parent=parent, baseline_missing=parent is None,
                    evidence=[evidence], identity=self.identity)
        payload = canonical(data)
        require(len(payload.encode()) <= MAX_PAYLOAD, 'candidate budget exceeded')
        revision = digest(payload.encode())
        def operation():
            require(self._current(bindings), 'source changed during submission')
            self.db.execute('INSERT OR IGNORE INTO revisions VALUES (?,?,?,?)',
                            (revision, artifact, scope, payload))
            self._put_event(revision, 'submitted:' + revision, 'submitted', {}, 0, producer)
            return revision
        return self._transaction(operation)

    def validate(self, revision, event_id, expected_seq):
        """Independent deterministic AST rule, not caller-supplied 'passed'. No code execution.

        Supports one top-level synchronous function and a required positional/kw-only arg.
        Does NOT validate prose, business intent, call sites, runtime or undeclared dependencies.
        """
        def operation():
            data = self.revision(revision)
            s = self.state(revision)
            existing = self.db.execute('SELECT payload FROM events WHERE event_id=?', (event_id,)).fetchone()
            if existing:
                e = json.loads(existing[0])
                require(e['revision'] == revision and e['type'] == 'validation'
                        and e['expected_seq'] == expected_seq, 'event id conflict')
                return e['body']  # Exact committed validation replay, never rerun against new source.
            require(s['validity'] == 'current', 'validation requires current source')
            require(len(s['validations']) < 4, 'validation budget exceeded')
            p = data['predicate']
            raw = self._source(p['path'])
            require(digest(raw) == next(b['sha256'] for b in data['bindings'] if b['path'] == p['path']),
                    'validation snapshot mismatch')
            try:
                tree = ast.parse(raw)
                nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and n.name == p['function']]
                if len(nodes) != 1 or type(nodes[0]) is not ast.FunctionDef or nodes[0].decorator_list:
                    result, actual = 'inconclusive', 'unique undecorated synchronous function unavailable'
                else:
                    args = nodes[0].args
                    positional = args.posonlyargs + args.args
                    required = positional[:len(positional) - len(args.defaults)]
                    names = [a.arg for a in required] + [a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is None]
                    result = 'passed' if p['parameter'] in names else 'failed'
                    actual = sorted(names)
            except (SyntaxError, UnicodeError, ValueError):
                result, actual = 'inconclusive', 'parse failure'
            require(self._current(data['bindings']), 'source changed during validation')
            body = dict(result=result, predicate=p, scope=data['scope'], source_vector=data['bindings'],
                        input_sha256=digest(raw), expected=p['parameter'], actual=actual,
                        rule='ast-required-parameter-v1', rule_sha256=digest(Path(__file__).read_bytes()),
                        environment='CPython ' + platform.python_version(),
                        invocation='Store.validate', limitations=['AST declaration only; not runtime or business correctness'])
            self._put_event(revision, event_id, 'validation', body, expected_seq, 'deterministic-ast-rule-v1')
            return body
        return self._transaction(operation)

    def _eligible(self, revision, scope):
        data, s = self.revision(revision), self.state(revision)
        return (data['scope'] == scope and s['review_state'] == 'supported'
                and s['validity'] == 'current'
                and any(v['result'] == 'passed' and v['source_vector'] == data['bindings']
                        and v['predicate'] == data['predicate'] and v['scope'] == scope
                        and v['rule_sha256'] == digest(Path(__file__).read_bytes())
                        and v['environment'] == 'CPython ' + platform.python_version()
                        for v in s['validations']))

    def record(self, revision, event_id, kind, body, expected_seq, actor='explicit-local-host'):
        """No API to self-declare supported/passed. Adoption is a claimed action reference only."""
        require(kind in {'contest', 'invalidate', 'stale', 'adopt', 'activate', 'supersede'}, 'event type denied')
        def operation():
            data = self.revision(revision)
            # Check duplicate payload before admission/CAS: replay is not a new activation.
            e = dict(event_id=event_id, revision=revision, type=kind, body=body,
                     expected_seq=expected_seq, actor=actor)
            old = self.db.execute('SELECT payload FROM events WHERE event_id=?', (event_id,)).fetchone()
            if old:
                require(old[0] == canonical(e), 'event id conflict')
                return False
            if kind in {'contest', 'invalidate'}:
                require(set(body) == {'reason', 'evidence_ref', 'scope', 'predicate', 'source_vector'}
                        and body['scope'] == data['scope'] and body['predicate'] == data['predicate']
                        and body['source_vector'] == data['bindings'] and body['reason'] and body['evidence_ref'],
                        'scoped negative evidence required')
            elif kind == 'stale':
                require(set(body) == {'reason'} and body['reason'] and not self._current(data['bindings']),
                        'stale event requires source mismatch')
            elif kind in {'adopt', 'activate'}:
                require(set(body) == {'scope', 'session', 'run', 'tool_call', 'action_ref'}
                        and all(isinstance(v, str) and v for v in body.values()), 'scoped action reference required')
                require(self._eligible(revision, body['scope']), 'admission denied')
            elif kind == 'supersede':
                require(set(body) == {'replacement'}, 'replacement required')
                replacement = self.revision(body['replacement'])
                require(replacement['parent'] == revision and replacement['artifact'] == data['artifact']
                        and replacement['scope'] == data['scope'], 'replacement lineage mismatch')
                require(self._eligible(body['replacement'], data['scope']), 'replacement not supported/current')
                require(self.state(revision)['validity'] != 'superseded', 'already superseded')
            return self._put_event(revision, event_id, kind, body, expected_seq, actor)
        return self._transaction(operation)

    def retrieve(self, scope, *, limit=3, max_bytes=4096, window=16):
        """Exact task scope; bounded candidate window; no warm, repair or activation writes."""
        require(1 <= limit <= 3 and 1 <= max_bytes <= 4096 and 1 <= window <= 16, 'retrieval budget')
        indexes = {r[1] for r in self.db.execute('PRAGMA index_list(revisions)')}
        if 'scope_lookup' not in indexes:
            return {'items': [], 'gap': 'missing_scope_index', 'truncated': False}
        rows = self.db.execute('SELECT digest FROM revisions INDEXED BY scope_lookup WHERE scope=? '
                               'ORDER BY digest LIMIT ?', (scope, window + 1)).fetchall()
        items, used, truncated = [], 0, len(rows) > window
        for (revision,) in rows[:window]:
            if not self._eligible(revision, scope):
                continue
            d = self.revision(revision)
            item = {k: d[k] for k in ('artifact', 'scope', 'proposition', 'predicate', 'limitations', 'parent', 'baseline_missing')}
            item.update(revision=revision, source_bindings=d['bindings'],
                        assurance='scoped AST predicate only; prose unverified',
                        validation_event_refs=[e['event_id'] for e in self.events(revision) if e['type'] == 'validation'])
            size = len(canonical(item).encode())
            if len(items) >= limit or used + size > max_bytes:
                truncated = True
                continue
            items.append(item)
            used += size
        return {'items': items, 'gap': None, 'truncated': truncated, 'item_bytes': used}

    def rebuild_index(self):
        """Explicit maintenance only. A missing index never silently means no old records."""
        return self._transaction(lambda: self.db.execute(
            'CREATE INDEX IF NOT EXISTS scope_lookup ON revisions(scope, digest)') and None)
