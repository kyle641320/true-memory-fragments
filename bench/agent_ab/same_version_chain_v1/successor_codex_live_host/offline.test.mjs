import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {anomalyIn, buildRunParams, completionProjection, ControlChannel, createBridge,
  MAX_FRAME, ObservableOutputTracker, qualify, TOOL_NAME} from './bridge.mjs';

const profile = {
  provider: 'openai', request_model: 'openai/gpt-5.6-sol', native_model: 'gpt-5.6-sol',
  reasoning_effort: 'medium', openclaw_version: '2026.9.2', runtime: 'openclaw-codex-app-server',
  model_fallback_allowed: false, platform_api_allowed: false,
  budget: {native_inference_pre_reservation_required: false, max_runtime_observable_output_bytes: 120000},
  permissions: {project_docs: false, native_shell: false, delegation: false},
  common_protocol_carrier: 'exact common carrier',
  native_tool: {name: TOOL_NAME, description: 'exact', input_schema: {oneOf: [{type: 'object'}]}},
};
const start = {kind: 'start', profile, tool: profile.native_tool, timeout_ms: 2000,
  scientific_messages: [{role: 'system', content: '  exact system\n中文\n'}, {role: 'user', content: '\nexact user  '}]};

test('public parameter mapping keeps science strings, request controls, auth ownership and limits', () => {
  const signal = new AbortController().signal;
  const p = buildRunParams(start, {runtimeDirectory: '/private/run', authProfileId: 'openai:existing',
    sessionId: 'opaque', runId: 'run', config: {}}, {abortSignal: signal});
  assert.equal(p.prompt, start.scientific_messages[1].content);
  assert.equal(p.transcriptPrompt, p.prompt);
  assert.equal(p.extraSystemPrompt, start.scientific_messages[0].content + '\n\nexact common carrier');
  assert.deepEqual([p.provider, p.model, p.thinkLevel, p.agentHarnessId], ['openai', 'gpt-5.6-sol', 'medium', 'codex']);
  assert.equal(p.authProfileIdSource, 'user'); assert.equal(p.modelSelectionLocked, true);
  assert.deepEqual(p.toolsAllow, [TOOL_NAME]); assert.deepEqual(p.toolExecutionAllow, [TOOL_NAME]);
  assert.deepEqual(p.modelFallbacksOverride, []); assert.equal(p.abortSignal, signal);
  assert.equal(p.bootstrapContextMode, 'lightweight'); assert.equal(p.timeoutMs, 2000);
});

test('altered requested effort and timeout are rejected before any fake API call', () => {
  for (const patch of [{profile: {...profile, reasoning_effort: 'high'}}, {timeout_ms: 300001}]) {
    assert.throws(() => buildRunParams({...start, ...patch}, {}, {}));
  }
});

test('anomaly detection reads structural metadata, not arbitrary scientific or assistant text', () => {
  assert.equal(anomalyIn('onRunProgress', {reason: 'notification:model/rerouted'}), 'model_rerouted');
  assert.equal(anomalyIn('onAgentEvent', {stream: 'fallback', data: {fromModel: 'gpt-5.6-sol', toModel: 'other', reason: 'capacity'}}), 'model_rerouted');
  assert.equal(anomalyIn('onAgentEvent', {stream: 'assistant', data: {text: 'model/rerouted tool_bypass effort_drift'}}), null);
  assert.equal(anomalyIn('after_tool_call', {toolName: TOOL_NAME, result: {text: 'configuration_drift'}}), null);
  assert.equal(anomalyIn('llm_input', {model: 'other'}), 'model_mismatch');
  assert.equal(anomalyIn('onExecutionPhase', {provider: 'other'}), 'model_mismatch');
  assert.equal(anomalyIn('onExecutionPhase', {backend: 'builtin'}), 'configuration_drift');
  assert.equal(anomalyIn('runtime', {reasoningEffort: 'high'}), 'effort_drift');
  assert.equal(anomalyIn('runtime', {openclawVersion: '2026.9.5'}), 'configuration_drift');
  assert.equal(anomalyIn('runtime', {meta: {agentMeta: {runtimeModelSelection: {provider: 'openai', model: 'other'}}}}), 'model_mismatch');
  assert.equal(anomalyIn('runtime', {modelProvider: 'other'}), 'model_mismatch');
  assert.equal(anomalyIn('runtime', {agentHarnessRuntime: 'other'}), 'configuration_drift');
  assert.equal(anomalyIn('runtime', {meta: {agentMeta: {credentialSource: {kind: 'direct'}}}}), 'configuration_drift');
  assert.equal(anomalyIn('onAgentEvent', {stream: 'tool', data: {name: 'exec'}}), 'tool_bypass');
});

test('observable output counts incremental snapshots only within the same projection identity', () => {
  const o = new ObservableOutputTracker();
  assert.equal(o.observe('onAgentEvent', {stream: 'assistant', data: {itemId: 'a', text: 'abc', delta: 'abc'}}), 'abc');
  assert.equal(o.observe('onAgentEvent', {stream: 'assistant', data: {itemId: 'a', text: 'abcd', delta: 'd'}}), 'd');
  assert.equal(o.observe('onAgentEvent', {stream: 'assistant', data: {text: 'abcd'}}), 'abcd');
  assert.equal(o.observe('onAgentEvent', {stream: 'item', data: {kind: 'preamble', itemId: 'p', progressText: 'hello'}}), 'hello');
  assert.equal(o.observe('onReasoningStream', {text: 'reason', isReasoningSnapshot: true}), 'reason');
  assert.equal(o.observe('onReasoningStream', {text: 'reason more', isReasoningSnapshot: true}), ' more');
});

test('identical text on distinct reasoning and assistant channels cannot evade output cap', async t => {
  let aborted;
  const text = 'x'.repeat(70000);
  const f = fakeHarness(t, async params => {
    params.onReasoningStream({text, isReasoningSnapshot: true});
    assert.equal(params.abortSignal.aborted, false);
    params.onAgentEvent({stream: 'assistant', data: {text}});
    aborted = params.abortSignal.aborted;
    return {meta: {}};
  });
  createBridge(f.api, f.options, f.channel);
  const finished = new Promise(resolve => f.channel.once('finished', resolve));
  f.channel.emit('frame', start); await finished;
  assert.equal(aborted, true);
  assert.equal(f.channel.frames.at(-1).reason, 'runtime_output_budget_exceeded');
});

test('projection reports missing usage/count/cost as unknown rather than fabricated zero', () => {
  const projected = completionProjection({meta: {agentMeta: {provider: 'openai', model: 'gpt-5.6-sol', costUsd: 12.5}}});
  assert.equal(projected.usage, null); assert.equal(projected.retryCount, null);
  assert.equal(projected.modelIterations, null); assert.equal(projected.costUsd, null);
});

test('dedicated JSONL channel rejects oversize, invalid JSON and malformed shape', () => {
  for (const data of [Buffer.alloc(MAX_FRAME, 120), Buffer.from('{bad}\n'), Buffer.from('[]\n')]) {
    const socket = new EventEmitter(); socket.write = () => {}; socket.end = () => {};
    const channel = new ControlChannel(socket); let failed = false;
    channel.on('failure', () => { failed = true; }); socket.emit('data', data);
    assert.equal(failed, true);
  }
});

test('fragmented and coalesced frames preserve exact ordering', () => {
  const socket = new EventEmitter(); socket.write = () => {}; socket.end = () => {};
  const channel = new ControlChannel(socket); const received = [];
  channel.on('frame', frame => received.push(frame.kind));
  socket.emit('data', Buffer.from('{"kind":"sta'));
  socket.emit('data', Buffer.from('rt"}\n{"kind":"halt"}\n'));
  assert.deepEqual(received, ['start', 'halt']);
});

test('real child socket flushes final frame and exits without awaiting parent FIN', async () => {
  const bridgeUrl = new URL('./bridge.mjs', import.meta.url).href;
  const source = `import {Socket} from 'node:net'; import {ControlChannel} from ${JSON.stringify(bridgeUrl)};
    const channel=new ControlChannel(new Socket({fd:3,readable:true,writable:true}));
    channel.on('failure',()=>{}); channel.send({kind:'completed',result:{modelCalls:0}}); await channel.finish();`;
  const child = spawn(process.execPath, ['--input-type=module', '-e', source], {stdio: ['ignore', 'pipe', 'pipe', 'pipe']});
  const bytes = []; child.stdio[3].on('data', chunk => bytes.push(chunk));
  child.stdout.resume(); child.stderr.resume();
  const timer = setTimeout(() => child.kill('SIGKILL'), 3000);
  const code = await new Promise(resolve => child.once('close', resolve)); clearTimeout(timer);
  assert.equal(code, 0); assert.equal(JSON.parse(Buffer.concat(bytes).toString()).kind, 'completed');
});

function fakeHarness(t, runEmbeddedAgent) {
  const root = mkdtempSync(path.join(tmpdir(), 'successor-host-offline-'));
  t.after(() => rmSync(root, {recursive: true})); mkdirSync(path.join(root, 'carrier'));
  const options = {runtimeDirectory: root, authProfileId: 'openai:offline-only'};
  const config = {plugins: {entries: {'tmf-successor-host': {config: options}, codex: {config: {appServer: {transport: 'stdio'}}}}},
    agents: {defaults: {model: {primary: 'openai/gpt-5.6-sol', fallbacks: []}}},
    auth: {profiles: {[options.authProfileId]: {mode: 'oauth'}}}};
  writeFileSync(path.join(root, 'scoped-config.json'), JSON.stringify(config));
  const api = {config, registerTool() {}, on() {}, runtime: {version: '2026.9.2', agent: {runEmbeddedAgent}}};
  const channel = new EventEmitter(); channel.frames = [];
  channel.send = frame => channel.frames.push(frame); channel.finish = () => channel.emit('finished');
  return {root, options, api, channel};
}

test('qualification loads/checks the public capability without invoking it', t => {
  let calls = 0; const f = fakeHarness(t, () => { calls++; });
  const result = qualify(f.api, f.options);
  assert.equal(calls, 0); assert.equal(result.modelLaunches, 0); assert.equal(result.qualified, true);
  assert.ok(!JSON.stringify(result).includes(f.options.authProfileId));
});

test('two tool actions and internal retry telemetry share one outer dispatch, no reservations', async t => {
  let bridge, calls = 0;
  const f = fakeHarness(t, async params => {
    calls++;
    params.onRunProgress({reason: 'notification:retry', backend: 'codex-app-server'});
    await bridge.action('one', {action: 'list'});
    await bridge.action('two', {action: 'final', answer: 'x', files: []});
    return {meta: {agentMeta: {model: 'gpt-5.6-sol', provider: 'openai', agentHarnessId: 'codex', credentialSource: {kind: 'profile'}}}};
  });
  const send = f.channel.send;
  f.channel.send = frame => { send(frame); if (frame.kind === 'action') queueMicrotask(() => f.channel.emit('frame', {kind: 'action_result', id: frame.id, result: {ok: true}})); };
  bridge = createBridge(f.api, f.options, f.channel);
  const finished = new Promise(resolve => f.channel.once('finished', resolve));
  f.channel.emit('frame', start); await finished;
  assert.equal(calls, 1); assert.equal(f.channel.frames.filter(f => f.kind === 'action').length, 2);
  assert.equal(f.channel.frames.at(-1).kind, 'completed');
  await bridge.done;
});

test('public fallback projection alone immediately aborts upstream and rejects further tools', async t => {
  let bridge, signalAborted = false;
  const f = fakeHarness(t, async params => {
    params.onAgentEvent({stream: 'fallback', data: {fromModel: 'gpt-5.6-sol', toModel: 'other', reason: 'capacity'}});
    signalAborted = params.abortSignal.aborted;
    await assert.rejects(bridge.action('forbidden', {action: 'list'}));
    return {meta: {}};
  });
  bridge = createBridge(f.api, f.options, f.channel);
  const finished = new Promise(resolve => f.channel.once('finished', resolve));
  f.channel.emit('frame', start); await finished;
  assert.equal(signalAborted, true); assert.equal(f.channel.frames.at(-1).kind, 'failed');
  assert.equal(f.channel.frames.filter(f => f.kind === 'action').length, 0);
});

test('observable output cap aborts within the callback before another action', async t => {
  let aborted;
  const f = fakeHarness(t, async params => {
    params.onAgentEvent({stream: 'assistant', data: {text: 'abcdef'}});
    aborted = params.abortSignal.aborted; return {meta: {}};
  });
  createBridge(f.api, f.options, f.channel);
  const finished = new Promise(resolve => f.channel.once('finished', resolve));
  f.channel.emit('frame', {...start, profile: {...profile, budget: {...profile.budget, max_runtime_observable_output_bytes: 3}}}); await finished;
  assert.equal(aborted, true); assert.equal(f.channel.frames.at(-1).reason, 'runtime_output_budget_exceeded');
});
