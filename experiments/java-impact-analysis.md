# Java Impact Analysis Experiment

**Date**: 2026-08-20  
**Goal**: Validate TMF's ability to track Java field-type relationships and compute accurate blast radius for interface/class changes

## Background

TMF v1 已支持 Python 的 reads/writes/calls 边，但 Java 生态的依赖关系更复杂：
- DI 容器注入（Spring `@Autowired`）
- 接口-实现解耦
- 类型系统（泛型、继承、多态）

本实验验证 TMF 能否正确追踪：
1. 字段类型声明（field → uses_type → class）
2. 方法读字段（method → reads → field）
3. 通过类型边计算爆炸半径

## Test Case: Spring PetClinic

### 目标场景
用户修改 `OwnerService` 接口，需要知道哪些方法会受影响。

### 关键路径
```
PetController.processCreationForm (method)
  → reads → PetController.ownerService (field)
  → uses_type → OwnerService (class)
```

### 验证结果

#### 1. Field Type Resolution ✓

TMF 成功识别字段类型：
- Claim: `claim_java_9937a6d34ce5cf9c` (PetController.ownerService)
- Type: `claim_java_ebff279db81957b7` (OwnerService)
- Edge: `uses_type` 边正确建立

```bash
# Query result:
PetController.ownerService (field)
  uses_type → OwnerService (class)
```

#### 2. Method Reads Field ✓

TMF 成功追踪方法读字段：
- Method: `claim_java_422847b95fc76f75` (PetController.processCreationForm)
- Reads: `claim_java_9937a6d34ce5cf9c` (PetController.ownerService)

```bash
# Query result:
PetController.processCreationForm (method)
  reads → PetController.ownerService (field)
  reads → PetController.VIEWS_PETS_CREATE_OR_UPDATE_FORM (field)
  
  calls → Owner.getPet
  calls → OwnerService.saveAndFlush
  calls → PetController.isDuplicatePetNameViolation
  calls → Pet.getBirthDate
  calls → Owner.addPet
```

#### 3. End-to-End Blast Radius ✓

`experiments/validate-java-impact.py OwnerService` 实际输出 5 个方法：

| 方法 | 行号 |
|---|---|
| PetController.findOwner | 67-73 |
| PetController.findPet | 75-87 |
| PetController.processCreationForm | 107-137 |
| PetController.processUpdateForm | 144-181 |
| PetController.updatePetDetails | 188-202 |

### Ground Truth 交叉验证

源码 grep `ownerService` 在 PetController 内的出现点：

```
53:  private final OwnerService ownerService;      // 声明
57:  public PetController(OwnerService ownerService, ...)  // 构造器参数
58:  this.ownerService = ownerService;            // 写入（正确排除）
69:  this.ownerService.findById(ownerId);         // findOwner      ✓
83:  this.ownerService.findById(ownerId);         // findPet        ✓
126: this.ownerService.saveAndFlush(owner);       // processCreationForm ✓
178: ownerService.evictOwnerCache(...);           // processUpdateForm   ✓
201: this.ownerService.saveAndFlush(owner);       // updatePetDetails    ✓
```

全仓范围确认（`grep -rn OwnerService src/main src/test`）：
- main 中除 `OwnerService.java` 自身外，仅 `PetController` 持有该类型
- test 目录零引用

**结论**：TMF 输出 = ground truth，precision 1.0 / recall 1.0，false positive 0 / false negative 0。构造器写入点被正确区分为 `writes` 而非 `reads`。

## Current Status

**✓ Proven**: TMF 可以通过 `reads` + `uses_type` 边追踪 Java 字段类型依赖，并计算精确爆炸半径。

## Implementation Plan

### Phase 1: Type-Aware Readers Query ✓ DONE
`experiments/validate-java-impact.py` 已实现并验证：
- 找到所有类型为 `OwnerService` 的字段
- 递归找到所有读取这些字段的方法
- 返回方法的 qualname + 文件位置

下一步可考虑把该查询逻辑收敛进 `tmf_readers` 的类型扩展模式（需要先解决下方 scope 语义问题）。

### Phase 2: Interface Hierarchy (Future)
扩展支持接口/继承链：
- `OwnerService` (interface) ← `OwnerServiceImpl` (implementation)
- 查询时自动包含所有实现类

### Phase 3: Call Chain Analysis (Future)
支持多跳传播分析：
- 方法 A 读字段 `ownerService`
- 方法 B 调用方法 A
- 修改 `OwnerService` 时，方法 B 也在爆炸半径内

## Test Script Location
- Database: `/tmp/spring-petclinic/.tmf/index/claims.sqlite3`
- Validation script: `experiments/validate-java-impact.py` (TBD)

## Known Limitations (2026-08-20)

1. **Contract vs Declaration scope 混淆**（本次实验主要绊脚石）：
   - `tmf_readers` 当前只查 `scope=declaration` 的 claim
   - Java 方法体在 `scope=class` 下，方法签名另有一份 `scope=contract` claim
   - 关系边只挂在 `scope=class` 的方法体 claim 上；查 contract claim 得到 0 条边
   - 需要统一 scope 语义或让查询层支持多 scope fallback

1b. **字段候选集有重复/噪音**：
   - 脚本第 2 步打印出 `PetController.PetController`（构造器）和重复的 `ownerService`
   - 去重后不影响最终结果，但 SQL 子查询写法应收紧到单次 join

2. **Interface hierarchy 缺失**：
   - 当前只能查到直接类型匹配
   - 无法自动追踪 `OwnerService` → `OwnerServiceImpl`

3. **Generic types 未支持**：
   - `List<Owner>` 类型无法精确匹配

## References
- TMF v1 schema: `/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/docs/claims-schema.md`
- Spring PetClinic source: `/tmp/spring-petclinic`
