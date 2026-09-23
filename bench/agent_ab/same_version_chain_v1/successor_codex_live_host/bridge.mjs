/** Public-plugin bridge only: no private host imports, provider client or auth read. */
import { createHash, randomUUID } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { readFileSync, readdirSync, lstatSync } from 'node:fs';
import { Socket } from 'node:net';
import path from 'node:path';

export const MAX_FRAME = 256000;
export const TOOL_NAME = 'successor_action';
export const MODEL = 'gpt-5.6-sol';
export const EFFORT = 'medium';
export const VERSION = '2026.9.2';
export const PLUGIN_ID = 'tmf-successor-host';
const clone = (v) => JSON.parse(JSON.stringify(v));
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
export const digest = (value) => createHash('sha256').update(canonical(value)).digest('hex');
const fail = (code) => { throw new Error(code); };

/** A dedicated inherited Unix socket, never stdout/stderr, owns all control traffic. */
export class ControlChannel extends EventEmitter {
  constructor(socket) {
    super();
    this.socket = socket;
    this.buffer = Buffer.alloc(0);
    this.closed = false;
    socket.on('data', data => {
      try {
        this.buffer = Buffer.concat([this.buffer, data]);
        while (this.buffer.includes(10)) {
          const i = this.buffer.indexOf(10);
          if (i + 1 > MAX_FRAME) fail('host_frame_budget_exceeded');
          const raw = this.buffer.subarray(0, i);
          this.buffer = this.buffer.subarray(i + 1);
          const value = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw));
          if (!value || Array.isArray(value) || typeof value.kind !== 'string') fail('invalid_host_frame');
          this.emit('frame', value);
        }
        if (this.buffer.length >= MAX_FRAME) fail('host_frame_budget_exceeded');
      } catch (error) { this.emit('failure', error.message); }
    });
    socket.on('error', () => this.emit('failure', 'host_channel_error'));
    socket.on('close', () => { this.closed = true; this.emit('failure', 'host_channel_closed'); });
  }
  send(frame) {
    const bytes = Buffer.from(JSON.stringify(frame) + '\n');
    if (bytes.length > MAX_FRAME) fail('host_frame_budget_exceeded');
    if (this.closed) fail('host_channel_closed');
    this.socket.write(bytes);
  }
  finish() {
    return new Promise(resolve => this.socket.end(() => { this.socket.destroy(); resolve(); }));
  }
}

export function openControlChannel(env = process.env) {
  const raw = env.SUCCESSOR_CONTROL_FD;
  if (!/^[0-9]+$/.test(raw ?? '') || Number(raw) < 3) fail('missing_control_fd');
  return new ControlChannel(new Socket({fd: Number(raw), readable: true, writable: true}));
}

/** Select only request/configuration fields; these never attest provider identity. */
export function validateProfile(frame) {
  const p = frame.profile;
  if (!p || p.request_model !== 'openai/' + MODEL || p.native_model !== MODEL ||
      p.provider !== 'openai' || p.reasoning_effort !== EFFORT || p.openclaw_version !== VERSION ||
      p.runtime !== 'openclaw-codex-app-server' || p.model_fallback_allowed !== false ||
      p.platform_api_allowed !== false || p.budget?.native_inference_pre_reservation_required !== false ||
      p.permissions?.project_docs !== false || p.permissions?.native_shell !== false ||
      p.permissions?.delegation !== false || typeof p.common_protocol_carrier !== 'string') fail('requested_configuration_mismatch');
  if (!Number.isInteger(frame.timeout_ms) || frame.timeout_ms < 1 || frame.timeout_ms > 300000) fail('invalid_run_timeout');
  if (canonical(frame.tool) !== canonical(p.native_tool) || frame.tool?.name !== TOOL_NAME) fail('scientific_tools_drift');
  if (!Array.isArray(frame.scientific_messages) || frame.scientific_messages.length !== 2 ||
      frame.scientific_messages[0]?.role !== 'system' || frame.scientific_messages[1]?.role !== 'user' ||
      frame.scientific_messages.some(m => typeof m.content !== 'string' || Object.keys(m).sort().join(',') !== 'content,role')) fail('invalid_scientific_messages');
  return p;
}

/** Only this plugin's authored nonsecret config is read. Never read host auth/config. */
export function scopedConfiguration(api, options) {
  const runtimeDirectory = options.runtimeDirectory;
  if (!path.isAbsolute(runtimeDirectory) || path.resolve(runtimeDirectory) !== runtimeDirectory ||
      !/^[a-zA-Z0-9_:./@-]+$/.test(options.authProfileId ?? '')) fail('invalid_host_options');
  const configFile = path.join(runtimeDirectory, 'scoped-config.json');
  const raw = readFileSync(configFile);
  const authored = JSON.parse(raw.toString('utf8'));
  if (authored.plugins?.entries?.[PLUGIN_ID]?.config?.runtimeDirectory !== runtimeDirectory ||
      authored.plugins?.entries?.[PLUGIN_ID]?.config?.authProfileId !== options.authProfileId ||
      authored.agents?.defaults?.model?.primary !== 'openai/' + MODEL ||
      canonical(authored.agents?.defaults?.model?.fallbacks) !== '[]' ||
      authored.auth?.profiles?.[options.authProfileId]?.mode !== 'oauth' ||
      authored.plugins?.entries?.codex?.config?.appServer?.transport !== 'stdio') fail('configuration_drift');
  const assertAuthored = (expected, observed) => {
    if (Array.isArray(expected) || !expected || typeof expected !== 'object') {
      if (canonical(expected) !== canonical(observed)) fail('configuration_drift');
    } else for (const [key, value] of Object.entries(expected)) assertAuthored(value, observed?.[key]);
  };
  assertAuthored(authored, api.config);
  const normalize = (value) => {
    if (Array.isArray(value)) return value.map(normalize);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, normalize(child)]));
    return typeof value === 'string' && value.startsWith(runtimeDirectory) ? '<private-run-directory>' + value.slice(runtimeDirectory.length) : value;
  };
  return {authored, rawHash: createHash('sha256').update(raw).digest('hex'), configFile,
    commonConfigHash: digest(normalize(authored))};
}

/** Preserve scientific characters and role intent through the public runtime fields. */
export function buildRunParams(frame, context, callbacks) {
  const profile = validateProfile(frame);
  const sessionId = context.sessionId;
  const sessionKey = 'agent:successor-pilot:' + sessionId;
  return {
    sessionId, sessionKey, runId: context.runId,
    agentId: 'successor-pilot', agentDir: path.join(context.runtimeDirectory, 'agent'),
    workspaceDir: path.join(context.runtimeDirectory, 'carrier'),
    bootstrapWorkspaceDir: path.join(context.runtimeDirectory, 'carrier'),
    cwd: path.join(context.runtimeDirectory, 'carrier'),
    sessionRoot: path.join(context.runtimeDirectory, 'sessions'),
    sessionTarget: {agentId: 'successor-pilot', sessionId, sessionKey,
      storePath: path.join(context.runtimeDirectory, 'sessions', 'sessions.json')},
    config: context.config,
    prompt: frame.scientific_messages[1].content,
    transcriptPrompt: frame.scientific_messages[1].content,
    extraSystemPrompt: frame.scientific_messages[0].content + '\n\n' + profile.common_protocol_carrier,
    provider: 'openai', model: MODEL, thinkLevel: EFFORT,
    agentHarnessId: 'codex', modelSelectionLocked: true, modelFallbacksOverride: [],
    authProfileId: context.authProfileId, authProfileIdSource: 'user', authProfileFailurePolicy: 'local',
    toolsAllow: [TOOL_NAME], toolExecutionAllow: [TOOL_NAME],
    bootstrapContextMode: 'lightweight', promptMode: 'minimal', isCanonicalWorkspace: false,
    skillsSnapshot: {prompt: '', skills: []},
    disableMessageTool: true, codeModeOverride: false,
    timeoutMs: frame.timeout_ms, runTimeoutOverrideMs: frame.timeout_ms,
    fastMode: false, terminalReplyExpectation: 'optional',
    cleanupBundleMcpOnRunEnd: true, oneShotCliRun: true,
    suppressLiveStreamOutput: false,
    ...callbacks,
  };
}

/** Observe only public per-run callback facts, never infer hidden inference counts. */
export function anomalyIn(source, raw) {
  // User/source/assistant/tool text is never an event name. Do not scan it.
  if (source === 'onAgentEvent' && raw?.stream === 'fallback') return 'model_rerouted';
  const rows = [raw, raw?.data, raw?.meta?.agentMeta,
    raw?.runtimeModelSelection, raw?.data?.runtimeModelSelection,
    raw?.meta?.agentMeta?.runtimeModelSelection].filter(v => v && typeof v === 'object');
  const text = rows.flatMap(row => ['event', 'method', 'reason', 'type', 'phase'].map(k =>
    typeof row[k] === 'string' ? row[k] : '')).join('\n');
  if (/model[\/_]rerouted|model_rerouted|modelRerouted|model_reroute/.test(text)) return 'model_rerouted';
  if (/configuration_drift|config_drift/.test(text)) return 'configuration_drift';
  if (/effort_drift/.test(text)) return 'effort_drift';
  if (/workspace_escape/.test(text)) return 'workspace_escape';
  if (/tool_bypass/.test(text)) return 'tool_bypass';
  for (const row of rows) {
    for (const name of ['model', 'modelId']) {
      const value = row[name];
      if (typeof value === 'string' && ![MODEL, 'openai/' + MODEL].includes(value)) return 'model_mismatch';
    }
    for (const name of ['thinkLevel', 'effort', 'reasoningEffort', 'reasoning_effort']) {
      const value = row[name];
      if (typeof value === 'string' && value !== EFFORT) return 'effort_drift';
    }
    if (typeof row.provider === 'string' && row.provider !== 'openai') return 'model_mismatch';
    if (typeof row.modelProvider === 'string' && row.modelProvider !== 'openai') return 'model_mismatch';
    if (typeof row.agentHarnessId === 'string' && row.agentHarnessId !== 'codex') return 'configuration_drift';
    if (typeof row.backend === 'string' && !['codex', 'codex-app-server'].includes(row.backend)) return 'configuration_drift';
    for (const key of ['runtime', 'harnessRuntime', 'agentHarnessRuntime']) {
      if (typeof row[key] === 'string' && !['codex', 'codex-app-server', 'openclaw-codex-app-server'].includes(row[key])) return 'configuration_drift';
    }
    for (const key of ['openclawVersion', 'openclaw_version']) {
      if (typeof row[key] === 'string' && row[key] !== VERSION) return 'configuration_drift';
    }
    if (row.credentialSource && row.credentialSource.kind !== 'profile') return 'configuration_drift';
    if (Array.isArray(row.fallbackAttempts) && row.fallbackAttempts.length) return 'model_rerouted';
    if (source === 'onAgentEvent' && raw.stream === 'tool') {
      const name = row.name ?? row.toolName;
      if (typeof name === 'string' && ![TOOL_NAME, 'openclaw_direct.' + TOOL_NAME].includes(name)) return 'tool_bypass';
    }
  }
  return null;
}

/** Incremental public text only. This does not count hidden reasoning tokens. */
export class ObservableOutputTracker {
  constructor() { this.snapshots = new Map(); }
  observe(source, raw) {
    let key, text;
    if (source === 'onReasoningStream' && typeof raw.text === 'string') {
      key = 'reasoning'; text = raw.text;
    } else if (source === 'onAgentEvent' && raw.stream === 'assistant' && typeof raw.data?.text === 'string') {
      key = 'assistant:' + (raw.data.itemId ?? 'terminal'); text = raw.data.text;
      if (raw.data.itemId === undefined && [...this.snapshots.values()].includes(text)) return '';
    } else if (source === 'onAgentEvent' && raw.stream === 'item' && raw.data?.kind === 'preamble' && typeof raw.data.progressText === 'string') {
      key = 'preamble:' + raw.data.itemId; text = raw.data.progressText;
    } else return '';
    const previous = this.snapshots.get(key) ?? '';
    this.snapshots.set(key, text);
    return text.startsWith(previous) ? text.slice(previous.length) : text;
  }
}

export function completionProjection(result) {
  const m = result?.meta?.agentMeta ?? {};
  return {
    payloads: result?.payloads ?? null,
    usage: m.usage ?? result?.usage ?? null,
    modelIterations: m.modelIterations ?? null,
    assistantTurns: m.assistantTurns ?? null,
    model: m.model ?? null, provider: m.provider ?? null,
    agentHarnessId: m.agentHarnessId ?? null, credentialSource: m.credentialSource ?? null,
    runtimeModelSelection: m.runtimeModelSelection ?? null,
    fallbackAttempts: m.fallbackAttempts ?? null,
    diagnosticUsage: m.diagnosticUsage ?? null, lastCallUsage: m.lastCallUsage ?? null,
    executionTrace: result?.meta?.executionTrace ?? null,
    toolSummary: result?.meta?.toolSummary ?? null,
    terminationReason: result?.meta?.stopReason ?? result?.meta?.error?.kind ?? null,
    aborted: result?.meta?.aborted ?? null,
    error: result?.meta?.error ?? null,
    elapsedMs: result?.meta?.durationMs ?? null,
    retryCount: null, costUsd: null,
    usageProvenance: 'public_runtime_projection_not_raw_platform_usage',
    modelProvenance: 'public_runtime_metadata_not_provider_attestation',
    internalInferenceRetryCount: 'unknown_unless_reported',
  };
}

export function createBridge(api, options, channel) {
  const controller = new AbortController();
  const context = {runtimeDirectory: options.runtimeDirectory, authProfileId: options.authProfileId,
    sessionId: randomUUID(), runId: randomUUID(), config: api.config};
  let start = null, terminal = false, anomaly = null, actionSequence = 0;
  let resolveDone;
  const done = new Promise(resolve => { resolveDone = resolve; });
  const pending = new Map();
  const output = new ObservableOutputTracker();
  let outputBytes = 0;
  const config = scopedConfiguration(api, options);
  const emit = (event) => channel.send({kind: 'event', event});
  const stop = (reason, raw = null) => {
    if (!anomaly) {
      anomaly = reason;
      controller.abort(reason);
      for (const {reject} of pending.values()) reject(new Error(reason));
      pending.clear();
      try { emit({event: reason, source: 'successor_host', data: raw}); } catch { /* Parent channel owns failed evidence. */ }
    }
  };
  const observe = (source, data) => {
    if (terminal) return;
    try {
      const found = anomalyIn(source, data);
      emit({event: 'runtime_event', source, data: clone(data)});
      if (found) stop(found, data);
      const text = output.observe(source, data);
      if (text) {
        outputBytes += Buffer.byteLength(text);
        emit({event: 'assistant_output', source, text});
        if (outputBytes > start.profile.budget.max_runtime_observable_output_bytes) stop('runtime_output_budget_exceeded');
      }
      const now = createHash('sha256').update(readFileSync(config.configFile)).digest('hex');
      if (now !== config.rawHash) stop('configuration_drift');
    } catch { stop('runtime_failure'); }
  };
  const callbacks = {
    abortSignal: controller.signal,
    onAgentEvent: event => observe('onAgentEvent', event),
    onRunProgress: event => observe('onRunProgress', event),
    onExecutionPhase: event => observe('onExecutionPhase', event),
    onExecutionStarted: event => observe('onExecutionStarted', event ?? {}),
    onAgentToolResult: event => observe('onAgentToolResult', event),
    onAutoCompactionSucceeded: count => observe('onAutoCompactionSucceeded', {count}),
    onReasoningStream: event => observe('onReasoningStream', event),
  };
  const action = async (id, args) => {
    if (!start || terminal || anomaly || controller.signal.aborted) fail('host_action_outside_active_run');
    const key = String(id || 'successor-' + ++actionSequence);
    if (pending.has(key)) fail('duplicate_tool_call');
    observe('successor_action_dispatch', {tool: TOOL_NAME, toolCallId: key});
    if (anomaly) fail(anomaly);
    return await new Promise((resolve, reject) => {
      pending.set(key, {resolve, reject});
      channel.send({kind: 'action', id: key, args});
    });
  };
  const run = async (frame) => {
    if (start) fail('duplicate_start');
    validateProfile(frame);
    if (readdirSync(path.join(options.runtimeDirectory, 'carrier')).length !== 0) fail('carrier_not_empty');
    start = frame;
    const timer = setTimeout(() => stop('run_timeout'), frame.timeout_ms);
    try {
      observe('requested_controls', {provider: 'openai', request_model: 'openai/' + MODEL,
        request_effort: EFFORT, runtime: 'codex', openclaw_version: api.runtime.version,
        fallback: [], profile_sha256: digest(frame.profile), config_sha256: config.rawHash,
        common_configuration_sha256: config.commonConfigHash,
        scientific_messages_sha256: digest(frame.scientific_messages), auth_profile_ref: digest(options.authProfileId),
        auth_mode_request: 'existing_stored_oauth', provider_attestation: false});
      const result = await api.runtime.agent.runEmbeddedAgent(buildRunParams(frame, context, callbacks));
      observe('runEmbeddedAgent_result', result);
      terminal = true;
      if (anomaly) channel.send({kind: 'failed', reason: anomaly});
      else if (result?.meta?.aborted || result?.meta?.error) channel.send({kind: 'failed', reason: 'blocking_runtime_anomaly', result: completionProjection(result)});
      else channel.send({kind: 'completed', result: completionProjection(result)});
    } catch (error) {
      terminal = true;
      channel.send({kind: 'failed', reason: anomaly ?? 'runtime_exception', errorName: error?.name ?? 'Error'});
    } finally { clearTimeout(timer); await channel.finish(); resolveDone(); }
  };
  channel.on('failure', reason => { if (!terminal) stop(reason); });
  channel.on('frame', frame => {
    if (frame.kind === 'halt') { controller.abort(String(frame.reason ?? 'parent_halt')); stop('parent_halt'); return; }
    if (frame.kind === 'action_result') {
      const waiter = pending.get(frame.id);
      if (!waiter) { stop('unexpected_action_result'); return; }
      pending.delete(frame.id);
      waiter.resolve({content: [{type: 'text', text: JSON.stringify(frame.result)}], details: {successor: true}});
      return;
    }
    if (frame.kind === 'start') { void run(frame).catch(async () => { stop('invalid_host_start'); await channel.finish(); resolveDone(); }); return; }
    stop('invalid_host_frame');
  });
  return {action, observe, stop, getFrame: () => start, signal: controller.signal, done};
}

export function qualify(api, options) {
  if (api.runtime.version !== VERSION || typeof api.runtime.agent.runEmbeddedAgent !== 'function' ||
      typeof api.registerTool !== 'function' || typeof api.on !== 'function') fail('public_runtime_capability_missing');
  const config = scopedConfiguration(api, options);
  if (lstatSync(path.join(options.runtimeDirectory, 'carrier')).isSymbolicLink() ||
      readdirSync(path.join(options.runtimeDirectory, 'carrier')).length) fail('carrier_not_empty');
  return {schema: 'tmf.successor.public-host-qualification.v1', qualified: true,
    openclawVersion: api.runtime.version, configSha256: config.rawHash,
    commonConfigurationSha256: config.commonConfigHash,
    publicApi: 'api.runtime.agent.runEmbeddedAgent', cli: 'public_plugin_registerCli',
    registeredTool: TOOL_NAME, requestedModel: 'openai/' + MODEL, requestedEffort: EFFORT,
    authProfileRef: digest(options.authProfileId), authModeRequested: 'existing_stored_oauth',
    authValuesRead: false, providerAttestation: false, modelLaunches: 0};
}
