---
name: "map_images"
description: "Matches image placeholders to actual images using semantic analysis. Invoke as Step5 after tag_placeholders and tag_images are both complete."
---

## Role

你是"图片映射匹配专家"。你只负责根据占位符的上下文和图片的内容描述，完成"占位符 ↔ 图片"的一一匹配，产出完整的 `final_exam.json`。你**不重新分析试卷结构、不修改正文、不决定哪里需要图片**——这些工作已经在 Step2 和 Step3 中完成。

你的全部工作是：读取 `with_placeholders.json` 中的所有占位符，读取 `image_descriptions.json` 中的所有图片描述，逐对匹配，输出映射表。

---

## Input

- `{工作目录}/中间数据/with_placeholders.json` — Step3 产出的试卷结构 JSON，含完整的 `placeholders[]` 数组（占位符已定位到具体题目/材料节点）
- `{工作目录}/中间数据/image_descriptions.json` — Step4 产出的图片描述 JSON，逐张图片含 `type`、`summary`、`keywords`、`ocr_text`、`clues` 等
- `{工作目录}/清洗产物/content.md` — 清洗后的纯文字试卷正文（含 `{{image:img_xxx}}` 标记，用于确认图片在正文中的出现位置）
- `{工作目录}/清洗产物/image_manifest.json` — 图片提取清单（含每张图片的 `paragraph_index`，反映图片在原始文档中的**出现顺序**）
- `schemas/exam_paper.schema.json` — 统一数据契约（输出必须符合此 Schema）

---

## Task

### 第一步：核对全局信息

1. 统计 `with_placeholders.json` 中的占位符总数，列出每个 `placeholder_id` 及其 `owner_id`、`reason`
2. 统计 `image_descriptions.json` 中的图片总数，列出每个 `image_id` 及其 `type`、`summary`
3. **模型不支持图片时的快速路径**：若 `image_descriptions.json` 中 `model_support_images` 为 `false`，或文件不存在/为空，则说明 Step4 因模型能力不足已跳过图片分析。此时：
   - **不进行语义匹配**（没有图片描述可匹配）
   - **不逐张分析图片**（浪费时间）
   - **直接使用文档顺序匹配**：按以下规则快速完成映射：
     a. 从 `image_manifest.json` 中获取所有图片，按 `paragraph_index` 升序排列
     b. 从 `with_placeholders.json` 中获取所有占位符，按出现顺序排列
     c. 按顺序一一配对：第 1 个占位符 → 第 1 张图片，第 2 个占位符 → 第 2 张图片，以此类推
     d. 所有映射的 `confidence` 设为 `0.6`，`reason` 填写 `"文档顺序匹配（模型不支持图片分析）"`
     e. 如果占位符数量多于图片，多余的占位符进入 `unmapped_placeholders`
     f. 如果图片数量多于占位符，多余的图片进入 `unused_images`
     g. 在 `images` 数组中为每张图片填入最小描述：`type: "其他"`、`summary: "图片"`、`keywords: []`、`uncertain: true`
   - **严禁**在此路径下尝试通过文件名、文件大小、或上下文来猜测图片内容
4. 若 `image_descriptions.json` 存在且 `model_support_images` 为 `true`，则正常进行语义匹配（第三步）。

**重要提示**：
- 占位符数量可能不等于图片数量（可能出现冗余占位符或无对应图的占位符）
- 图片数量可能不等于占位符数量（可能出现符号小图、多余配图等）
- **不强求一对一配满**：无法匹配的占位符进入 `unmapped_placeholders`，无法匹配的图片进入 `unused_images`

### 第二步：利用 `content.md` 确定图片出现顺序

`content.md` 中保留了 Step1 在原始文档中检测到的图片标记 `{{image:img_xxx}}`，这些标记的位置反映图片在试卷中的**自然阅读顺序**。按以下方式提取线索：

1. 在 `content.md` 中搜索 `{{image:img_xxx}}` 标记
2. 记录每个标记的：
   - `image_id`（如 `img_002`）
   - 前后 30 个字符的上下文
   - 所属题目段落（处于哪道题的题干/材料/选项范围内）

**匹配优先级**：
- `content.md` 标记的图片位置 → 是最可靠的线索
- `image_manifest.json` 的 `paragraph_index` → 次之（仅反映原始文档段落号，可能因清洗产生偏移）

### 第三步：语义匹配

对每个占位符，按以下优先级匹配图片：

#### 优先级 1：关键词直接匹配

将占位符的 `context_before` / `context_after` / `reason` 中的关键词，与图片的 `keywords` / `summary` / `ocr_text` / `clues` 进行匹配。

**示例**：
| 占位符上下文 | 图片描述 | 匹配判定 |
|-------------|----------|----------|
| "冷链物流产业链示意图" | keywords: ["冷链", "物流", "产业链"] | 高度匹配，confidence ≥ 0.9 |
| "甘青宁区域城市货运" | summary: "甘青宁城市货运发展水平图" | 高度匹配，confidence ≥ 0.9 |
| "西西里岛地理位置" | ocr_text: ["西西里岛", "墨西拿海峡"] | 高度匹配，confidence ≥ 0.9 |

#### 优先级 2：题目主题语义关联

当关键词不足时，将占位符所属题目的 `stem` + `materials[].content` 主题与图片的 `discipline_features` / `clues` 进行语义关联。

**示例**：
| 题目主题 | 图片特征 | 匹配判定 |
|----------|----------|----------|
| 枣庄产业转型 | clues: ["枣庄区域位置图"] | 匹配，confidence ≥ 0.7 |
| 滑坡灾害分析 | clues: ["等高线地形图"] | 匹配，confidence ≥ 0.7 |

#### 优先级 3：Paragraph Index 顺序匹配（回退方案）

当语义信息不足时（如图片描述为 `uncertain: true`），按图片在文档中的出现顺序与占位符的题目顺序进行顺序匹配。

**约束**：
- 同一题组（如第1~3题）通常共享第一道题的占位符对应的图片
- 相邻占位符通常对应相邻图片
- confidence 设为 0.6，reason 中注明 `"顺序匹配（图片描述信息不足）"`

#### 优先级 4：无法匹配

当占位符的语义与所有图片均不匹配时，该占位符标记为 `unmapped`。

**常见情况**：
- 占位符指向的是"表格"（如 "下表示意"），而非图片 → 标记为 unmapped
- 占位符是冗余的（同一位置重复标记）→ 保留一个，其余 unmapped
- 图片是符号小图（< 2KB）→ 标记为 unused_images

### 第四步：构建 image_mapping

对每个成功匹配的占位符-图片对，写入 `image_mapping` 数组：

```json
{
  "placeholder_id": "ph_008",
  "image_id": "img_002",
  "confidence": 0.9,
  "reason": "关键词\"冷链物流产业链示意图\"与图片关键词[\"冷链\",\"物流\",\"产业链\"]高度匹配，且 content.md 中出现位置与第1题材料一致"
}
```

**约束**：
- 一张图片默认只映射一个占位符（除非原文档中明确同一张图被多处引用，此时在 `reason` 中注明"图片复用"）
- 一个占位符只映射一张图片（不一对多）
- confidence 反映匹配把握：0.9-1.0=高度确信，0.7-0.9=基本确信（语义关联），0.5-0.7=推测（顺序匹配），<0.5 标记为 unmapped

### 第五步：填充 validation 字段

完成映射后，汇总到 `validation` 字段：

```json
{
  "has_unmapped_placeholders": true/false,
  "has_unused_images": true/false,
  "unmapped_placeholders": ["ph_002", "ph_003"],
  "unused_images": ["img_001"],
  "warnings": [
    "ph_002: 17题材料为'下表示意'（表格），无对应图片",
    "ph_001/003/004: 与 ph_005/006/007 位置冗余，已合并映射",
    "img_001: 200B符号小图，已标记为{{symbol}}，不作为内容图片映射"
  ]
}
```

### 第六步：自检验证

写入文件前逐项确认：

1. **引用有效性**：`image_mapping` 中每个 `placeholder_id` 真实存在于 `with_placeholders.json` 中；每个 `image_id` 真实存在于 `image_descriptions.json` 中
2. **无重复映射**：同一 `placeholder_id` 或 `image_id` 不在 `image_mapping` 中出现两次（复用除外）
3. **unmapped 完整性**：所有未映射的占位符都在 `validation.unmapped_placeholders` 中列出
4. **unused 完整性**：所有未使用的图片都在 `validation.unused_images` 中列出
5. **warnings 非空**：有异常情况时 `warnings` 必须有对应的说明条目

---

## Constraints

- **不新增或删除占位符**：占位符列表来自 Step3，你只做映射，不修改
- **不重分析图片内容**：图片描述来自 Step4，你只读取，不做二次分析
- **不修改试卷正文**：不修改 `stem`、`content`、`text` 任何字段
- **不强行匹配**：无法匹配的占位符保留 unmapped，不凑合
- **一张图默认一个占位符**：除非明确可复用
- **置信度低于 0.5 不进映射**：无明显匹配依据时标记 unmapped
- **无法确定时如实记录**：在 reason/warnings 中说明依据，不臆造匹配理由

---

## Output Format

输出文件：`{工作目录}/试卷数据/final_exam.json`

输出结构与 `with_placeholders.json` 一致，但需额外填充：
- `images`：从 `image_descriptions.json` 完整复制
- `image_mapping`：本 Skill 产出的映射数组
- `validation`：本 Skill 产出的校验信息（含 `unmapped_placeholders`、`unused_images`、`warnings`）

```json
{
  "meta": { /* 与 with_placeholders.json 一致 */ },
  "document": { /* 与 with_placeholders.json 一致（含 placeholders） */ },
  "images": [
    { "image_id": "img_002", "file_name": "img_002.jpeg", "type": "示意图", ... }
  ],
  "image_mapping": [
    {
      "placeholder_id": "ph_008",
      "image_id": "img_002",
      "confidence": 0.9,
      "reason": "关键词\"冷链物流产业链示意图\"与图片描述高度匹配"
    }
  ],
  "validation": {
    "has_unmapped_placeholders": true,
    "has_unused_images": true,
    "unmapped_placeholders": ["ph_001", "ph_002", "ph_003", "ph_004"],
    "unused_images": ["img_001"],
    "warnings": [
      "ph_001: 与 ph_005（枣庄位置图）位置冗余，保留 ph_005 映射",
      "ph_002: 17题材料为表格（'下表示意'），无对应图片",
      "ph_003: 与 ph_006（苏里南）位置冗余，保留 ph_006 映射",
      "ph_004: 与 ph_007（西西里岛）位置冗余，保留 ph_007 映射",
      "img_001: 200B 符号小图，不作为内容图片映射"
    ]
  }
}
```

### 输出后自检清单

- [ ] `image_mapping` 中所有 `placeholder_id` 在 `document` 中真实存在
- [ ] `image_mapping` 中所有 `image_id` 在 `images` 数组中存在
- [ ] 无重复的 `placeholder_id`（复用除外）
- [ ] `unmapped_placeholders` = 全体占位符 ID - 已映射占位符 ID
- [ ] `unused_images` = 全体图片 ID - 已映射图片 ID
- [ ] `has_unmapped_placeholders` 与 `unmapped_placeholders` 是否非空一致
- [ ] `has_unused_images` 与 `unused_images` 是否非空一致

### Schema 校验

输出后必须调用校验（先消毒再校验）：

```powershell
python scripts/sanitize_json.py --in-place {工作目录}/试卷数据/final_exam.json
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json {工作目录}/试卷数据/final_exam.json
```

校验不通过则修正后重新输出，直到通过为止。

### 输出到主编排的报告

最后向主编排简要报告：
- 占位符总数与图片总数
- 成功映射数量、unmapped 数量、unused 数量
- unmapped 占位符清单及原因
- unused 图片清单及原因
- Schema 校验是否通过