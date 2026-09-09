/** TMF reflex integration for OpenClaw. No gateway configuration is modified here. */
import { spawnSync } from "node:child_process";
import * as path from "node:path";
import * as fs from "node:fs";
import * as crypto from "node:crypto";
import * as os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const integrationRoot = path.resolve(here, "..");
const touchTools = new Set(["read", "edit", "write", "apply_patch"]);
const mutationTools = new Set(["edit", "write", "apply_patch"]);
const DEFAULT_TTL_MS = 30 * 60 * 1000;
const MAX_REASON = 1800;

export interface RepoConfig { repoRoot: string; stateRoot?: string; }
export interface PluginConfig { recoveryObservationRoot?: string; enabled?: boolean; mode?: "block"|"approval"; python?: string; tmfRoot?: string; repos?: RepoConfig[]; pendingTtlMs?: number; }
interface HookContext { sessionKey?: string; sessionId?: string; runId?: string; toolCallId?: string; }
interface StalePath { path: string; qualname?: string; current_source_blob: string|null; anchor?: {line_start?: number|null; line_end?: number|null; reliable?: boolean}; }
interface Collision { schema_version: string; collision_id: string; canonical_repo_root: string; canonical_state_root: string; blocked_action_fingerprint: string; blocked_tool: string; blocked_target_path: string; stale_paths: StalePath[]; recovery_commands?: string[]; reason?: string; session_identity?: string; run_identity?: string|null; }
interface Pending { generation: symbol; ttlMs: number; collision: Collision; session: string; cleanupKey?: string; repoKey: string; createdAt: number; expiresAt: number; notices: number; observed: Set<string>; sourceChanged: boolean; }
interface ReadCandidate { pendingKey: string; generation: symbol; paths: string[]; blobs: Map<string,string>; params: Record<string,unknown>; file: string; }
interface MutationCandidate { pendingKey: string; generation: symbol; fingerprint: string; observationIdentity?: string; }

const pending = new Map<string, Pending>();
const reads = new Map<string, ReadCandidate>();
const mutations = new Map<string, MutationCandidate>();
// No eviction: late public receipts have no invocation-instance token. This
// registry survives cleanup/reset but NOT module/process replacement.
export const RECEIPT_IDENTITY_CAPACITY = 4096;
const MAX_IDENTITY_LENGTH = 256;
const identities = new Map<string, { tool: string; tainted: boolean }>();

function inside(candidate: string, root: string): boolean {
  const c = path.resolve(candidate), r = path.resolve(root);
  return c === r || c.startsWith(r + path.sep);
}
function canonicalPath(value:string):string {
  const expanded=value==="~"?os.homedir():value.startsWith("~/")?path.join(os.homedir(),value.slice(2)):value;
  let parent=path.resolve(expanded); const tail:string[]=[];
  while(!fs.existsSync(parent) && path.dirname(parent)!==parent) { tail.unshift(path.basename(parent)); parent=path.dirname(parent); }
  return path.join(fs.realpathSync(parent),...tail);
}
function canonicalRepo(repo: RepoConfig): RepoConfig {
  const stateRoot=canonicalPath(repo.stateRoot || path.join(repo.repoRoot, ".tmf"));
  if (path.basename(stateRoot)!==".tmf") throw new Error("TMF state_root_error: stateRoot must resolve to a directory named .tmf");
  return {repoRoot: canonicalPath(repo.repoRoot), stateRoot};
}
export function resolveFile(params: Record<string, unknown>, cwd: string): string | undefined {
  const value = params.file_path || params.path || params.file || params.filePath || params.filepath;
  if (typeof value !== "string" || !value) return undefined;
  return path.resolve(cwd, value);
}
export function route(file: string, repos: RepoConfig[]): RepoConfig | undefined {
  const matches = repos.map(canonicalRepo).filter((r) => inside(file, r.repoRoot));
  return matches.length === 1 ? matches[0] : undefined;
}
function sessionIdentity(ctx: HookContext, event?: any): string | undefined {
  const value=ctx.sessionKey || ctx.sessionId || ctx.runId || event?.runId;
  return value ? String(value) : undefined;
}
function repoKey(repo: RepoConfig): string { const r=canonicalRepo(repo); return `${r.repoRoot}\0${r.stateRoot}`; }
function pendingKey(session: string, repo: RepoConfig): string { return `${session}\0${repoKey(repo)}`; }
function callKey(ctx: HookContext, event: any): string | undefined {
  const values: Record<string,string> = {};
  for (const field of ["sessionKey", "sessionId", "runId", "toolCallId"] as const) {
    const a=ctx[field], b=event?.[field];
    for (const v of [a,b]) if (v!==undefined && (typeof v!=="string" || !v.trim() || v.length>MAX_IDENTITY_LENGTH)) return undefined;
    if (a!==undefined && b!==undefined && a!==b) return undefined;
    if (a!==undefined || b!==undefined) values[field]=(a??b)!;
  }
  const session=values.sessionKey || values.sessionId;
  return session && values.runId && values.toolCallId ? JSON.stringify([session,values.runId,values.toolCallId]) : undefined;
}
function reserveIdentity(key:string|undefined, tool:string): string|undefined {
  if (!key) return "identity_missing_or_mismatched";
  const prior=identities.get(key);
  if (prior) {
    prior.tainted=true;
    reads.delete(key); mutations.delete(key);
    return "identity_reused";
  }
  if (identities.size>=RECEIPT_IDENTITY_CAPACITY) return "identity_capacity";
  identities.set(key,{tool,tainted:false});
  return undefined;
}
function identityBlock(code:string):any {
  // Ambiguous identity is not safely overridable with approval.
  return {block:true,blockReason:`TMF dual gate [${code}]: receipt identity unavailable; use unique session/run/tool-call IDs. Registry exhaustion requires a quiescent isolated lifecycle, not TTL retry.`};
}
function expire(now=Date.now()): void {
  for (const [key,value] of pending) if (value.expiresAt <= now) pending.delete(key);
  for (const [key,value] of reads) if (pending.get(value.pendingKey)?.generation!==value.generation) reads.delete(key);
  for (const [key,value] of mutations) if (pending.get(value.pendingKey)?.generation!==value.generation) mutations.delete(key);
}
function blobSha(file: string): string|null {
  try { const data=fs.readFileSync(file); return crypto.createHash("sha1").update(`blob ${data.length}\0`).update(data).digest("hex"); }
  catch { return null; }
}
function parseDecision(proc: ReturnType<typeof spawnSync>): any|undefined {
  const raw = proc.status === 2 ? proc.stderr : proc.stdout;
  if (typeof raw !== "string") return undefined;
  const line=raw.trim().split("\n").at(-1); if (!line) return undefined;
  try { return JSON.parse(line); } catch { return undefined; }
}
function invokePython(event:any,cwd:string,config:PluginConfig,repo:RepoConfig): {status:number|null; decision:any|undefined} {
  const payload=JSON.stringify({tool_name:String(event.toolName||"").toLowerCase(),tool_input:event.params||{},cwd});
  const env:NodeJS.ProcessEnv={...process.env,TMF_WORKTREE:config.tmfRoot||path.resolve(integrationRoot,"../.."),TMF_STATE_ROOT:canonicalRepo(repo).stateRoot};
  const proc=spawnSync(config.python||"python3",[path.join(integrationRoot,"hooks","pre_tool_use.py")],{input:payload,encoding:"utf8",env});
  return {status:proc.status,decision:parseDecision(proc)};
}
function block(config:PluginConfig, code:string, pendingValue?:Pending): any {
  const n=pendingValue ? ++pendingValue.notices : 1;
  const paths=pendingValue?.collision.stale_paths.map(x=>`${x.path}${x.qualname?`::${x.qualname}`:""}`).join(", ")||"current source";
  const command=pendingValue?.collision.recovery_commands?.[0];
  const detail:Record<string,string>={
    need_warm:`TMF dual gate [need_warm]: locally warm the exact stale source (${paths})${command?` with: ${command}`:""}.`,
    need_read:`TMF dual gate [need_read]: warm is current; now successfully Read the exact stale source and cover its anchor (${paths}).`,
    stale_retry:`TMF dual gate [stale_retry]: the retry is identical to the stale blocked action. Read current source and submit a corrected retry.`,
    source_changed:`TMF dual gate [source_changed]: source changed again after the collision/read; re-warm and Read the current exact source.`,
    missing:`TMF dual gate [missing]: a required source is missing or renamed. No rename is guessed; rediscover explicitly and re-establish TMF state.`,
    engine_error:`TMF dual gate [engine_error]: collision state exists but freshness could not be verified; retry later or inspect TMF state.`,
  };
  const reason=`${detail[code]||`TMF dual gate [${code}] blocked.`} (notice ${Math.min(n,3)}/3; repeated detail is bounded)`.slice(0,MAX_REASON);
  return config.mode==="approval"?{requireApproval:{reason}}:{block:true,blockReason:reason};
}
function sameRequiredBlobs(value:Pending): "same"|"changed"|"missing" {
  for (const item of value.collision.stale_paths) {
    const current=blobSha(path.join(value.collision.canonical_repo_root,item.path));
    if (!current) return "missing";
    if (current!==item.current_source_blob) return "changed";
  }
  return "same";
}
function rearmSource(value:Pending): void {
  // A source rearm is a new authority epoch even if target/collision/blob recur.
  value.generation=Symbol("pending-generation");
  for (const item of value.collision.stale_paths) {
    item.current_source_blob=blobSha(path.join(value.collision.canonical_repo_root,item.path));
  }
  value.sourceChanged=true;
  value.observed.clear();
  value.notices=0;
  value.createdAt=Date.now();
  value.expiresAt=value.createdAt+value.ttlMs;
  expire(); // discard both Read and mutation authority from the superseded epoch
}
function paginationInt(value:unknown, fallback:number|null):number|null {
  if (value==null) return fallback;
  if (typeof value==="number" && Number.isSafeInteger(value)) return value;
  if (typeof value==="string" && /^\d+$/.test(value.trim())) return Number(value);
  return null;
}
function coversAnchor(params:Record<string,unknown>, item:StalePath, totalLines?:number):boolean {
  const start=paginationInt(params.offset,1);
  const limit=paginationInt(params.limit,null);
  if (start==null || start<1) return false;
  if (item.anchor?.reliable && (!Number.isSafeInteger(item.anchor.line_start) || !Number.isSafeInteger(item.anchor.line_end) || item.anchor.line_start!<1 || item.anchor.line_end!<item.anchor.line_start!)) return false;
  if (!item.anchor?.reliable || !Number.isInteger(item.anchor.line_start) || !Number.isInteger(item.anchor.line_end)) {
    // Some parser bindings do not carry line anchors. In that case require a
    // demonstrable whole-file Read: start at line 1 and either omit the limit
    // or request at least the current file's complete line count.
    if (start!==1) return false;
    if (params.limit==null) return true;
    return limit!=null && limit>0 && totalLines!=null && limit>=totalLines;
  }
  // OpenClaw may normalize pagination fields to decimal strings between the
  // model tool call and plugin lifecycle event. Treat those exactly like the
  // numeric Read API while rejecting fractions, negatives, and junk.
  if (params.limit==null) return start<=item.anchor.line_start!;
  if (limit==null || limit<=0) return false;
  return start<=item.anchor.line_start! && start+limit-1>=item.anchor.line_end!;
}
/** Supported: OpenClaw single text-block Read, exact offset/limit slice, optionally
 * its user-limit continuation notice. No custom probe metadata is trusted.
 * Truncated/adaptive/sanitized/unknown shapes fail closed; use an explicit narrow
 * offset/limit Read covering the anchor to recover. No substring source search. */
export function actualReadCovers(result:any, params:Record<string,unknown>, item:StalePath, source:string):boolean {
  if (!result || result.isError || result.error || !Array.isArray(result.content) || result.content.length!==1) return false;
  if (result.details != null && (typeof result.details!=="object" || Object.keys(result.details).length>0)) return false;
  const block=result.content[0];
  if(block?.type!=="text" || typeof block.text!=="string") return false;
  const start=paginationInt(params.offset,1), limit=paginationInt(params.limit,null);
  if(start==null || start<1 || (params.limit!=null && (limit==null || limit<1))) return false;
  const lines=source.split("\n");
  if(start>lines.length) return false;
  const end=limit==null?lines.length:Math.min(lines.length,start-1+limit);
  const selected=lines.slice(start-1,end).join("\n");
  // Built-in base Read caps at 2000 lines/51200 bytes. Refuse larger receipts,
  // including adaptive concatenation, even if they resemble complete source.
  if(end-start+1>2000 || Buffer.byteLength(selected,"utf8")>51200) return false;
  const expected=end<lines.length ? `${selected}\n\n[${lines.length-end} more lines in file. Use offset=${end+1} to continue.]` : selected;
  if(block.text!==expected) return false;
  const total=source.length===0?0:lines.length-(source.endsWith("\n")?1:0);
  return coversAnchor({offset:start,limit:end-start+1},item,total);
}
function actionFingerprint(toolName:string,params:Record<string,unknown>,rel:string):string {
  const stable=(v:any):string=>Array.isArray(v)?`[${v.map(stable).join(",")}]`:v&&typeof v==="object"?`{${Object.keys(v).sort().map(k=>`${JSON.stringify(k)}:${stable(v[k])}`).join(",")}}`:JSON.stringify(v);
  return crypto.createHash("sha256").update(stable({tool_name:toolName,path:rel,input:params})).digest("hex");
}
function dependencyMatch(value:Pending,tool:string,file:string|undefined):boolean {
  if (!file || !mutationTools.has(tool)) return false;
  return path.resolve(file)===path.join(value.collision.canonical_repo_root,value.collision.blocked_target_path) && tool===value.collision.blocked_tool;
}

export function runPreToolUse(event:any,cwd:string,config:PluginConfig,ctx:HookContext={}):any {
  expire();
  const toolName=String(event.toolName||"").toLowerCase(), params=event.params||{};
  if (!touchTools.has(toolName)) return undefined; // shell cannot unlock
  const file=resolveFile(params,cwd); if (!file) return undefined; // documented pathless fail-open
  let repo:RepoConfig|undefined;
  try { repo=route(file,config.repos||[]); } catch { return block(config,"state_root_error"); }
  if (!repo) return undefined;
  const identity=callKey(ctx,event), identityError=reserveIdentity(identity,toolName);
  if (identityError) return identityBlock(identityError);
  const session=JSON.parse(identity!)[0] as string;
  const key=session?pendingKey(session,repo):undefined;
  const active=key?pending.get(key):undefined;

  if (active && toolName==="read") {
    const matches=active.collision.stale_paths.filter(item=>path.join(active.collision.canonical_repo_root,item.path)===path.resolve(file));
    if (!matches.length) return undefined;
    const state=sameRequiredBlobs(active); if (state==="missing") return block(config,"missing",active); if(state==="changed") { rearmSource(active); return block(config,"source_changed",active); }
    // Warm must be independently current before a Read can become an observation token.
    const check=invokePython(event,cwd,config,repo);
    if (check.status===2) return block(config,"need_warm",active);
    if (check.status!==0 || check.decision?.decision!=="allow") return block(config,"engine_error",active);
    active.sourceChanged=false;
    if (!matches.every(item=>{
      const source=path.join(active.collision.canonical_repo_root,item.path);
      let totalLines:number|undefined;
      try { const text=fs.readFileSync(source,"utf8"); totalLines=text.length===0?0:text.split(/\r?\n/).length-(text.endsWith("\n")?1:0); }
      catch { return false; }
      return coversAnchor(params,item,totalLines);
    })) return block(config,"need_read",active);
    const ck=callKey(ctx,event); if (ck) reads.set(ck,{pendingKey:key!,generation:active.generation,paths:matches.map(x=>x.path),blobs:new Map(matches.map(x=>[x.path,x.current_source_blob!])),params:{...params},file:path.resolve(file)});
    return undefined;
  }

  if (active && dependencyMatch(active,toolName,file)) {
    const state=sameRequiredBlobs(active); if(state==="missing") return block(config,"missing",active); if(state==="changed") { rearmSource(active); return block(config,"source_changed",active); }
    if (active.sourceChanged) return block(config,"need_warm",active);
    const check=invokePython(event,cwd,config,repo);
    if (check.status===2) return block(config,"need_warm",active);
    if (check.status!==0 || check.decision?.decision!=="allow") return block(config,"engine_error",active);
    const required=new Set(active.collision.stale_paths.map(x=>x.path));
    if ([...required].some(p=>!active.observed.has(p))) return block(config,"need_read",active);
    const rel=path.relative(canonicalRepo(repo).repoRoot,file).split(path.sep).join("/");
    if (actionFingerprint(toolName,params,rel)===active.collision.blocked_action_fingerprint) return block(config,"stale_retry",active);
    const ck=callKey(ctx,event);
    if (!ck) return block(config,"engine_error",active);
    mutations.set(ck,{pendingKey:key!,generation:active.generation,fingerprint:actionFingerprint(toolName,params,rel),
      observationIdentity:config.recoveryObservationRoot ? recoveryIdentity(ctx,event) : undefined});
    return undefined;
  }

  const check=invokePython(event,cwd,config,repo);
  if (check.status!==2 || check.decision?.schema_version!=="tmf.reflex.collision.v1") return undefined;
  const collision=check.decision as Collision;
  if (session) {
    collision.session_identity=session; collision.run_identity=event.runId||ctx.runId||null;
    const now=Date.now(), value:Pending={generation:Symbol("pending-generation"),ttlMs:config.pendingTtlMs||DEFAULT_TTL_MS,collision,session,cleanupKey:ctx.sessionKey ?? event.sessionKey,repoKey:repoKey(repo),createdAt:now,expiresAt:now+(config.pendingTtlMs||DEFAULT_TTL_MS),notices:0,observed:new Set(),sourceChanged:false};
    pending.set(pendingKey(session,repo),value);
    expire(); // a reused map slot must not retain the previous generation

    return block(config,"need_warm",value);
  }
  return block(config,"need_warm");
}

/** Positive receipts for the installed built-in Edit/Write contract only.
 * Unknown/custom/apply_patch shapes retain pending (pathless patch is outside
 * this gate). This is receipt evidence, not an independent filesystem oracle. */
function successfulMutation(tool:string, event:any):boolean {
  const result=event.result;
  if (event.error!==undefined && event.error!==null) return false;
  if (!result || typeof result!=="object" || Array.isArray(result)) return false;
  if ((result.error!==undefined && result.error!==null) ||
      (result.isError!==undefined && result.isError!==false) ||
      result.status!==undefined || (result.ok!==undefined && result.ok!==true)) return false;
  if (!Array.isArray(result.content) || result.content.length!==1) return false;
  const text=result.content[0];
  if (text?.type!=="text" || typeof text.text!=="string") return false;
  const params=event.params||{};
  const file=params.path ?? params.file_path;
  if (typeof file!=="string" || !file) return false;
  if (tool==="edit" && Array.isArray(params.edits) && params.edits.length>0 &&
      params.edits.every((e:any)=>e && typeof e.oldText==="string" && typeof e.newText==="string"))
    return text.text===`Successfully replaced ${params.edits.length} block(s) in ${file}.`;
  // Installed Write says "bytes" but uses JS string.length (UTF-16 units).
  if (tool==="write" && typeof params.content==="string")
    return text.text===`Successfully wrote ${params.content.length} bytes to ${file}`;
  return false;
}

export function runAfterToolCall(event:any,cwd:string,config:PluginConfig,ctx:HookContext={}):void {
  expire();
  const ck=callKey(ctx,event); if(!ck) return;
  const tool=String(event.toolName||"").toLowerCase();
  const ownership=identities.get(ck);
  if (!ownership || ownership.tainted || ownership.tool!==tool) return;
  if(tool==="read") {
    const candidate=reads.get(ck); reads.delete(ck); if(!candidate || event.error) return;
    const active=pending.get(candidate.pendingKey); if(!active || active.generation!==candidate.generation) return;
    if (resolveFile(event.params||{},cwd)!==candidate.file ||
        paginationInt(event.params?.offset,1)!==paginationInt(candidate.params.offset,1) ||
        paginationInt(event.params?.limit,null)!==paginationInt(candidate.params.limit,null)) return;
    for(const rel of candidate.paths) {
      const file=path.join(active.collision.canonical_repo_root,rel);
      const items=active.collision.stale_paths.filter(x=>x.path===rel);
      try {
        const bytes=fs.readFileSync(file), text=bytes.toString("utf8");
        const digest=crypto.createHash("sha1").update(`blob ${bytes.length}\0`).update(bytes).digest("hex");
        if(digest!==candidate.blobs.get(rel) || !Buffer.from(text,"utf8").equals(bytes)) continue;
        if(items.every(item=>actualReadCovers(event.result,candidate.params,item,text)) && blobSha(file)===digest) active.observed.add(rel);
      } catch { /* missing/unreadable is not an observation */ }
    }
    return;
  }
  const candidate=mutations.get(ck); mutations.delete(ck); if(!candidate || !successfulMutation(tool,event)) return;
  const active=pending.get(candidate.pendingKey); if(!active || active.generation!==candidate.generation) return;
  const file=resolveFile(event.params||{},cwd);
  if(!file) return;
  const rel=path.relative(active.collision.canonical_repo_root,file).split(path.sep).join("/");
  if(actionFingerprint(tool,event.params||{},rel)===candidate.fingerprint) {
    pending.delete(candidate.pendingKey); // release authority unchanged; recording is downstream
    observeRecovery(active,ck,tool,rel,candidate.fingerprint,config,ctx,event,candidate.observationIdentity);
  }
}
export function cleanupSession(event:any,ctx:HookContext={}):void {
  // session_end supplies a key and a UUID, not interchangeable aliases.
  // Without an authoritative key (including legacy sessionId-only calls),
  // leave transients alone; no guessed UUID -> key mapping or run alias.
  for (const field of ["sessionKey", "sessionId"] as const) {
    const a=ctx[field], b=event?.[field];
    for (const v of [a,b]) if (v!==undefined && (typeof v!=="string" || !v.trim() || v.length>MAX_IDENTITY_LENGTH)) return;
    if (a!==undefined && b!==undefined && a!==b) return;
  }
  const session=ctx.sessionKey ?? event?.sessionKey;
  if (!session) return;
  const removed=new Set<string>();
  for(const [key,value] of pending) if(value.cleanupKey===session) { pending.delete(key); removed.add(key); }
  for(const [key,value] of reads) if(removed.has(value.pendingKey)) reads.delete(key);
  for(const [key,value] of mutations) if(removed.has(value.pendingKey)) mutations.delete(key);
}
export function debugState():any { expire(); return {pending:pending.size,reads:reads.size,mutations:mutations.size}; }
/** Clear transient state only. Never reopen a previously seen receipt tuple. */
export function resetState():void { pending.clear(); reads.clear(); mutations.clear(); }
export function debugReceiptIdentityState():any { return {size:identities.size,capacity:RECEIPT_IDENTITY_CAPACITY}; }

export function runSessionStart(repo:RepoConfig,config:PluginConfig):string|undefined {
  const stateRoot=canonicalRepo(repo).stateRoot!; if(!fs.existsSync(stateRoot)) return undefined;
  const proc=spawnSync(config.python||"python3",[path.join(integrationRoot,"hooks","session_start.py"),"--repo",path.resolve(repo.repoRoot),"--state-root",stateRoot,"--json"],{encoding:"utf8"});
  if(proc.status!==0)return undefined; try{return JSON.parse(proc.stdout).injection||undefined}catch{return undefined}
}
const plugin={id:"tmf-reflex",register(api:any){
  const config:PluginConfig=api.pluginConfig||{}; if(config.enabled===false)return;
  for(const repo of config.repos||[]) canonicalRepo(repo); // reject invalid configuration at registration
  const cwd=(()=>{try{return api.runtime.agent.resolveAgentWorkspaceDir(api.config)||process.cwd()}catch{return process.cwd()}})();
  api.on("before_tool_call",async(event:any,ctx:any)=>runPreToolUse(event,cwd,config,ctx));
  api.on("after_tool_call",async(event:any,ctx:any)=>runAfterToolCall(event,cwd,config,ctx));
  api.on("session_start",async(event:any)=>{for(const repo of config.repos||[]){const injection=runSessionStart(repo,config);if(injection)await api.session.workflow.enqueueNextTurnInjection({text:injection,placement:"prepend_context",metadata:{kind:"tmf_session_start_calibration"}})}});
  api.on("session_end",async(event:any,ctx:any)=>cleanupSession(event,ctx));
}};
export default plugin;

// Isolated trusted-local experiment. Disabled without explicit observation root.
// No automatic cognition submit/validate/adopt or agent mental-state claims.
const recoveryGaps:any[]=[];
export function debugRecoveryGaps():any[] { return recoveryGaps.slice(); }
function recoveryIdentity(ctx:HookContext,event:any):string {
 return JSON.stringify(['sessionKey','sessionId','runId','toolCallId'].map(k=>(ctx as any)[k]??event[k]??null));
}
function observeRecovery(active:Pending, receiptKey:string, tool:string, target:string,
 fingerprint:string, config:PluginConfig, ctx:HookContext, event:any, expectedIdentity?:string):void {
 if(!config.recoveryObservationRoot) return;
 let id:string|null=null;
 try {
  id=crypto.randomUUID();
  if(!expectedIdentity || expectedIdentity!==recoveryIdentity(ctx,event)) throw new Error('observation_identity_drift');
  const repo=active.collision.canonical_repo_root;
  const paths=[...new Set([...active.collision.stale_paths.map(x=>x.path),target])].sort();
  if(paths.length>16) throw new Error("binding_budget");
  const vector=paths.map(rel=>{
   const file=fs.realpathSync(path.join(repo,rel));
   if(path.isAbsolute(rel) || rel.split('/').includes('..') || !inside(file,repo)) throw new Error("source_escape");
   const fd=fs.openSync(file,'r'); let bytes:Buffer;
   try { if(!fs.fstatSync(fd).isFile() || fs.fstatSync(fd).size>8192) throw new Error("snapshot_budget");
    const buffer=Buffer.alloc(8193);const n=fs.readSync(fd,buffer,0,8193,0);if(n>8192)throw new Error("snapshot_budget");bytes=buffer.subarray(0,n);
   } finally {fs.closeSync(fd);}
   const snippet=bytes.toString('utf8');if(!Buffer.from(snippet).equals(bytes))throw new Error("non_utf8");
   return {path:rel,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
    git_blob:crypto.createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex'),snippet};
  });
  for(const b of vector)if(blobSha(path.join(repo,b.path))!==b.git_blob)throw new Error("capture_drift");
  const identity:any={};const identityGaps:string[]=[];
  for(const k of ['sessionKey','sessionId','runId','toolCallId'] as const){
    identity[k]=ctx[k]??event[k]??null;if(identity[k]===null)identityGaps.push(k+':not_provided_by_host');
  }
  const observation={schema:'tmf.recovery-observation.v1',id,status:'recovery_released_without_consolidation',
   canonical_repo_root:repo,canonical_state_root:active.collision.canonical_state_root,
   collision_id:active.collision.collision_id,identity,identity_gaps:identityGaps,receipt_key:receiptKey,
   mutation:{tool,target,fingerprint,assurance:'matched built-in-shaped host receipt; not semantic correctness'},
   observed_dependencies:active.collision.stale_paths.map(x=>({path:x.path,qualname:x.qualname??null,
    observed_git_blob:x.current_source_blob,read_observed:active.observed.has(x.path)})),
   postmutation_vector:vector,limitations:['No candidate submitted','No semantic correctness or adoption inferred']};
  const payload=JSON.stringify(observation);if(Buffer.byteLength(payload)>160*1024)throw new Error('observation_budget');
  fs.mkdirSync(config.recoveryObservationRoot,{recursive:true});
  // Fixed-size journal: retain observations, do not silently evict provenance.
  if(fs.readdirSync(config.recoveryObservationRoot).length>=64)throw new Error('journal_capacity');
  fs.writeFileSync(path.join(config.recoveryObservationRoot,id+'.json'),payload,{flag:'wx',mode:0o600});
 } catch(e) {
  const gap={id,status:'recovery_released_observation_gap',reason:String(e).slice(0,300)};
  if(recoveryGaps.length<64)recoveryGaps.push(gap);
  // Gap channel is bounded in-memory debug output, not a durable host notification contract.
 }
}
