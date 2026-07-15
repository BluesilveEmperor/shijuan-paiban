---
name: "tag_placeholders_anchor"
description: "Create image placeholders only for anchor/floating images in the exam structure. Uses anchor image analysis results to determine correct positions. Does NOT create placeholders for inline images."
---

# Step3: tag_placeholders_anchor — anchor 浮动图占位（增量编辑模式）

## Role

你负责**仅对浮动图片**（`original_type == "anchor"`）在试卷结构中标注插入位置。inline 内嵌图片的位置已由代码在 Step1 自动确定（`{{image:img_xxx}}`），你不需要处理。

**v3.6 核心变更**：禁止全量输出 `with_placeholders.json`。你必须先用 `cp`/`copy` 复制 `structure.json` → `with_placeholders.json`，然后使用 **Edit 工具逐占位符增量修改**该文件。不允许使用 Write 工具重写整个 JSON。

---

## Input

| 文件 | 说明 |
|------|------|
| `{工作目录}/中间数据/structure.json` | Step2 产物，试卷结构（含 inline 图片的 `{{image:img_xxx}}` 标记） |
| `{工作目录}/中间数据/anchor_descriptions.json` | Step4 产物，anchor 图的内容分析（含 `position_hint`） |
| `{工作目录}/清洗产物/content.md` | 清洗后的试卷全文 |
| `{工作目录}/清洗产物/image_manifest.json` | 图片清单，用于确认 anchor 图数量 |
| `schemas/exam_paper.schema.json` | 统一数据契约 |

---

## Task

### 1. 确认 anchor 图数量

从 `image_manifest.json` 统计 `original_type == "anchor"` 的图片数量。如果为 0，跳过此步骤，不生成占位符。

### 2. 阅读试卷全文

仔细阅读 `content.md`，理解每道题的语义：
- 题干在问什么
- 材料提供了什么信息
- 图片应该放在材料的什么位置

### 3. 为每张 anchor 图确定位置

结合 `anchor_descriptions.json` 中的以下信息：
- `keywords`：图片中的地理关键词
- `position_hint`：AI 对图片位置的初步判断
- `anchor_context`：原始锚点段落的文本

逐张判断每张 anchor 图应该插入到哪道题、哪个位置。

### 4. 创建占位符

在 `structure.json` 的对应位置插入占位符 `{{image:ph_anchor_XXX}}`，并创建对应的 `placeholder` 对象。

**占位符格式**：
```json
{
  "placeholder_id": "ph_anchor_001",
  "token": "{{image:ph_anchor_001}}",
  "location_type": "material",
  "owner_id": "question_003",
  "context_before": "四大地理区域分布如下图所示",
  "context_after": "下列关于北方地区的说法",
  "reason": "材料明确提到'如下图所示'，anchor_descriptions 中该图关键词'四大地理区域'与材料吻合，position_hint 也指向此位置",
  "_source": "anchor",
  "_ai_reason": "锚点段落（段落12）内容与图片无关，已根据图片内容+材料语义重新定位到第3题"
}
```

**location_type 枚举**：
- `material`：图片属于题目材料
- `question_stem`：图片在题干中
- `subquestion`：图片在小问中
- `option`：图片在选项中

**重要约束**：
- 每个占位符必须标记 `_source: "anchor"`（这是 v3.5 双轨分流的关键标识）
- 每个占位符必须有 `_ai_reason`（记录 AI 的判断依据，用于后续排查）
- 允许一道题有多个占位符（一段材料可以有多张图）

### 5. 无法确定时的处理

如果无法确定某张 anchor 图应该放在哪里：
- 设置 `uncertain: true`
- 在 `notes` 中说明无法确定的原因
- 仍创建占位符，但放在最可能的默认位置（如对应题组的第一道题）

---

## Output（增量编辑模式）

### 第零步：复制基础文件

先用 shell 命令复制 `structure.json` 作为工作副本：

```powershell
copy {工作目录}/中间数据/structure.json {工作目录}/中间数据/with_placeholders.json
```

### 第一步：逐占位符 Edit 修改

对每张 anchor 图，使用 **Edit 工具**在 `with_placeholders.json` 中：

1. **添加 placeholder 到题目的 `placeholders` 数组**：
   - SEARCH: 目标题目的 `"placeholders": []`
   - REPLACE: `"placeholders": [{ ...占位符对象... }]`
   
2. **在材料 content 中插入 token**：
   - SEARCH: 材料 content 中的目标位置文本
   - REPLACE: 在适当位置插入 `{{image:ph_anchor_XXX}}`

**每次 Edit 只修改一个占位符**，避免大范围替换导致 JSON 损坏。

### 第二步：校验

每次 Edit 后立即运行校验确保 JSON 仍然有效：

```powershell
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json {工作目录}/中间数据/with_placeholders.json
```

### 第三步：消毒

所有占位符添加完成后，运行消毒：

```powershell
python scripts/sanitize_json.py --in-place {工作目录}/中间数据/with_placeholders.json
```

### 占位符格式

每个占位符对象格式如下：

```json
{
  "placeholder_id": "ph_anchor_001",
  "token": "{{image:ph_anchor_001}}",
  "location_type": "material",
  "owner_id": "question_003",
  "context_before": "我国的四大地理区域划分",
  "context_after": "如下图所示",
  "reason": "材料提到'如下图'，图片为四大地理区域分布图",
  "_source": "anchor",
  "_ai_reason": "图片与第3题材料语义吻合，锚点已修正"
}
```

**重要**：输出仅含 anchor 图的占位符。inline 图的占位符已在 `structure.json` 的文本中（`{{image:img_xxx}}`），无需处理。

---

## Constraints

### 强制约束（v3.6 新增，违反即失败）

1. ❌ **禁止使用 Write 工具输出完整的 with_placeholders.json**：你必须先用 shell 复制 structure.json，然后仅用 Edit 工具修改
2. ❌ **禁止全文重写**：每次 Edit 只修改一个占位符对应的数组元素，不改动文件其他部分
3. ✅ **必须先复制再编辑**：`copy structure.json with_placeholders.json` 是第一步操作
4. ✅ **每次 Edit 后必须校验**：`python scripts/validate_json.py` 确保 JSON 仍然合法

### 业务约束

5. ❌ **不为 inline 图创建占位符**：`{{image:img_xxx}}` 已由代码在 Step1 生成
6. ❌ **不修改 inline 图占位符**：`structure.json` 中的 `{{image:img_xxx}}` 标记保持不变
7. ✅ **每个占位符必须有 `_source: "anchor"`**
8. ✅ **每个占位符必须有 `_ai_reason`**
9. ✅ **允许一道题有多个占位符**
10. ✅ **结合 `anchor_descriptions.json` 的 `position_hint` 辅助判断**

---

## Self-check

- [ ] 是否先用 `copy` 命令复制了 `structure.json` → `with_placeholders.json`？
- [ ] 是否每次只 Edit 一个占位符（没有一次修改多个占位符）？
- [ ] 是否每次 Edit 后都运行了 `validate_json.py` 校验？
- [ ] 是否全程没有使用 Write 工具？
- [ ] 是否只创建了 anchor 图的占位符（不包含 inline 图）？
- [ ] 占位符数量是否与 `image_manifest.json` 中 anchor 图数量一致？
- [ ] 每个占位符是否有 `_source: "anchor"` 和 `_ai_reason`？
- [ ] 是否结合了 `anchor_descriptions.json` 的 `position_hint`？
- [ ] 是否有重复的 `placeholder_id`？
