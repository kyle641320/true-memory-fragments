# TMF 开源推广前执行计划

日期：2026-09-04
状态：执行中

## 总目标

在不夸大现有证据的前提下，把 TMF 从“有硬机制证据的研究型仓库”推进到“可被外部复现、可安装、可审阅、适合公开推广”的状态。

## 当前基线

已具备：

- M10 r50：PREREAD 2/50，TMF 42/50；stale 记忆误导 96%，TMF 引错 0%。
- Guava R21 四臂：仅 stale note 时失败；加入 entry hints / 局部 locator 后通过。
- Guava freshness、stale hard-stop、跨进程持久化闭环、局部 re-warm 机制已有确定性证据。
- R21 已推送到 `kyle641320/true-memory-fragments`，commit `a956db0`。

未完成：

- 证据仍集中在 Guava/单类 fixture 系，M11-M15 企业场景区分度不足。
- 检索层 lexical recall/MRR 偏弱。
- Java typed field-receiver calls 存在 0/7 召回缺口。
- understanding tier 有 schema，但缺乏稳定 pipeline 产出。
- 安装仍需 venv、Java parser、hooks、MCP 和 warm 配置。
- 外部非作者复现案例和社区信任信号不足。

## 执行顺序

### P0-A：证据覆盖扩展

目标：补出至少 3 个与 Guava 不同的、有明确 stale 陷阱和 oracle 区分度的场景；优先复用已有企业场景设计，不做短链路 SOURCE_ONLY 对照。

验收：

- 每个场景有真实多跳链、stale mutation、硬 oracle。
- 至少包含一个 Java typed receiver 场景。
- 报告 raw/protocol-clean/semantic-adjusted 分数。
- 明确记录 TMF、PREREAD、STALE_DOC 各自赢/输，不能选择性展示。

### P0-B：修 Java typed field-receiver calls

目标：补齐明确可解析的 `field.receiver` 调用边；未知类型继续 unresolved，禁止猜测连边。

验收：

- 复现既有 0/7 缺口。
- 新增最小 fixture 和回归测试。
- 在 Guava/企业场景上重新统计召回。

### P0-C：修 lexical retrieval

目标：提升 exact symbol、path、自然语言查询的召回与排序；以既有 frozen queries 为基准。

验收：

- 报告 Recall@3/@5/@10、MRR、按 query 类型分组。
- 不得提升语义查询而回归 exact-name/path 查询。
- 只有可复现实测改善才算完成。

### P1-A：understanding tier 端到端产出

目标：让 semantic contract 从 schema/代码路径变成可查询、可 freshness 绑定的实际 claim。

验收：

- pipeline 能稳定生成 understanding claim。
- store/retrieve/explain 均能读到。
- 有正例、空产出和失败原因。

### P1-B：安装体验

目标：最短路径：

```bash
pip install "true-memory-fragments[java]"
tmf init
tmf warm
tmf install-hook
```

验收：

- 干净环境可复现。
- Java 依赖、state root、MCP 配置和 hook 注册有诊断。
- 首次 warm 与增量 refresh 的时间/资源有明确说明。

### P1-C：公开材料

目标：README 增加限制、失败案例、复现命令、R21/M10 数据和至少 2 个非作者复现记录。

验收：

- 不声称全面优于 Atlas/Maka。
- 明确 scoped evidence 与未验证项。
- 社区发布前先做一次外部审阅清单。

## P1-C：公开材料与自然发现（新增，2026-09-05）

### 结论

README 当前更像研究档案，不像陌生用户的产品入口：首屏先讲 Bionic Design Philosophy / Pain Reflex，真实用户痛点、安装路径和 30 秒 Demo 埋得太深。GitHub 自然 Star 长期不足不能简单归因于技术价值不足，更可能是“用户搜索语言—README 首屏—可复制 Demo—外部分发”闭环尚未形成。

### SEO / discoverability 口径

SEO（Search Engine Optimization）在这里指让 GitHub、Google 和社区用户用真实问题搜索时能找到项目，不是机械堆关键词。优先覆盖：`AI coding agent memory`、`stale context prevention`、`source-aware code memory`、`code graph for LLM agents`、`Claude Code memory`、`cross-session code understanding`。

### 已采取动作

- README 首屏改为“stale-context protection for AI coding agents”。
- 增加问题场景、无 TMF/有 TMF 对比、适用范围与明确非目标。
- 将证据状态前置，但保留 scoped evidence，不夸大 productivity/token savings。
- 增加 30-second mental model 和 SEO/discoverability 说明。

### 后续动作

1. 制作一个 30 秒终端/GIF Demo。
2. 写一篇真实 stale-context 案例文章，并链接回 README。
3. 完善 GitHub topics、仓库 description、Quick Start 和最短安装路径。
4. 将完整实验材料与研究报告下沉到 docs/evidence，避免 README 首屏研究化。
5. 在 Claude Code / MCP / AI coding agent 相关社区做定向发布；不把“自然 Star”当作仅靠 README 自动发生的结果。

### 验收标准

- 陌生开发者 30 秒内能回答“TMF 解决什么问题”。
- 5 分钟内能完成最小安装/运行。
- README 明确已验证、部分验证、未验证三类结论。
- 外部发布材料至少包含一个可复现 Demo，而不是只有理论和实验报告。



1. 先盘点已有 M11-M15 场景与缺口，选择最有区分度的 3 个，不启动全仓 warm。
2. 对选中场景先做 deterministic fixture/oracle 设计，再决定是否跑模型。
3. 任何新增结果必须独立复验；失败归因分 raw/protocol/semantic/TMF。
4. 每完成一个阶段写报告并更新本计划状态。

## 明确禁止

- 不再把 zhihu 仓证据当作完整 TMF 证据。
- 不再重复短链路 SOURCE_ONLY 对照作为主线。
- 不把 runner-level guard 冒充 live OpenClaw hook E2E。
- 不为制造好看的结果删除失败场景。
- 不修改冻结的 TMF engine 目录以外的实验目标，除非本计划对应修复项明确授权。

## 当前下一步

盘点 M11-M15 现有场景，选出 3 个最可能形成有效 stale 陷阱的企业场景，形成 `M11_M15_SCENARIO_GAP_AUDIT.md`；然后先做 fixture/oracle，不立即跑昂贵模型。
