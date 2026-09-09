"""Explicit trusted-local recovery ticket → unchanged cognition Store seam.
No authentication, automatic extraction, validation, adoption, or reactivation.
"""
import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from .prototype import Store, require, digest


@dataclass(frozen=True)
class ObservationContext:
    """Explicit trusted-local caller route; never reconstructed from a ticket.

    Mechanical and cognition roots intentionally have separate identities.
    This object does not authenticate the caller or confer host authority.
    """
    repo_root: str
    mechanical_state_root: str
    cognition_state_root: str
    session_key: str | None
    session_id: str | None
    run: str
    tool_call: str


def load_observation(ticket, store, *, context):
    require(isinstance(context, ObservationContext), 'explicit caller context required')
    for value in (context.repo_root, context.mechanical_state_root, context.cognition_state_root):
        require(isinstance(value, str) and value and str(Path(value).resolve()) == value,
                'canonical caller route required')
    require(context.repo_root == str(store.repo) and context.cognition_state_root == str(store.root),
            'foreign cognition store route')
    require(context.session_key is not None or context.session_id is not None, 'missing caller session')
    values = [v for v in (context.session_key, context.session_id) if v is not None]
    values += [context.run, context.tool_call]
    for value in values:
        require(isinstance(value, str) and value.strip() and len(value) <= 512,
                'invalid caller identity')
    with Path(ticket).open('rb') as f:
        raw = f.read(160 * 1024 + 1)
    require(len(raw) <= 160 * 1024, 'observation budget')
    o = json.loads(raw)
    require(o['schema'] == 'tmf.recovery-observation.v1', 'observation schema')
    require(o['status'] == 'recovery_released_without_consolidation', 'not a release observation')
    require(o['canonical_repo_root'] == str(store.repo), 'foreign observation repo')
    require(o['canonical_state_root'] == context.mechanical_state_root, 'foreign mechanical state route')
    require(o['identity']['runId'] and o['identity']['toolCallId']
            and (o['identity']['sessionKey'] or o['identity']['sessionId']), 'missing receipt identity')
    actual_identity = [o['identity']['sessionKey'] or o['identity']['sessionId'],
                       o['identity']['runId'], o['identity']['toolCallId']]
    require(o['identity']['sessionKey'] == context.session_key
            and o['identity']['sessionId'] == context.session_id
            and actual_identity == [context.session_key or context.session_id, context.run, context.tool_call],
            'foreign recovery identity')
    require(json.loads(o['receipt_key']) == actual_identity, 'receipt identity mismatch')
    v = o['postmutation_vector']
    bindings = [{'path': b['path'], 'sha256': b['sha256']} for b in v]
    require(store.capture([b['path'] for b in bindings]) == bindings, 'postimage/current dependency drift')
    require(all(digest(b['snippet'].encode()) == b['sha256'] for b in v), 'postimage evidence mismatch')
    for b in v:
        data = b['snippet'].encode()
        require(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == b['git_blob'], 'git blob evidence mismatch')
    deps = o['observed_dependencies']
    require(deps and all(d['read_observed'] and d['observed_git_blob'] for d in deps), 'missing read evidence')
    require(set(b['path'] for b in v) == {d['path'] for d in deps} | {o['mutation']['target']}, 'incomplete vector')
    # Recovery of a callsite must not silently consolidate a changed dependency.
    for d in deps:
        require(next(b['git_blob'] for b in v if b['path'] == d['path']) == d['observed_git_blob'],
                'dependency changed since Read; needs new observation')
    return o, bindings


@dataclass(frozen=True)
class CognitionIdentity:
    artifact: str
    task_scope: str


PROVENANCE_PREFIX = 'tmf-recovery-provenance-v1:'


def stable_keys(identity, context):
    require(isinstance(identity, CognitionIdentity), 'explicit cognition identity required')
    for value in (identity.artifact, identity.task_scope):
        require(isinstance(value, str) and 0 < len(value) <= 256 and value == value.strip(),
                'invalid stable cognition identity')
    route = dict(repo=context.repo_root, mechanical=context.mechanical_state_root,
                 cognition=context.cognition_state_root)
    def key(value):
        return digest(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())
    scope = 'task:' + key(dict(route=route, task_scope=identity.task_scope))
    artifact = 'cognition:' + key(dict(route=route, identity=asdict(identity)))
    return artifact, scope


def provenance(observation, context, identity):
    raw = json.dumps(observation, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return dict(schema='tmf.recovery-provenance.v1', observation_digest=digest(raw),
                context=asdict(context), cognition_identity=asdict(identity))


def provenance_entry(value):
    return PROVENANCE_PREFIX + json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def stored_provenance(revision):
    entries = [x for x in revision['limitations'] if x.startswith(PROVENANCE_PREFIX)]
    require(len(entries) == 1, 'missing or ambiguous revision provenance')
    value = json.loads(entries[0][len(PROVENANCE_PREFIX):])
    require(provenance_entry(value) == entries[0] and value['schema'] == 'tmf.recovery-provenance.v1',
            'invalid revision provenance')
    return value


def submit_candidate(store, ticket, *, context, identity, path, function, parameter, producer, parent=None):
    o, bindings = load_observation(ticket, store, context=context)
    require(any(d['path'] == path and d['qualname'] == function for d in o['observed_dependencies']),
            'predicate outside observed dependency declaration')
    artifact, scope = stable_keys(identity, context)
    if parent is not None:
        prior = store.revision(parent)
        require(prior['artifact'] == artifact and prior['scope'] == scope, 'foreign cognition lineage')
        pp = stored_provenance(prior)
        require(pp['cognition_identity'] == asdict(identity), 'foreign parent cognition identity')
        for field in ('repo_root', 'mechanical_state_root', 'cognition_state_root'):
            require(pp['context'][field] == getattr(context, field), 'foreign parent route')
    return store.submit(artifact=artifact, scope=scope,
        proposition=f'{path}::{function} requires parameter {parameter}',
        predicate=dict(kind='python_required_parameter', path=path, function=function, parameter=parameter),
        bindings=bindings, producer=producer, parent=parent,
        limitations=['AST declaration only; callsite/runtime/business semantics unverified',
                     'Trusted-local caller context is not authenticated adoption',
                     'No adoption, activation or supersession performed',
                     provenance_entry(provenance(o, context, identity))])


def validate_candidate(store, ticket, revision, *, context, identity, event_id, expected_seq):
    o, bindings = load_observation(ticket, store, context=context)
    r = store.revision(revision)
    artifact, scope = stable_keys(identity, context)
    require(r['artifact'] == artifact and r['scope'] == scope and r['bindings'] == bindings,
            'foreign observation candidate')
    require(stored_provenance(r) == provenance(o, context, identity), 'revision provenance mismatch')
    return store.validate(revision, event_id, expected_seq)
