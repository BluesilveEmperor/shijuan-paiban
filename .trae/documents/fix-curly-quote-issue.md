# 修复方案：中文弯引号导致 JSON 解析失败的系统性问题

## Context

地理试卷排版v3.0 流水线中，AI 使用 Write 工具写入 JSON 文件时，中文弯引号 `""`（U+201C/U+201D）被转换为 ASCII `"`（U+0022），导致 JSON 解析失败，流水线中断。此问题影响 Step2-5 全部步骤，每次排版含弯引号的试卷都会触发。

**根因链**：Write 工具/模型输出管道转换弯引号 → JSON 语法断裂 → 解析失败 → 流水线停止

**项目中的5个设计缺陷**：
1. Write 工具对含弯引号的 JSON 不可靠
2. `sanitize_json.py` 被5个SKILL文件引用8次，但从未创建
3. SKILL指令矛盾："用Write工具" vs "别用Write工具写JSON"
4. `修复方案.md` 引用了v3.0中不存在的 `generate_structure.py`
5. 问题影响全部4个AI写JSON的步骤（Step2-5）

---

## 实施计划

### Step 1: 创建 `scripts/sanitize_json.py`

**核心脚本**，处理两种损坏场景：

- **场景A（语法断裂）**：`"stem": ""尾矿利用"环节"` → 内部 `"` 被当作字符串结束符，json.loads() 失败
- **场景B（语义损坏）**：`"stem": "被称为\"牧草之王\""` → json.loads() 成功但内容中 `"` 为 U+0022 而非 U+201C/U+201D

**算法**：
1. 尝试 json.loads() → 成功则进入 Phase 3 检查语义损坏
2. 失败则逐字符解析，在字符串值内部找到裸 `"` → 替换为 U+201C/U+201D
3. 重新 json.loads() → 成功则继续
4. 递归遍历 JSON 树，用正则修复中文语境中的 ASCII `"` 对 → `CJK"内容"CJK` → `CJK\u201c内容\u201dCJK`
5. json.dump(ensure_ascii=False, indent=2) 重写文件

**命令行接口**：
```
python scripts/sanitize_json.py --in-place <文件>
python scripts/sanitize_json.py --input <输入> --output <输出>
python scripts/sanitize_json.py --check <文件>   # 仅检查不修改
```

### Step 2: 修改 `tag_structure/SKILL.md`

**替换第282-339行**的两个矛盾章节（"JSON 写入最佳实践" + "Python 源文件中文字符串警告"），改为：

```markdown
### JSON 写入规则

**规则1**：使用 Write 工具生成 JSON 文件

**规则2（必须遵守）**：Write 内容中所有中文弯引号使用 Unicode 转义：
- `"` (U+201C) → `\u201c`
- `"` (U+201D) → `\u201d`
示例：`紫花苜蓿被称为\u201c牧草之王\u201d` → json.loads() 正确还原

**规则3**：写入后必须先 sanitize 再 validate

**禁止**：直接使用 `""` 原始字符、编写 Python 脚本生成 JSON、跳过 sanitize
```

**修改第269行自检清单**：弯引号检查改为检查 `\u201c`/`\u201d` 转义

**添加约束**：不使用中文弯引号原始字符

### Step 3-5: 修改 tag_placeholders / tag_images / map_images SKILL.md

在各文件的 Schema 校验章节前，插入 JSON 写入规则引用（与 Step2 相同规则）。

在各文件的自检清单中添加弯引号转义检查项。

### Step 6: 修改 `master_exam_layout/SKILL.md`

- 3处 `sanitize_json.py` 引用命令无需修改（脚本创建后即可执行）
- 在异常场景处理表中新增：`sanitize_json.py 退出码非0 → 停止并报告`

### Step 7: 更新 `修复方案.md`

- 修复项3 标记为 `[已由 v3.0 sanitize_json.py 方案替代]`
- 修复项8 标记为 `[已过时 — 文件不存在]`
- 修复执行顺序中删除 `generate_structure.py`，新增 `sanitize_json.py`

---

## 关键文件清单

| 文件 | 操作 |
|------|------|
| `scripts/sanitize_json.py` | **新建** - 核心修复脚本 |
| `.trae/skills/tag_structure/SKILL.md` | **替换第282-339行**，消除矛盾 |
| `.trae/skills/tag_placeholders/SKILL.md` | **插入** JSON写入规则 |
| `.trae/skills/tag_images/SKILL.md` | **插入** JSON写入规则 |
| `.trae/skills/map_images/SKILL.md` | **插入** JSON写入规则 |
| `.trae/skills/master_exam_layout/SKILL.md` | **新增** 异常场景 |
| `文档/修复方案.md` | **标记** 过时内容 |

## 验证方法

1. 对现有损坏的 `structure.json` 运行 `sanitize_json.py --in-place`，确认修复成功
2. 构造含弯引号的测试 JSON，验证场景A和B都能修复
3. 重跑完整流水线，确认 Step2-5 不再出现弯引号损坏
