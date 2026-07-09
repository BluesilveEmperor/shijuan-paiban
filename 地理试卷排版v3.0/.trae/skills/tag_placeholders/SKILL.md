---
name: "tag_placeholders"
description: "Annotates where images are needed in structured exam JSON using placeholders. Invoke as Step3 after tag_structure."
---

## Role
你是"图片占位标注专家"。你只负责在已有结构化的试卷 JSON 中标注需要图片的位置，输出占位符，不做图片匹配。

你不读取图片文件、不分析图片内容、不建立占位符与图片的映射。你的全部工作就是：逐题审读题干/材料/选项/子问题，判断哪些位置需要图片，插入带唯一 ID 的占位符。

## Input
- `{工作目录}/中间数据/structure.json` — Step2 产出的试卷结构 JSON（`placeholders` 字段均为空数组 `[]`）
- `{工作目录}/清洗产物/content.md` — 清洗后的纯文字试卷正文（用于获取完整上下文，含 `<sup>`/`<sub>` 和 `{{image:img_xxx}}` 标记）
- `{工作目录}/清洗产物/image_manifest.json` — 图片清单（了解有多少张可用图片及其提取来源）
- `schemas/exam_paper.schema.json` — 统一数据契约（输出必须符合此 Schema）

## Task

基于 `structure.json` 增量标注图片占位符，输出 `with_placeholders.json`。

**核心原则：复制+增量修改，不重写整个文件。** `with_placeholders.json` 与 `structure.json` 的唯一区别是部分 `placeholders` 数组被填充、部分 `stem`/`content` 中嵌入了 `{{image:ph_xxx}}` 标记。通过复制原文件再增量编辑，避免重新输出整个 JSON，大幅减少 token 消耗。

### 第零步：复制文件

在开始任何分析之前，先将 `structure.json` 复制为 `with_placeholders.json`：

```powershell
copy "{工作目录}\中间数据\structure.json" "{工作目录}\中间数据\with_placeholders.json"
```

后续所有修改都在 `with_placeholders.json` 上用 **Edit 工具** 增量进行，**不再使用 Write 工具重写整个文件**。

### 第一步：掌握全局上下文

首先做以下三项工作：

**1. 通读 `content.md`**

获取每道题完整上下文。特别注意 Step1 留下的 `{{image:img_xxx}}` 标记——这些标记告诉你此处原本有一张图片（已被提取），**正是需要创建占位符的位置**。

`content.md` 中的关键标记：

| 标记 | 含义 | 你的操作 |
|------|------|----------|
| `{{image:img_xxx}}` | Step1 在此检测到一张内容图片 | **必须**为该位置创建占位符 |
| `{{symbol:img_xxx}}` | Step1 在此检测到一张小图（疑似符号） | 酌情处理：若上下文判断确需插图则创建占位符，否则忽略（Step2 已处理符号推断） |

**2. 查看 `image_manifest.json`**

了解可用图片数量、文件名、提取来源：

```json
{
  "total_images": 3,
  "images": [
    {"id": "img_001", "file_name": "image1.png", ...},
    {"id": "img_002", "file_name": "image2.png", ...}
  ]
}
```

注意：你**不为每张图片创建一个占位符**。你只为**正文中需要图片的位置**创建占位符。图片数量与占位符数量不一定相等。

**3. 通读 `structure.json`**

掌握试卷整体结构：有哪些分区、每道题的内容、材料、选项、子问题。

### 第二步：逐题排查需要图片的位置

对 `structure.json` 中每道题，按以下优先级排查：

#### 优先级 1：正文明确提到"如图"

**触发词**（任一个即触发）：
- "如图" / "图X" / "图X所示" / "图X中"
- "下图" / "上图" / "右图" / "左图"
- "示意图"（紧邻题干时）
- "读图" / "据图" / "看图"
- "图中" / "图示"

**判定位置**：
- 若触发词在 `stem`（题干）中 → `location_type: "question_stem"`，`owner_id` 为 `question.id`
- 若触发词在 `materials[].content` 中 → `location_type: "material"`，`owner_id` 为 `material.id`
- 若触发词在 `subquestions[].stem` 中 → `location_type: "subquestion"`，`owner_id` 为 `subq.id`
- 若触发词在 `options[].text` 中 → `location_type: "option"`，`owner_id` 为 `question.id`

**示例**：
```
题干: "图1为某区域等高线地形图，据此回答1~2题。"
→ 创建占位符，location_type: "question_stem"，owner_id: "question_001"
```

#### 优先级 2：材料题引导语

**触发词**：
- "阅读图文材料"
- "读图文材料"
- 材料内容包含"如材料图"等

**判定**：在对应 `material` 节点创建占位符，`location_type: "material"`。

#### 优先级 3：`content.md` 中有 `{{image:img_xxx}}` 标记

此标记由 Step1 的 `docx_to_markdown()` 在检测到原文档中的图片时自动生成。这些位置**必须**创建占位符。

**定位方法**：
1. 在 `content.md` 中找到 `{{image:img_xxx}}` 标记
2. 读取标记前后的上下文（前后各 30 字）
3. 在 `structure.json` 中找到包含此上下文的节点（题干/材料/选项/子问题）
4. 在该节点的 `placeholders` 数组中创建占位符

**注意**：`content.md` 中可能有 `{{image:img_xxx}}` 标记，但 `structure.json` 的 `stem` 字段中**不含**此标记（Step2 已将其移除或忽略）。你需要通过上下文匹配来定位。

#### 优先级 4：地理学科天然需要插图的场景

即使正文没有明确说"如图"，以下场景通常需要图片：

| 场景 | 判断依据 | 示例 |
|------|----------|------|
| 等值线判读 | 题干含"等高线"、"等温线"、"等压线"、"等降水量线"等 | "该区域等高线密集处表示..." |
| 区域定位 | 题干含具体地名 + 地理特征描述 | "M国位于非洲西部，南临几内亚湾..." |
| 气候/洋流 | 题干讨论气候特征、洋流方向 | "受洋流影响，沿岸气候..." |
| 示意图引用 | 题干含"示意图"、"模式图"、"剖面图" | "读水循环示意图，回答..." |
| 景观判断 | 题干含景观描述（植被、地貌、建筑） | "该地区典型的植被类型是..." |

**处理**：若满足以上场景但未找到"如图"触发词，在 `reason` 中详细说明判断依据。`uncertain` 标记为 `true`。

#### 优先级 5：选项含图片标记

若 `content.md` 中某选项文字旁有 `{{image:img_xxx}}` 标记，说明该选项本身是图片。

**处理**：创建占位符，`location_type: "option"`。

### 第三步：为每个占位符生成完整信息并增量写入

逐题排查完成后，对每个需要图片的位置，用 **Edit 工具** 在 `with_placeholders.json` 上做两类修改：

**修改类型 A：在正文（stem/content）中嵌入 `{{image:ph_xxx}}` 标记**

使用 Edit 工具，将标记插入到正文的准确位置。例如：

```
原文本: "下图示意1960~2015年东京都市圈人口净迁入率变化。"
修改为: "下图示意1960~2015年东京都市圈人口净迁入率变化。{{image:ph_001}}"
```

**修改类型 B：填充 placeholders 数组**

将空数组 `"placeholders": []` 替换为包含占位符对象的数组。例如：

```
"placeholders": []
→
"placeholders": [
  {
    "placeholder_id": "ph_001",
    "token": "{{image:ph_001}}",
    "location_type": "material",
    "owner_id": "material_001",
    "context_before": "下图示意1960~2015年",
    "context_after": "东京都市圈人口净迁入率变化",
    "reason": "材料中提到'下图示意'，需要插入对应图片",
    "uncertain": false
  }
]
```

**关键要求**：
- 每次只修改一个题目的相关字段，避免 Edit 的 `old_string` 不唯一
- 先嵌入正文标记（修改类型 A），再填充 placeholders 数组（修改类型 B）
- 不修改任何其他字段（meta、options、subquestions 结构等保持原样）

每个占位符必须包含以下全部字段：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `placeholder_id` | string | 全局唯一 ID，格式 `ph_001`、`ph_002`... | `"ph_001"` |
| `token` | string | 占位符标记文本，格式 `{{image:ph_xxx}}` | `"{{image:ph_001}}"` |
| `location_type` | string | 枚举：`title` / `material` / `question_stem` / `subquestion` / `option` | `"question_stem"` |
| `owner_id` | string | 占位符所属节点的 ID（`question.id` / `material.id` / `subq.id`） | `"question_001"` |
| `context_before` | string | 占位符前文（截取前 20 字以内） | `"图1为某区域等高线"` |
| `context_after` | string | 占位符后文（截取后 20 字以内） | `"，据此回答1~2题"` |
| `reason` | string | 插入占位符的依据 | `"题干明确提到'图1'，需要插入等高线地形图"` |
| `uncertain` | boolean | 是否为不确定判断（默认 `false`，不确定时 `true`） | `false` |

### 第四步：自检验证

写完所有占位符后，执行以下自检：

1. **ID 唯一性**：所有 `placeholder_id` 不重复（`ph_001`、`ph_002`...）
2. **owner 有效性**：每个 `placeholder_id` 的 `owner_id` 必须在 `structure.json` 中存在（匹配到实际的 `question.id` / `material.id` / `subq.id`）
3. **token 一致性**：`token` 必须为 `{{image:placeholder_id}}` 格式（如 `placeholder_id` 为 `ph_001`，则 `token` 为 `{{image:ph_001}}`）
4. **content.md 标记全覆盖**：`content.md` 中每个 `{{image:img_xxx}}` 标记都应找到对应占位符（除非确认为无关标记）
5. **无冗余**：不在"如图"以外的、无明确依据的位置创建占位符
6. **reason 非空**：每个占位符的 `reason` 字段有实质内容，不空不敷衍

## Constraints

- **不读取图片文件**：不访问 `{工作目录}/清洗产物/images/` 目录中的实际图片，不分析图片内容
- **不创建图片映射**：`image_mapping` 保持 `[]`，映射是 Step5 的工作
- **不分析图片类型**：不猜测图片是地图还是图表，不填写图片的 `type`/`summary`/`keywords`
- **不修改题目结构**：不新增或删除 `questions`/`sections`/`materials`/`subquestions`，只填充 `placeholders` 数组
- **内嵌图片标记到正文中**：对于 `location_type` 为 `material`、`question_stem`、`subquestion` 的占位符，**必须**将 `{{image:ph_xxx}}` 标记嵌入到对应正文的**准确位置**（即图片原本所在的位置），而不是末尾。`placeholders` 数组同时保留作为追踪记录。排版脚本（Step6）依赖此标记来定位图片插入位置。
- **不修改正文原文**：在正文中嵌入 `{{image:xxx}}` 标记是元数据操作，不改变原文内容本身
- **无依据不插图**：只有当满足第三步判定条件时才创建占位符，不在没有明确线索处随意插入
- **不重复占位**：一处位置只创建一个占位符
- **不强制凑满图片数**：占位符数量不必等于 `image_manifest.json` 中的图片数量
- **不确定时标记 uncertain**：无法 100% 确定某处需要图片时，仍然创建占位符，但 `uncertain: true` + `reason` 说明推断依据

### 特殊说明

`{{symbol:img_xxx}}` 标记表示 Step1 在此检测到一张小图片（< 2KB，可能是符号而非内容图）。Step2 已尝试推断其含义。你在 Step3 中：
- 若 Step2 已推断为符号（如 `°`、`′`、`″`），则**不创建占位符**
- 若 Step2 未推断且上下文判断确需插图，则创建占位符，`uncertain: true`

## Output Format

输出文件：`{工作目录}/中间数据/with_placeholders.json`

此文件由第零步复制 `structure.json` 得来，与原文件的区别**仅有**：

1. 部分题目的 `"placeholders": []` 被替换为包含占位符对象的数组
2. 部分题目的 `stem` 或材料的 `content` 中嵌入了 `{{image:ph_xxx}}` 标记
3. 其余所有字段（meta、sections 结构、options、subquestions、images、image_mapping、validation）保持原样不变

**禁止使用 Write 工具重写整个文件。** 只使用 Edit 工具对上述两个字段做增量修改。

### 修改示例

假设 `structure.json` 中 question_001 的材料提到"下图示意"：

**修改类型 A（嵌入正文标记）**：
```json
// 修改前（material_001 的 content）:
"content": "东京都市圈包含1市3县...下图示意1960~2015年东京都市圈人口净迁入率变化。"

// 修改后:
"content": "东京都市圈包含1市3县...下图示意1960~2015年东京都市圈人口净迁入率变化。{{image:ph_001}}"
```

**修改类型 B（填充 placeholders 数组）**：
```json
// 修改前:
"placeholders": []

// 修改后:
"placeholders": [
  {
    "placeholder_id": "ph_001",
    "token": "{{image:ph_001}}",
    "location_type": "material",
    "owner_id": "material_001",
    "context_before": "下图示意1960~2015年",
    "context_after": "东京都市圈人口净迁入率变化",
    "reason": "材料中提到'下图示意'，需要插入对应图片",
    "uncertain": false
  }
]
```

### 输出后自检清单

在完成所有编辑后逐项确认：

- [ ] **使用了 Edit 工具增量修改**，而非 Write 工具重写整个文件
- [ ] 所有 `placeholder_id` 全局唯一（无重复 `ph_xxx`）
- [ ] 每个 `token` 与对应的 `placeholder_id` 一致（`{{image:ph_xxx}}` 中 `ph_xxx` 等于 `placeholder_id`）
- [ ] 每个 `owner_id` 在 `structure.json` 中真实存在
- [ ] **占位符标记已内嵌**：检查每个 `location_type` 为 `material`/`question_stem`/`subquestion` 的占位符，确认对应的 `content`/`stem` 字段中已包含 `{{image:ph_xxx}}` 标记
- [ ] **标记位置准确**：确认标记位于正确位置（如"下图为..."之后、"（如下图）"之后），而非随意添加到末尾
- [ ] `content.md` 中每个 `{{image:img_xxx}}` 标记都已找到对应占位符
- [ ] `location_type` 全部来自枚举值：`title` / `material` / `question_stem` / `subquestion` / `option`
- [ ] 每个占位符 `reason` 非空且有实质内容
- [ ] 未修改 `structure.json` 原有的任何字段值（只填充了 `placeholders` 和嵌入标记）
- [ ] `images` 字段保持 `[]`
- [ ] `image_mapping` 字段保持 `[]`

### Schema 校验

输出后必须调用校验（先消毒再校验）：

```powershell
python scripts/sanitize_json.py --in-place {工作目录}/中间数据/with_placeholders.json
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json {工作目录}/中间数据/with_placeholders.json
```

校验不通过则修正后重新输出，直到通过为止。

### 输出到主编排的报告

最后向主编排简要报告：
- 创建占位符总数
- 各 `location_type` 的数量分布
- 是否有 `uncertain: true` 的占位符及其 `placeholder_id`
- Schema 校验是否通过
