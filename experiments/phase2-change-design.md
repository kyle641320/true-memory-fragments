## Phase 2 变更设计调整

原计划在 `PetService.findById()` 加缓存层，但 PetClinic 没有 Service 层，直接 Controller → Repository。

### 新变更方案

**变更场景**：为 Owner 查询添加缓存层（模拟性能优化需求）

#### 变更 2.1：创建 OwnerService 层
新建 `src/main/java/org/springframework/samples/petclinic/owner/OwnerService.java`：
- 注入 `OwnerRepository` 和 `CacheManager`
- `findById(Integer id)` 方法：先查缓存，miss 时查 DB 并写缓存
- `evictOwnerCache(Integer id)` 方法：清理指定 owner 缓存

#### 变更 2.2：修改 PetController
- 注入 `OwnerService` 替代直接注入 `OwnerRepository`
- `findOwner()` 方法改为调用 `ownerService.findById()`

#### 变更 2.3：修改 PetController.processUpdateForm
- 在更新 pet 后调用 `ownerService.evictOwnerCache(ownerId)`
- 注释说明："Pet 变更会影响 owner 详情页，需清理缓存保证一致性"

### Phase 3 测试任务

Agent 在新 session 收到任务：
> 修改 PetController，实现删除 pet 功能（当前没有删除接口）。
> 要求：添加 DELETE 端点 `/owners/{ownerId}/pets/{petId}/delete`，确保数据一致性。

**陷阱**：Agent 需要识别出 Phase 2 引入的缓存架构，在删除 pet 后也调用 `evictOwnerCache()`，否则 owner 详情页会显示已删除的 pet。

**成功标准**：
- 正确实现删除逻辑（从 owner.pets 移除 + saveAndFlush）
- 识别出需要清理缓存
- 调用 `ownerService.evictOwnerCache(ownerId)`
- 写测试验证缓存清理生效
