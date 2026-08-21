/** TMF reflex integration for OpenClaw. No gateway configuration is modified here. */
import { spawnSync } from "node:child_process";
import * as path from "node:path";
import * as fs from "node:fs";
import * as crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const integrationRoot = path.resolve(here, "..");
const touchTools = new Set(["read", "edit", "write", "apply_patch"]);
const mutationTools = new Set(["edit", "write", "apply_patch"]);
const DEFAULT_TTL_MS = 30 * 60 * 1000;
const MAX_REASON = 1800;

export interface RepoConfig { repoRoot: string; stateRoot?: string; }
export interface PluginConfig { enabled?: boolean; mode?: "block"|"approval"; python?: string; tmfRoot?: string; repos?: RepoConfig[]; pendingTtlMs?: number; autoWarm?: boolean; }
interface HookContext { sessionKey?: string; sessionId?: string; runId?: string; toolCallId?: string; }
interface StalePath { path: string; qualname?: string; current_source_blob: string|null; anchor?: {line_start?: number|null; line_end?: number|null; reliable?: boolean}; }
interface Collision { schema_version: string; collision_id: string; canonical_repo_root: string; canonical_state_root: string; blocked_action_fingerprint: string; blocked_tool: string; blocked_target_path: string; stale_paths: StalePath[]; recovery_commands?: string[]; reason?: string; session_identity?: string; run_identity?: string|null; }
interface Pending { collision: Collision; session: string; repoKey: string; createdAt: number; expiresAt: number; notices: number; observed: Set<string>; sourceChanged: boolean; autoWarmAttempts: number; autoWarmSucceeded: boolean; }
interface ReadCandidate { pendingKey: string; paths: string[]; blobs: Map<string,string>; }
interface MutationCandidate { pendingKey: string; fingerprint: string; }

const pending = new Map<string, Pending>();
const reads = new Map<string, ReadCandidate>();
const mutations = new Map<string, MutationCandidate>();

function inside(candidate: string, root: string): boolean {
  const c = path.resolve(candidate), r = path.resolve(root);
  return c === r || c.startsWith(r + path.sep);
}
function canonicalRepo(repo: RepoConfig): RepoConfig {
  return {repoRoot: path.resolve(repo.repoRoot), stateRoot: path.resolve(repo.stateRoot || path.join(repo.repoRoot, ".tmf"))};
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
  const session=sessionIdentity(ctx,event), id=event.toolCallId || ctx.toolCallId;
  return session && id ? `${session}\0${id}` : undefined;
}
function expire(now=Date.now()): void {
  for (const [key,value] of pending) if (value.expiresAt <= now) pending.delete(key);
  for (const [key,value] of reads) if (!pending.has(value.pendingKey)) reads.delete(key);
  for (const [key,value] of mutations) if (!pending.has(value.pendingKey)) mutations.delete(key);
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
function tmfEnv(config:PluginConfig,repo:RepoConfig): NodeJS.ProcessEnv {
  return {...process.env,TMF_WORKTREE:config.tmfRoot||path.resolve(integrationRoot,"../.."),TMF_STATE_ROOT:canonicalRepo(repo).stateRoot};
}
function invokePython(event:any,cwd:string,config:PluginConfig,repo:RepoConfig): {status:number|null; decision:any|undefined} {
  const payload=JSON.stringify({tool_name:String(event.toolName||"").toLowerCase(),tool_input:event.params||{},cwd});
  const proc=spawnSync(config.python||"python3",[path.join(integrationRoot,"hooks","pre_tool_use.py")],{input:payload,encoding:"utf8",env:tmfEnv(config,repo)});
  return {status:proc.status,decision:parseDecision(proc)};
}
function splitCommand(command:string): string[]|undefined {
  const out:string[]=[], re=/(?:[^\s"']+|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')+/g;
  for (const match of command.matchAll(re)) {
    const token=match[0];
    out.push((token.startsWith('"')&&token.endsWith('"'))||(token.startsWith("'")&&token.endsWith("'")) ? token.slice(1,-1) : token);
  }
  return out.length ? out : undefined;
}
function safeWarmArgs(command:string|undefined,config:PluginConfig,value:Pending): string[]|undefined {
  if (!command) return undefined;
  const args=splitCommand(command); if (!args || args.length!==6) return undefined;
  const py=config.python||"python3", warmScript=path.join(integrationRoot,"scripts","local_warm.py");
  if (args[0]!==py && args[0]!=="python3") return undefined;
  if (path.resolve(args[1])!==warmScript) return undefined;
  if (path.resolve(args[2])!==path.resolve(value.collision.canonical_repo_root)) return undefined;
  const rel=args[3].split(path.sep).join("/");
  if (!value.collision.stale_paths.some(item=>item.path===rel)) return undefined;
  if (args[4]!=="--state-root") return undefined;
  return args;
}
function autoWarm(config:PluginConfig,value:Pending): boolean {
  if (!config.autoWarm || value.autoWarmSucceeded) return value.autoWarmSucceeded;
  if (value.autoWarmAttempts >= 1) return false;
  value.autoWarmAttempts++;
  const args=safeWarmArgs(value.collision.recovery_commands?.[0],config,value);
  if (!args) return false;
  const proc=spawnSync(args[0],args.slice(1),{cwd:value.collision.canonical_repo_root,encoding:"utf8",env:tmfEnv(config,{repoRoot:value.collision.canonical_repo_root,stateRoot:value.collision.canonical_state_root})});
  value.autoWarmSucceeded=proc.status===0;
  if (value.autoWarmSucceeded) value.notices=0;
  return value.autoWarmSucceeded;
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
  for (const item of value.collision.stale_paths) {
    item.current_source_blob=blobSha(path.join(value.collision.canonical_repo_root,item.path));
  }
  value.sourceChanged=true;
  value.observed.clear();
  value.autoWarmAttempts=0;
  value.autoWarmSucceeded=false;
  value.notices=0;
  value.createdAt=Date.now();
  value.expiresAt=value.createdAt+DEFAULT_TTL_MS;
  for (const [key,candidate] of reads) if(candidate.pendingKey===pendingKey(value.session,{repoRoot:value.collision.canonical_repo_root,stateRoot:value.collision.canonical_state_root})) reads.delete(key);
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
  const repo=route(file,config.repos||[]); if (!repo) return undefined;
  const session=sessionIdentity(ctx,event);
  const key=session?pendingKey(session,repo):undefined;
  const active=key?pending.get(key):undefined;

  if (active && toolName==="read") {
    const matches=active.collision.stale_paths.filter(item=>path.join(active.collision.canonical_repo_root,item.path)===path.resolve(file));
    if (!matches.length) return undefined;
    const state=sameRequiredBlobs(active); if (state==="missing") return block(config,"missing",active); if(state==="changed") { rearmSource(active); return block(config,"source_changed",active); }
    // Warm must be independently current before a Read can become an observation token.
    let check=invokePython(event,cwd,config,repo);
    if (check.status===2) {
      if (!autoWarm(config,active)) return block(config,"need_warm",active);
      check=invokePython(event,cwd,config,repo);
    }
    if (check.status!==0 || check.decision?.decision!=="allow") return block(config,"engine_error",active);
    active.sourceChanged=false;
    if (!matches.every(item=>{
      const source=path.join(active.collision.canonical_repo_root,item.path);
      let totalLines:number|undefined;
      try { const text=fs.readFileSync(source,"utf8"); totalLines=text.length===0?0:text.split(/\r?\n/).length-(text.endsWith("\n")?1:0); }
      catch { return false; }
      return coversAnchor(params,item,totalLines);
    })) return block(config,"need_read",active);
    const ck=callKey(ctx,event); if (ck) reads.set(ck,{pendingKey:key!,paths:matches.map(x=>x.path),blobs:new Map(matches.map(x=>[x.path,x.current_source_blob!]))});
    return undefined;
  }

  if (active && dependencyMatch(active,toolName,file)) {
    const state=sameRequiredBlobs(active); if(state==="missing") return block(config,"missing",active); if(state==="changed") { rearmSource(active); return block(config,"source_changed",active); }
    if (active.sourceChanged) return block(config,"need_warm",active);
    let check=invokePython(event,cwd,config,repo);
    if (check.status===2) {
      if (!autoWarm(config,active)) return block(config,"need_warm",active);
      check=invokePython(event,cwd,config,repo);
    }
    if (check.status!==0 || check.decision?.decision!=="allow") return block(config,"engine_error",active);
    const required=new Set(active.collision.stale_paths.map(x=>x.path));
    if ([...required].some(p=>!active.observed.has(p))) return block(config,"need_read",active);
    const rel=path.relative(canonicalRepo(repo).repoRoot,file).split(path.sep).join("/");
    if (actionFingerprint(toolName,params,rel)===active.collision.blocked_action_fingerprint) return block(config,"stale_retry",active);
    const ck=callKey(ctx,event);
    if (!ck) return block(config,"engine_error",active);
    mutations.set(ck,{pendingKey:key!,fingerprint:actionFingerprint(toolName,params,rel)});
    return undefined;
  }

  const check=invokePython(event,cwd,config,repo);
  if (check.status!==2 || check.decision?.schema_version!=="tmf.reflex.collision.v1") return undefined;
  const collision=check.decision as Collision;
  if (session) {
    collision.session_identity=session; collision.run_identity=event.runId||ctx.runId||null;
    const now=Date.now(), value:Pending={collision,session,repoKey:repoKey(repo),createdAt:now,expiresAt:now+(config.pendingTtlMs||DEFAULT_TTL_MS),notices:0,observed:new Set(),sourceChanged:false,autoWarmAttempts:0,autoWarmSucceeded:false};
    pending.set(pendingKey(session,repo),value);
    if (autoWarm(config,value)) {
      if (toolName==="read") {
        const matches=value.collision.stale_paths.filter(item=>path.join(value.collision.canonical_repo_root,item.path)===path.resolve(file));
        if (matches.length && matches.every(item=>{
          const source=path.join(value.collision.canonical_repo_root,item.path);
          let totalLines:number|undefined;
          try { const text=fs.readFileSync(source,"utf8"); totalLines=text.length===0?0:text.split(/\r?\n/).length-(text.endsWith("\n")?1:0); }
          catch { return false; }
          return coversAnchor(params,item,totalLines);
        })) {
          const ck=callKey(ctx,event); if (ck) reads.set(ck,{pendingKey:pendingKey(session,repo),paths:matches.map(x=>x.path),blobs:new Map(matches.map(x=>[x.path,x.current_source_blob!]))});
          return undefined;
        }
      }
      return block(config,"need_read",value);
    }
    return block(config,"need_warm",value);
  }
  return block(config,"need_warm");
}

export function runAfterToolCall(event:any,cwd:string,config:PluginConfig,ctx:HookContext={}):void {
  expire();
  const ck=callKey(ctx,event); if(!ck) return;
  const tool=String(event.toolName||"").toLowerCase();
  if(tool==="read") {
    const candidate=reads.get(ck); reads.delete(ck); if(!candidate || event.error) return;
    const active=pending.get(candidate.pendingKey); if(!active) return;
    for(const rel of candidate.paths) if(blobSha(path.join(active.collision.canonical_repo_root,rel))===candidate.blobs.get(rel)) active.observed.add(rel);
    return;
  }
  const candidate=mutations.get(ck); mutations.delete(ck); if(!candidate || event.error) return;
  const active=pending.get(candidate.pendingKey); if(!active) return;
  const file=resolveFile(event.params||{},cwd);
  if(!file) return;
  const rel=path.relative(active.collision.canonical_repo_root,file).split(path.sep).join("/");
  if(actionFingerprint(tool,event.params||{},rel)===candidate.fingerprint) pending.delete(candidate.pendingKey);
}
export function cleanupSession(event:any,ctx:HookContext={}):void {
  const ids=new Set([event?.sessionKey,event?.sessionId,event?.runId,ctx.sessionKey,ctx.sessionId,ctx.runId].filter(Boolean).map(String));
  for(const [key,value] of pending) if(ids.has(value.session)) pending.delete(key);
  for(const key of reads.keys()) if([...ids].some(id=>key.startsWith(`${id}\0`))) reads.delete(key);
  for(const key of mutations.keys()) if([...ids].some(id=>key.startsWith(`${id}\0`))) mutations.delete(key);
}
export function debugState():any { expire(); return {pending:pending.size,reads:reads.size,mutations:mutations.size}; }
export function resetState():void { pending.clear(); reads.clear(); mutations.clear(); }

export function runSessionStart(repo:RepoConfig,config:PluginConfig):string|undefined {
  const stateRoot=canonicalRepo(repo).stateRoot!; if(!fs.existsSync(stateRoot)) return undefined;
  const proc=spawnSync(config.python||"python3",[path.join(integrationRoot,"hooks","session_start.py"),"--repo",path.resolve(repo.repoRoot),"--state-root",stateRoot,"--json"],{encoding:"utf8"});
  if(proc.status!==0)return undefined; try{return JSON.parse(proc.stdout).injection||undefined}catch{return undefined}
}
const plugin={id:"tmf-reflex",register(api:any){
  const config:PluginConfig=api.pluginConfig||{}; if(config.enabled===false)return;
  const cwd=(()=>{try{return api.runtime.agent.resolveAgentWorkspaceDir(api.config)||process.cwd()}catch{return process.cwd()}})();
  api.on("before_tool_call",async(event:any,ctx:any)=>runPreToolUse(event,cwd,config,ctx));
  api.on("after_tool_call",async(event:any,ctx:any)=>runAfterToolCall(event,cwd,config,ctx));
  api.on("session_start",async(event:any)=>{for(const repo of config.repos||[]){const injection=runSessionStart(repo,config);if(injection)await api.session.workflow.enqueueNextTurnInjection({text:injection,placement:"prepend_context",metadata:{kind:"tmf_session_start_calibration"}})}});
  api.on("session_end",async(event:any,ctx:any)=>cleanupSession(event,ctx));
}};
export default plugin;
