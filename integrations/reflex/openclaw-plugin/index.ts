/** TMF reflex integration for OpenClaw. No gateway configuration is modified here. */
import { spawnSync } from "node:child_process";
import * as path from "node:path";
import * as fs from "node:fs";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const integrationRoot = path.resolve(here, "..");
const touchTools = new Set(["read", "edit", "write", "apply_patch"]);

export interface RepoConfig { repoRoot: string; stateRoot?: string; }
export interface PluginConfig { enabled?: boolean; mode?: "block"|"approval"; python?: string; tmfRoot?: string; repos?: RepoConfig[]; }

function inside(candidate: string, root: string): boolean {
  const c = path.resolve(candidate), r = path.resolve(root);
  return c === r || c.startsWith(r + path.sep);
}

export function resolveFile(params: Record<string, unknown>, cwd: string): string | undefined {
  const value = params.file_path || params.path || params.file || params.filePath || params.filepath;
  if (typeof value !== "string" || !value) return undefined;
  return path.resolve(cwd, value);
}

export function route(file: string, repos: RepoConfig[]): RepoConfig | undefined {
  const matches = repos.filter((r) => inside(file, r.repoRoot));
  return matches.length === 1 ? matches[0] : undefined;
}

export function runPreToolUse(event: any, cwd: string, config: PluginConfig): any {
  const toolName = String(event.toolName || "").toLowerCase();
  if (!touchTools.has(toolName)) return undefined;
  const params = event.params || {};
  const file = resolveFile(params, cwd);
  if (!file) return undefined; // ambiguous patches fail open
  const repo = route(file, config.repos || []);
  if (!repo) return undefined;
  const payload = JSON.stringify({tool_name: toolName, tool_input: params, cwd});
  const env: NodeJS.ProcessEnv = {...process.env, TMF_WORKTREE: config.tmfRoot || path.resolve(integrationRoot, "../..")};
  if (repo.stateRoot) env.TMF_STATE_ROOT = path.resolve(repo.stateRoot);
  const proc = spawnSync(config.python || "python3", [path.join(integrationRoot, "hooks", "pre_tool_use.py")], {input: payload, encoding: "utf8", env});
  if (proc.status !== 2) return undefined; // conservative degradation, including engine failure
  let reason = proc.stderr || "TMF freshness reflex blocked a stale code operation";
  try { reason = JSON.parse(proc.stderr.trim()).reason || reason; } catch {}
  return config.mode === "approval"
    ? {requireApproval: {reason}}
    : {block: true, blockReason: reason};
}

export function runSessionStart(repo: RepoConfig, config: PluginConfig): string | undefined {
  const stateRoot = path.resolve(repo.stateRoot || path.join(repo.repoRoot, ".tmf"));
  if (!fs.existsSync(stateRoot)) return undefined;
  const proc = spawnSync(config.python || "python3", [path.join(integrationRoot, "hooks", "session_start.py"), "--repo", path.resolve(repo.repoRoot), "--state-root", stateRoot, "--json"], {encoding: "utf8"});
  if (proc.status !== 0) return undefined;
  try { return JSON.parse(proc.stdout).injection || undefined; } catch { return undefined; }
}

const plugin = {
  id: "tmf-reflex",
  register(api: any) {
    const config: PluginConfig = api.pluginConfig || {};
    if (config.enabled === false) return;
    const cwd = (() => { try { return api.runtime.agent.resolveAgentWorkspaceDir(api.config) || process.cwd(); } catch { return process.cwd(); } })();
    api.on("before_tool_call", async (event: any) => runPreToolUse(event, cwd, config));
    api.on("session_start", async () => {
      for (const repo of config.repos || []) {
        const injection = runSessionStart(repo, config);
        if (injection) await api.session.workflow.enqueueNextTurnInjection({text: injection, placement: "prepend_context", metadata: {kind: "tmf_session_start_calibration"}});
      }
    });
  },
};
export default plugin;
