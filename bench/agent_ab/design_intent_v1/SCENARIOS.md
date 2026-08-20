# design_intent_v1 实验场景设计

**设计者**: Javis  
**日期**: 2026-08-20  
**实验目标**: 测试 TMF 调用链连续性和隧道视野 bug 防护

## 核心假设

Agent 在 t₀ 理解完整调用链 `A→B→C→D`，代码在 t₁ 改动 `C`，Agent 在 t₂ 收到修改 `A` 的任务时：
- **无 TMF**: 可能只看 `A`，引入 bug（隧道视野）
- **有 TMF**: 检测到 `C` 过时，强制重读 `C`，避免 bug

## 实验对象

**Guava EventBus** (`com.google.common.eventbus`)
- 真实开源代码库
- 清晰的调用链路
- 约 2000 行，适合实验规模

## 场景 1: 事件分发链修改（下游影响）

### 调用链
```
EventBus.post(event)
  ↓
SubscriberRegistry.getSubscribers(event.getClass())
  ↓
Dispatcher.dispatch(event, subscribers)
  ↓
Subscriber.dispatchEvent(event)
```

### Phase A 任务（理解链路，答案丢弃）
**任务**: "Trace the complete call chain from `EventBus.post()` to actual subscriber method invocation. List every method in the chain and explain what each does."

**预期 claims**:
- `EventBus.post` calls `SubscriberRegistry.getSubscribers`
- `SubscriberRegistry.getSubscribers` calls `Subscriber.dispatchEvent`
- `Dispatcher.dispatch` iterates subscribers
- Chain length: 4 hops

### Phase B mutation
**改动**: 在 `Dispatcher.dispatch()` 中添加事件过滤逻辑：
```java
// 原代码：直接分发所有事件
void dispatch(Object event, Iterator<Subscriber> subscribers) {
  while (subscribers.hasNext()) {
    subscribers.next().dispatchEvent(event);
  }
}

// 改为：过滤掉某些事件
void dispatch(Object event, Iterator<Subscriber> subscribers) {
  if (event instanceof FilteredEvent) {
    return; // 新增：提前返回
  }
  while (subscribers.hasNext()) {
    subscribers.next().dispatchEvent(event);
  }
}
```

### Phase B 任务（需要完整链理解）
**任务**: "Modify `EventBus.post()` to add logging before dispatch. Make sure your logging captures all events, including filtered ones."

**预期差异**:
- **SOURCE_ONLY**: 只看 `post()`，在 `post()` 开头加日志，OK
- **TMF_STALE**: 检测到 `Dispatcher` 过时，重读后发现过滤逻辑，在 `post()` 开头加日志，OK
- **TMF_FRESH**: 但这个场景链路没变... 不太合适

**问题**: 这个 mutation 不够好，因为它没有破坏调用链，只是改了语义。

---

## 场景 2: 删除中间节点（上游依赖）

### 调用链
```
EventBus.post(event)
  ↓
SubscriberRegistry.getSubscribers(event.getClass())
  ↓
[iterate subscribers]
  ↓
Subscriber.dispatchEvent(event)
```

### Phase A 任务
**任务**: "List all methods that call `SubscriberRegistry.getSubscribers()`. Explain why each caller needs it."

**预期 claims**:
- `EventBus.post` calls `SubscriberRegistry.getSubscribers`
- Caller count: 1 (only `post`)

### Phase B mutation
**改动**: 重构 `getSubscribers` → 改名为 `findSubscribers`，但遗漏更新某个调用点（人工植入 bug）

### Phase B 任务
**任务**: "The method `SubscriberRegistry.getSubscribers()` was renamed to `findSubscribers()`. Update all call sites."

**预期差异**:
- **SOURCE_ONLY**: 全代码库搜索，找到所有调用点，全部更新
- **TMF_STALE**: claims 说 `post` 调用它，但 claims 过时（方法已改名），检测失效后重读，找到新方法名，更新调用点
- **TMF_FRESH**: claims 直接告诉它只有 `post` 调用，快速定位

**问题**: 这个场景测的是"找所有调用点"，不是"理解调用链避免 bug"。

---

## 场景 3: 异步边界移动（调用链语义变化）

### 调用链
```
AsyncEventBus.post(event)
  ↓
Dispatcher.dispatch(event, subscribers) [同步排队]
  ↓
executor.execute(() -> subscriber.dispatchEvent(event)) [异步边界]
```

### Phase A 任务
**任务**: "Trace the async boundary in `AsyncEventBus`. At which exact method call does execution switch from the calling thread to the executor thread? Explain why it's there."

**预期 claims**:
- Async boundary: `executor.execute` in `Subscriber.dispatchEvent`
- Calling thread: drains event queue
- Executor thread: invokes subscriber methods

### Phase B mutation
**改动**: 将异步边界移到 `post()` 入口：
```java
// 原代码：post() 同步，dispatchEvent() 异步
void post(Object event) {
  dispatcher.dispatch(event, getSubscribers(event));
}

// 改为：整个 dispatch 异步
void post(Object event) {
  executor.execute(() -> {
    dispatcher.dispatch(event, getSubscribers(event));
  });
}
```

### Phase B 任务
**任务**: "A performance optimization moved the async boundary from `Subscriber.dispatchEvent` to `AsyncEventBus.post`. Add a unit test that verifies event ordering is still preserved."

**预期差异**:
- **SOURCE_ONLY**: 读全部代码，理解新异步边界位置，写测试验证顺序（可能写错，因为不知道旧边界在哪）
- **TMF_STALE**: 检测到 `post` 和 `dispatchEvent` 都过时，重读两者，发现边界移动了，写测试验证新行为
- **TMF_FRESH**: claims 说旧边界在 `dispatchEvent`，但现在要测新代码... 这个场景有问题

**问题**: Phase B 的代码已经是新的，TMF_FRESH 的 claims 是旧代码的，不适用。

---

## 场景 4: 错误处理链补全（诊断追踪）

### 调用链
```
EventBus.post(event)
  ↓
Subscriber.dispatchEvent(event)
  ↓
try { method.invoke(target, event) }
  ↓
catch (InvocationTargetException e) {
    handleException(e.getCause(), context)
  }
```

### Phase A 任务
**任务**: "Trace how exceptions from subscriber methods are handled. List the complete chain: where is the exception thrown, caught, wrapped, and finally handled?"

**预期 claims**:
- `method.invoke` throws `InvocationTargetException`
- `Subscriber.dispatchEvent` catches and unwraps
- `EventBus.handleException` receives final exception
- Handler: `SubscriberExceptionHandler`

### Phase B mutation
**改动**: 在 `Dispatcher.dispatch()` 中添加新的异常捕获层：
```java
void dispatch(Object event, Iterator<Subscriber> subscribers) {
  while (subscribers.hasNext()) {
    try {
      subscribers.next().dispatchEvent(event);
    } catch (Exception e) {
      // 新增：吞掉所有异常，不再传播
      logger.warn("Subscriber failed", e);
    }
  }
}
```

### Phase B 任务
**任务**: "A bug report says subscriber exceptions are no longer reaching the `SubscriberExceptionHandler`. Debug and fix the issue."

**预期差异**:
- **SOURCE_ONLY**: 读全部错误处理代码，找到新加的 catch 块，删除它或改为重新抛出
- **TMF_STALE**: claims 说异常从 `dispatchEvent` 传到 `handleException`，但检测到 `dispatch` 过时，重读后发现新 catch 块吞异常了，修复
- **TMF_FRESH**: 不适用（代码已变）

**问题**: 同样的问题，Phase B 是新代码，TMF_FRESH 不适用。

---

## 重新设计：正确的实验结构

**问题根源**: Phase B 的代码是 mutated 版本，TMF_FRESH 的 claims 来自 base 版本，语义不匹配。

**正确结构**:
- **Phase A**: 在 **base** 版本上理解链路
- **Phase B mutation**: base → mutated
- **Phase B 三臂对比**:
  - **SOURCE_ONLY**: mutated 代码，无 claims
  - **TMF_STALE**: mutated 代码，stale claims (from base)
  - **TMF_FRESH**: **base 代码**，fresh claims (from base)

**等等，这不对。** TMF_FRESH 应该也在 mutated 代码上，但 claims 标记为 fresh（通过某种方式？）

**或者**:
- TMF_STALE: mutated 代码 + base claims → 检测失效 → 重读
- TMF_FRESH: base 代码 + base claims → 直接复用

但这样的话，TMF_FRESH 和 SOURCE_ONLY 不在同一份代码上，没法公平对比。

**正确理解**:

Phase B 任务应该在 **base** 代码上进行，不是 mutated 代码。Mutation 只是用来模拟"Phase A 和 Phase B 之间代码变了"的情况。

**重新设计**:

### 正确的 Phase B 结构

**Phase A (t₀)**: Agent 在 base v1 上理解链路，生成 claims
**时间流逝**: 代码从 base v1 → base v2 (mutation)
**Phase B (t₂)**: Agent 在 base v2 上收到新任务

**三臂对比**:
- **SOURCE_ONLY**: v2 代码，无 claims，从头理解
- **TMF_STALE**: v2 代码，v1 claims（过时），检测失效 → 局部重读
- **TMF_FRESH**: v1 代码，v1 claims（新鲜），直接复用

**不对，TMF_FRESH 还是在 v1 代码上，和其他两臂不公平。**

**彻底理解**:

TMF 的价值场景是：**Phase B 任务在变化后的代码上，但需要理解变化前的设计意图**。

例如：
- Phase A: 理解 v1 的设计（异步边界在哪，为什么）
- Code changes: v1 → v2 (异步边界移动了)
- Phase B: 在 v2 上做任务，但需要知道"v1 的设计是什么，v2 改了什么"

**三臂对比**:
- **SOURCE_ONLY**: v2 代码，无 claims → 只能看到 v2 现在是什么样，不知道 v1 是什么样
- **TMF_STALE**: v2 代码，v1 claims → 检测失效 → 重读 v2 相关部分 → 知道 v1→v2 变化
- **TMF_FRESH**: 这个臂不存在，因为 v2 代码上不可能有 fresh v2 claims（还没生成）

**所以只有两臂？**

不，**TMF_FRESH 应该是**: v2 代码，v2 claims (Phase A 在 v2 上重新生成)

**但这不是"cognitive continuity"，这是"重新理解"。**

---

## 最终理解：正确的实验设计

**TMF 的核心价值不是跨版本记忆，而是同版本下的调用链完整理解。**

**正确场景**:

### 场景：修改 A 时需要知道 A→B→C 完整链路

**Phase A**: Agent 理解 `EventBus.post()` 的完整调用链，生成 claims
**Phase B**: Agent 收到任务 "Add logging to EventBus.post()"

**三臂对比（都在同一份代码上）**:
- **SOURCE_ONLY**: 无 claims，读 `post()` 实现，加日志
  - **隧道视野风险**: 只看到 `post()` 调用 `getSubscribers` 和 `dispatch`，可能遗漏某些调用路径
- **TMF**: 有 claims，知道完整链路 `post → getSubscribers → dispatch → dispatchEvent`
  - **完整理解**: 加日志时考虑完整链路，不遗漏边界情况

**但这个任务太简单，"加日志"不需要理解完整链路。**

**更好的任务**:

**Phase B 任务**: "EventBus.post() is too slow. Profile and optimize the hotspot."

**预期差异**:
- **SOURCE_ONLY**: 只看 `post()` 方法体，可能优化错地方（如优化 `getSubscribers` 查找，但实际瓶颈在 `dispatchEvent`）
- **TMF**: 知道完整链路，profile 整条链，找到真正瓶颈

**但这需要真实 profile 数据，实验难度太高。**

---

## 结论：当前 TMF 实验设计困境

**根本问题**: TMF 的"调用链连续性"价值假设 **不适合用 A/B 实验测量**，因为：

1. **隧道视野 bug 需要真实编码任务**: 简单的"解释代码"任务不会触发隧道视野
2. **需要复杂任务才能体现价值**: 但复杂任务难以标准化评分
3. **"设计意图"难以客观测量**: 什么叫"理解了设计意图"？

**建议**:

不做 A/B 实验，改做 **案例研究 (Case Study)**:
- 选 1-2 个真实的 Agent 编码失败案例（隧道视野导致 bug）
- 手工分析：如果有 TMF 调用链 claims，是否能避免？
- 写成叙事报告，不追求统计显著性

**或者**:

承认当前 TMF 的价值主张 **无法通过自动化 A/B 实验验证**，只能通过：
- 真实用户反馈
- 长期使用体验
- 定性案例分析
