import { createBridge, openControlChannel, qualify, TOOL_NAME, PLUGIN_ID } from './bridge.mjs';

// Plugin registries may be rebuilt to activate the selected harness. A run-owned
// process singleton keeps the registered factory attached to this exact socket.
const bridgeKey = Symbol.for('tmf.successor.exact-process-bridge.v1');

export default {
  id: PLUGIN_ID,
  register(api) {
    const getBridge = () => globalThis[bridgeKey];
    api.registerTool(() => {
      const bridge = getBridge();
      const frame = bridge?.getFrame();
      if (!frame) return null;
      return {name: TOOL_NAME, label: TOOL_NAME, description: frame.tool.description,
        parameters: frame.tool.input_schema,
        execute: async (id, args) => bridge.action(id, args)};
    }, {names: [TOOL_NAME]});
    for (const hook of ['llm_input', 'llm_output', 'agent_end', 'before_compaction', 'after_compaction']) {
      api.on(hook, event => getBridge()?.observe(hook, event));
    }
    api.on('before_tool_call', event => {
      const bridge = getBridge();
      if (!bridge) return;
      bridge.observe('before_tool_call', event);
      if (event.toolName !== TOOL_NAME || bridge.signal.aborted) {
        bridge.stop('tool_bypass', {toolName: event.toolName});
        return {block: true, blockReason: 'successor exclusive mediated tool surface'};
      }
    });
    api.on('after_tool_call', event => getBridge()?.observe('after_tool_call', event));
    api.registerCli(({program}) => {
      program.command('successor-host')
        .description('Qualify or execute the sealed successor control bridge')
        .option('--qualify', 'Load and validate public capability without invoking a model')
        .option('--run', 'Execute one controller-admitted run on inherited control socket')
        .action(async options => {
          if (Boolean(options.qualify) === Boolean(options.run)) throw new Error('select_qualify_or_run');
          const result = qualify(api, api.pluginConfig);
          if (options.qualify) { process.stdout.write(JSON.stringify(result) + '\n'); return; }
          if (getBridge()) throw new Error('duplicate_process_run');
          globalThis[bridgeKey] = createBridge(api, api.pluginConfig, openControlChannel());
          await globalThis[bridgeKey].done;
        });
    }, {descriptors: [{name: 'successor-host', description: 'Qualify or execute the sealed successor control bridge',
      hasSubcommands: false, machineOutput: () => true}]});
  },
};
