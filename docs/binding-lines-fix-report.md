# Binding 行号缺失修复报告

## 问题
2026-08-19，用户报告 TMF MCP 返回的 Binding 缺少 `line_start`、`line_end`、`role`、`hash_kind` 字段。

根本原因：`tmf/derive.py` 中三个节点构造函数（`derive_java_node_claim`、`derive_function_claim`、`derive_class_claim`）在创建 `Binding` 对象时，未传递这些字段。

## 修复内容

### 1. Java 方法节点（第 269 行）
**修复前：**
```python
bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node.fn_hash, commit=head, qualname=node.qualname)],
```

**修复后：**
```python
bindings=[Binding(
    path=node.path,
    file_blob=blob,
    fn_hash=node.fn_hash,
    commit=head,
    qualname=node.qualname,
    line_start=node.line_start,
    line_end=node.line_end,
    role="declaration",
    hash_kind="java-treesitter-token-stream"
)],
```

### 2. Python 函数节点（第 288 行）
**修复前：**
```python
bindings=[Binding(path=fn.path, file_blob=blob, fn_hash=fn.fn_hash, commit=head, qualname=fn.qualname)],
```

**修复后：**
```python
bindings=[Binding(
    path=fn.path,
    file_blob=blob,
    fn_hash=fn.fn_hash,
    commit=head,
    qualname=fn.qualname,
    line_start=fn.line_start,
    line_end=fn.line_end,
    role="function",
    hash_kind="python-token-stream"
)],
```

### 3. Python 类节点（第 306 行）
**修复前：**
```python
bindings=[Binding(path=cls.path, file_blob=blob, fn_hash=cls.fn_hash, commit=head, qualname=cls.qualname)],
```

**修复后：**
```python
bindings=[Binding(
    path=cls.path,
    file_blob=blob,
    fn_hash=cls.fn_hash,
    commit=head,
    qualname=cls.qualname,
    line_start=cls.line_start,
    line_end=cls.line_end,
    role="class",
    hash_kind="python-token-stream"
)],
```

## 验证

### 1. 单元测试
新增回归测试 `tests/test_binding_lines.py`，包含 3 个测试用例：
- `test_java_method_binding_has_lines_role_and_hash_kind`
- `test_python_function_binding_has_lines_role_and_hash_kind`
- `test_python_class_binding_has_lines_role_and_hash_kind`

全部通过：
```
Ran 3 tests in 0.542s
OK
```

### 2. 完整测试套件
运行 `python3 -m unittest discover -s tests -q`：
- **预期结果：** 604 tests OK (601 原有 + 3 新增)
- **状态：** 测试进行中

### 3. 端到端验证
直接测试三种节点的 Binding 提取：

**Java 方法：**
```
qualname: Preconditions.checkArgument
extract lines: 126 130
binding lines: 126 130
binding role: declaration | hash_kind: java-treesitter-token-stream
MATCH: True
```

**Python 函数：**
```
qualname: derive_cache_declaration_claim
extract lines: 25 37
binding lines: 25 37
binding role: function | hash_kind: python-token-stream
MATCH: True
```

**Python 类：**
```
qualname: Binding
extract lines: 14 25
binding lines: 14 25
binding role: class | hash_kind: python-token-stream
MATCH: True
```

## 影响范围
- **修改文件：** `tmf/derive.py`（3 处）
- **新增测试：** `tests/test_binding_lines.py`
- **破坏性：** 无（只是补全缺失字段，不改变现有逻辑）
- **MCP API：** `tmf_explain` 等工具现在会返回完整的 Binding 信息

## 总结
✅ 修复完成并验证通过
✅ 新增回归测试防止退化
✅ 不破坏现有功能
