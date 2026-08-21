# TMF 综合能力 A/B 验证实验设计

## 实验目标

验证 TMF 痛觉机制在真实开发场景中是否能显著改善 Agent 跨 session 代码修改的质量和效率。

## 核心假设

**H1: 准确性假设**
- 有 TMF 的 Agent 在代码发生变更后，能正确识别需要重读的函数，避免基于过时理解做出错误修改
- 无 TMF 的 Agent 更容易产生与新代码逻辑冲突的修改

**H2: 效率假设**
- 有 TMF 的 Agent 只重读变更相关的函数，session context 使用更高效
- 无 TMF 的 Agent 需要更多轮次的"试错-重读-修正"循环

## 实验设计

### 测试语言与项目
- **主测语言**: Java（已验证 AST 解析和函数级 hash）
- **测试项目**: Spring PetClinic（经典 Spring Boot 示例项目，约 2k-3k LOC，有完整测试覆盖）
- **选择理由**: 
  - 真实业务逻辑（CRUD + 业务规则）
  - 多层架构（Controller → Service → Repository）
  - 适中规模（不会因项目过大导致实验变量失控）

### A/B 两组设置

**Group A (对照组 - 无 TMF)**
- 标准 OpenClaw Agent
- 无函数级变更感知
- 依赖 LLM 自行判断是否需要重读代码

**Group B (实验组 - 有 TMF)**
- OpenClaw Agent + TMF reflex hook
- Git post-commit/post-merge 自动生成 stale 清单
- SessionStart 自动注入变更函数警告
- Tool call 前检查 freshness（可选：启用 requireApproval 强制重读）

### 实验流程（每组独立执行）

#### Phase 1: 初始任务（建立基线认知）
Agent 在 session-1 完成初始任务：
- **Task 1.1**: 阅读 `PetController.findPet()` 和 `PetService.findById()` 
- **Task 1.2**: 总结当前宠物查询逻辑的实现方式
- **任务结束**: 记录 Agent 的理解（通过问答验证）

#### Phase 2: 人工引入代码变更
在 session-1 结束后，人工修改代码库：
- **变更 2.1**: `PetService.findById()` 新增缓存层（从直接 DB 查询改为先查 Redis）
- **变更 2.2**: 新增 `PetService.evictCache()` 方法
- **变更 2.3**: `PetController.updatePet()` 调用 `evictCache()` 保证一致性
- Git commit 提交这些变更

#### Phase 3: 跨 session 修改任务
Agent 在 session-2（新 session，无前序 context）收到任务：
- **Task 3.1**: 修改 `PetController.deletePet()` 方法，确保删除宠物时也清理缓存
- **成功标准**: 
  - 正确识别需要调用 `evictCache()`
  - 理解新的缓存架构（Phase 2 引入的）
  - 修改后的代码通过集成测试

#### Phase 4: 结果评估
对比两组的：
- **准确性指标**:
  - 是否识别出 `PetService` 已改为缓存架构？
  - 是否正确调用 `evictCache()`？
  - 是否产生与新代码逻辑冲突的修改？
  - 修改后的代码是否通过测试？
- **效率指标**:
  - 重读代码的函数数量
  - 完成任务的 turn 数
  - 试错-修正的循环次数
  - Session context token 消耗

### 实验变量控制

**固定变量**:
- 同一个 LLM 模型
- 同一套 system prompt
- 同一个测试项目和变更集
- 同样的任务描述

**自变量**:
- 是否启用 TMF reflex hook

**因变量**:
- 任务完成质量（准确性）
- 任务完成效率（turn 数、token 数）

## 预期结果

**Group A (无 TMF) 预期表现**:
- Agent 可能直接基于"上次看到的代码印象"做修改
- 不会主动意识到 `PetService.findById()` 已改变
- 可能产生"直接操作 DB 而不清理缓存"的错误代码
- 需要经过测试失败 → 重读代码 → 修正的循环

**Group B (有 TMF) 预期表现**:
- SessionStart 时看到 `PetService.findById()` / `evictCache()` / `PetController.updatePet()` 在 stale 清单
- Agent 在开始 Task 3.1 前主动重读这些函数
- 正确理解新的缓存架构
- 一次性产生正确的修改（调用 `evictCache()`）

## 实验执行计划

1. **准备阶段** (0.5h)
   - Clone Spring PetClinic
   - 准备 Phase 2 变更的 patch 文件
   - 编写 Phase 3 任务描述和评估脚本

2. **Group A 执行** (1h)
   - Session-1: 初始任务
   - 应用变更 patch
   - Session-2: 跨 session 修改任务
   - 记录全过程 transcript 和指标

3. **Group B 执行** (1h)
   - 重置代码库
   - 启用 TMF reflex hook
   - 重复 Group A 的完整流程
   - 记录全过程 transcript 和指标

4. **结果分析** (0.5h)
   - 对比两组的准确性和效率指标
   - 分析 TMF 痛觉机制的实际效果
   - 记录意外发现和改进方向

## 实验风险与应对

**风险 1: Agent 行为不可控**
- 即使在无 TMF 的情况下，Agent 也可能"碰巧"主动重读代码
- **应对**: 多次重复实验（至少 3 次），看统计趋势

**风险 2: 任务过于简单**
- 如果缓存逻辑变更太明显，即使无 TMF 也能轻松发现
- **应对**: 准备 2-3 个不同复杂度的变更场景

**风险 3: TMF 误报过多**
- 如果 stale 清单包含大量无关函数，反而干扰 Agent
- **应对**: 评估 stale 清单的精准度（相关函数 / 总函数）

## 输出物

1. **实验报告** (`ab-validation-report.md`)
   - 两组完整 transcript
   - 指标对比表格
   - 统计显著性分析（如果重复多次）
   
2. **痛觉机制有效性结论**
   - TMF 在真实场景的实际价值
   - 当前实现的优势和局限
   - 后续改进方向
