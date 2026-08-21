# TMF 验证实验：现状与路线图

最后更新：2026-08-20

## 一、已完成

### Java 语言支持验证（2026-08-20）
- 对象：Google Guava 真实提交 `8410194`（ExecutionSequencer RejectedExecutionException 修复）
- 结果：changed 6 / added 44 / deleted 0，与 git diff 完全吻合
- 覆盖能力：Java AST 解析、方法级 `fn_hash`、跨副本（android/guava 双目录）一致检测
- 结论：Java 的函数级变更检测链路可用

### README 仿生学设计补全（2026-08-20）
- 明确四类停止语义：Boundary / Async / Stale / Limit
- 明确 boundary（有把握地收敛）与 stale（明确地报废）的区别
- Commit `d8cea60`，已推 `kyle641320/true-memory-fragments` master

### Reflex Hook 集成文档（早前）
- 4 个 git 钩子：post-commit / post-merge / post-checkout / post-rewrite
- OpenClaw 插件 `before_tool_call` 拦截 + `requireApproval`
- SessionStart 注入 changed / deleted 符号预警

## 二、正在做：实验 1 — 痛觉机制 A/B 对照

设计文档：`experiments/ab-validation-design.md`

- 测试项目：Spring PetClinic（Java）
- 场景：session-1 建立认知 → 人工引入缓存架构变更 → session-2 跨会话修改
- 对照：Group A 无 TMF / Group B 有 TMF reflex hook
- 验证能力：函数级变更检测、痛觉机制（stale 警告）、跨 session 连续性
- 指标：准确性（是否识别架构变更、是否正确清理缓存、测试是否通过）+ 效率（重读函数数、turn 数、试错次数、token）

当前进度：设计完成，开始准备阶段（clone 项目 + 准备变更 patch + 评估脚本）

## 三、未来要做

### 实验 2 — 渐进认知 / bounded fragment
未被实验 1 覆盖的能力：按需展开调用链，而非重读单个函数。

- 任务形态：从 Controller 入口追踪到持久层，回答"这个请求最终写了哪些表/字段"
- 对照：有 TMF 时能否用 fresh claims 逐跳收敛并在 boundary 正确停止；无 TMF 时需要读多少文件
- 关键观察：boundary 停止是否准确（DB writes / 消息队列处收敛，而不是无限展开）
- 指标：展开跳数、读文件数、是否漏掉分支、是否在 boundary 误判为 stale

### 实验 3 — 关系图谱查询
- 反向查询：哪些函数调用了 `findById`？
- 数据流追踪：某字段被哪些函数写入 / 读取？
- 影响分析：修改这个方法会波及哪些调用方？
- 对照：TMF 图谱查询 vs grep/全文搜索的精准度与召回率
- 关键观察：precision/recall、是否遗漏动态调用、stale 边是否被正确排除

### 待评估的工程项
- Java 覆盖度：目前只验证了方法级 hash，接口实现/继承/override 关系尚未在 Java 上验证
- stale 清单精准度：如果误报过多会干扰 Agent，需要量化 相关函数/总函数 比例
- 多语言混合仓：Python + Java 同仓时的行为

## 四、边界与原则

- TMF 引擎（`worktrees/tmf-java-nodes-step0/tmf/`）冻结，实验期间只读使用
- TMF 输出只作为 freshness 标注的定位器，源码始终是权威
- locator 不可用时直接回退源码检查，不得中断调查
