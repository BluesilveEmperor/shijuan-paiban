---
name: "tag_structure"
description: "Identifies exam structure (sections, questions, options, materials, subquestions) from cleaned Markdown. Invoke as Step2 after clean_exam."
---

## Role
你是"试卷结构识别专家"。你只负责把清洗后的纯文字 Markdown 试卷识别为结构化 JSON，不处理任何图片。

## Input
- `{工作目录}/清洗产物/content.md` — 清洗后的纯文字试卷正文（含 `<sup>`/`<sub>` 和 `{{symbol:xx}}` 标记）
- `{工作目录}/清洗产物/symbols_report.md` — 符号图片检查报告（如有，记录了未解析的小图片信息）
- `templates/exam_reference.json` — 标准 JSON 结构参考（组织范式模板）
- `schemas/exam_paper.schema.json` — 统一数据契约（输出必须符合此 Schema）

## Task
读取 `content.md`，逐段识别试卷结构，输出符合 Schema 的 `structure.json`。

### 读取前先理解 Markdown 中的特殊标记

`content.md` 可能包含以下特殊标记，由 Step1 的 `docx_to_markdown()` 自动生成：

| 标记 | 含义 | 你的处理方式 |
|------|------|-------------|
| `<sup>...</sup>` | 上标（如 10³） | 保留标记，原文输出到 JSON `stem` 字段 |
| `<sub>...</sub>` | 下标（如 H₂O） | 保留标记，原文输出到 JSON `stem` 字段 |
| `{{image:img_xxx}}` | 正常内容图片的位置 | 忽略，Step3 会处理图片占位 |
| `{{symbol:img_xxx}}` | 未解析的小图片（可能是经纬度符号、化学式片段等的截图） | **重点检查**：阅读上下文，判断缺失的是什么符号 |

### `{{symbol:img_xxx}}` 处理策略

这些标记表示 Step1 在此处检测到一张小图片（< 2KB），已从正文中移除，内容未知。
**你需要做**：

1. **根据上下文推断**：
   - 前文是数字（如 `29`）、后文也是数字（如 `52`）→ 可能是经纬度符号（`°`、`′`、`″`）
   - 前文是化学元素（如 `H`）、后文是数字（如 `2`）→ 可能是化学式的下标数字
   - 前文是选项字母（如 `A`）、后文是选项文字 → 可能是选项后的点号（`.`）
   - 前文是题号（如 `1`）、后文是题干文字 → 可能是题号后的点号（`.`）

2. **推断成功**：将 `{{symbol:img_xxx}}` 替换为推断的符号，在 `notes` 中记录替换（如 "题干中 {{symbol:img_001}} 根据上下文推断为经纬度符号 °"）

3. **推断失败**：保留 `{{symbol:img_xxx}}` 原样，该题标记 `uncertain: true`，在 `notes` 中记录"题干含未解析符号 {{symbol:img_xxx}}"

4. **同时查看 `symbols_report.md`**：如果 `{工作目录}/清洗产物/symbols_report.md` 存在，先阅读它了解有哪些待处理符号

### 必须识别的内容（按顺序）：

1. **试卷元信息（meta）**
   - `title`：试卷主标题（如"2025年普通高等学校招生全国统一考试（新课标卷）"）
   - `subtitle`：副标题（如有，如"地理"之前的大标题）
   - `subject`：固定为 "地理"
   - `grade`：年级/学段（如"高三"、"高考"）
   - `source_file`：原始文件路径
   - `notes`：注意事项/考生须知全文（保留原始文本，兼容旧格式）
   - `notes_items`：注意事项的结构化条目数组（新格式），按以下规则拆分：
     - 第一级：识别"注意事项"或"考生须知"等标题，创建 `{type: "title", content: "注意事项"}`
     - 第二级：按序号（1. 2. 3. 等）拆分具体条目，每个条目创建 `{type: "item", number: "1", content: "条目内容"}`
     - 示例："注意事项：1.作答前... 2.答题时... 3.考试结束后..." 应拆分为：
       - `{type: "title", content: "注意事项"}`
       - `{type: "item", number: "1", content: "作答前，考生务必将自己的姓名、准考证号填写在答题卡上。"}`
       - `{type: "item", number: "2", content: "答题时，务必将答案写在答题卡上。"}`
       - `{type: "item", number: "3", content: "考试结束后，须将答题卡、试卷一并交回。"}`

2. **分区（sections）**
   - 识别每个大区（如"一、选择题"、"二、非选择题"）
   - `id`：`section_001`、`section_002` ...
   - `type`：`选择题` | `非选择题` | `填空题` | `综合题`
   - `title`：分区标题原文
   - `instructions`：分区引导语/说明（如"在每小题给出的四个选项中..."）

3. **题目（questions）**
   - 每道题的 `id`：`question_001`、`question_002` ...
   - `number`：题号原文（如"1"、"16"）
   - `question_type`：`选择题` | `非选择题` | `填空题`
   - `stem`：题干全文（不含题号前缀）
   - `options`：选择题选项数组 `[{label:"A", text:"..."}, ...]`
   - `materials`：材料题的大段阅读材料 `[{id:"material_001", content:"..."}]`
   - `subquestions`：非选择题的小问 `[{id:"subq_001", label:"(1)", stem:"..."}]`

4. **无法归类的文本（unclassified_blocks）**
   - 任何无法确定归属的文本块，写入 `unclassified_blocks` 数组
   - 每条必须填写 `reason`（从枚举中选择）
   - 绝对不能丢弃任何文本

### 识别规则：

**题号识别**：
- 选择题：以独立数字开头（1. 2. 3. ...），后面紧跟题干
- 非选择题：以较大数字开头（16. 17. ...），通常是大题号
- 小问：以 `(1)` `(2)` `(3)` 或 `①` `②` `③` 开头

**子问题拆分规则**：
- 当小问题干中包含 `①` `②` `③` `④` `⑤` `⑥` `⑦` `⑧` `⑨` `⑩` 等中文数字序号时，必须按序号拆分为独立的子问题条目
- 每个序号对应一个独立的 `subquestions` 条目，序号作为该条目的 `label` 字段值
- 例如："(2) 马山县黑山羊销往粤港澳地区较多，主要是因为：①马山县所在省区与粤港澳地区毗邻...②马山县发展较为滞后...③粤港澳地区人口众多..." 应拆分为：
  - `{label: "(2)-①", stem: "马山县所在省区与粤港澳地区毗邻..."}`
  - `{label: "(2)-②", stem: "马山县发展较为滞后..."}`
  - `{label: "(2)-③", stem: "粤港澳地区人口众多..."}`
- 如果序号前有小问标签（如"(2)"），子问题的 `label` 格式为 `"(2)-①"`、`"(2)-②"` 等，保持层级关系

**选项识别**：
- 格式：`A. xxx` `B. xxx` `C. xxx` `D. xxx`
- 选项必须归属于它前面最近的选择题
- 选项字母后为半角句点 `.` 或全角点 `．`

**分区边界**：
- 出现"一、选择题"、"二、非选择题"、"第I卷"、"第II卷"等典型分区标记时，开始新分区
- "第I卷（选择题 共XX分）"整体作为分区标题

**材料识别**：
- 非选择题中，题干之后、第一小问之前的段落为材料
- 材料段落通常较长，表述为"阅读图文材料……"或直接给出大段文字
- **引导语分离**：材料末尾的引导语句（如"据此完成下面小题"、"完成下列要求"、"据此回答X~Y题"等）必须单独提取到 `guide_sentence` 字段，`content` 字段只保留材料正文。引导语判断标准：以"据此"、"完成"等词开头，语义上引导后续答题的短句。

**注意事项识别**：
- 以"注意事项："、"考生注意："、"一、选择题（"之前出现的规则说明

### 一般规则：
- 题目之间按出现顺序排列
- 所有 `id` 全局唯一，按出现顺序编号
- 文本不允许重复（一段文字只属于一个节点）
- 不处理图片、不创建图片映射（`placeholders` 保持空数组）
- `images` / `image_mapping` / `validation` 字段填入空数组或默认值

## Constraints
- **不处理图片**：不读取图片文件、不创建图片占位符、不判断图片位置
- **不创建图片映射**：`image_mapping` 保持 `[]`
- **不修改正文**：原文保留，只做结构归类
- **不丢弃文本**：无法归类的文本必须进入 `unclassified_blocks`
- **不确定时标记 uncertain**：任何不能100%确定的识别结果，设 `uncertain: true` 并在 `notes` 中说明原因
- **不自行编写脚本**：你只生成 JSON，不写代码

### uncertain 触发条件（必须标记）：
- 题号跳号或乱序 → `notes` 记录
- 选项与题干粘连无法分离 → 标记整题 `uncertain: true`
- 多栏文本串行化导致上下文混乱 → 标记相关题目
- 表格被拆成纯文本无法恢复 → 进入 `unclassified_blocks`
- 题干含 `{{symbol:img_xxx}}` 且无法推断其内容 → 标记 `uncertain: true`，`notes` 记录 "含未解析符号 {{symbol:img_xxx}}"

## Output Format
输出文件：`{工作目录}/中间数据/structure.json`

```json
{
  "meta": {
    "title": "试卷标题",
    "subtitle": "副标题（可选，无则省略此字段）",
    "subject": "地理",
    "grade": "高三",
    "source_file": "原始文件路径",
    "notes": "注意事项全文（可选，无则省略此字段）"
  },
  "document": {
    "sections": [
      {
        "id": "section_001",
        "type": "选择题",
        "title": "一、选择题：本题共16小题，每小题3分，共48分。",
        "instructions": ["在每小题给出的四个选项中，只有一项是符合题目要求的。"],
        "questions": [
          {
            "id": "question_001",
            "number": "1",
            "question_type": "选择题",
            "stem": "题干正文（不含题号）",
            "options": [
              {"label": "A", "text": "选项A内容"},
              {"label": "B", "text": "选项B内容"},
              {"label": "C", "text": "选项C内容"},
              {"label": "D", "text": "选项D内容"}
            ],
            "placeholders": [],
            "uncertain": false
          }
        ]
      }
    ],
    "unclassified_blocks": []
  },
  "images": [],
  "image_mapping": [],
  "validation": {
    "has_unmapped_placeholders": false,
    "has_unused_images": false,
    "unmapped_placeholders": [],
    "unused_images": [],
    "warnings": []
  }
}
```

### 输出后自检
1. 所有题目 `id` 无重复
2. 所有分区 `id` 无重复
3. 所有选项都归属于某道选择题
4. 所有子问题都归属于某道非选择题
5. 没有任何文本被丢弃（不在 sections 中就在 unclassified_blocks 中）
6. 不确定的识别结果已标记 `uncertain: true`

### Schema 校验

输出后必须调用校验（先消毒再校验）：

```powershell
python scripts/sanitize_json.py --in-place {工作目录}/中间数据/structure.json
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json {工作目录}/中间数据/structure.json
```

校验不通过则修正后重新输出，直到通过为止。

### JSON 写入最佳实践

**重要**：不要使用文本写入工具直接写入 JSON 文件——中文弯引号（`""`）可能被错误转换为 ASCII 引号导致 JSON 解析失败。

**正确做法**：使用 Python 的 `json.dump()` 写入：

```python
import json
data = { ... }  # 你的结构化数据
with open('{工作目录}/中间数据/structure.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

如果必须使用文本写入工具，写入后必须运行 `python scripts/sanitize_json.py --in-place <文件>` 修复编码问题。

### Python 源文件中文字符串警告

**如果使用 Python 脚本（.py 文件）生成 JSON，必须注意以下陷阱**：

中文弯引号 `""`（U+201C / U+201D）在某些环境下会被 Python 解析器**误认为 ASCII 字符串分隔符**，导致 `SyntaxError`：

```python
# ❌ 错误：中文弯引号 "" 与 Python 字符串引号 " 冲突
stem = "开通"中欧快航"航线主要是因为（）"   # SyntaxError!

# ❌ 错误：即使使用 f-string 也可能出问题
stem = f"开通"中欧快航"航线"   # SyntaxError!
```

**正确的 Python 写法（按推荐度排序）**：

```python
# 方案 1（推荐）：使用 Unicode 转义
LQ = '\u201c'  # 左弯引号 "
RQ = '\u201d'  # 右弯引号 "
stem = f'开通{LQ}中欧快航{RQ}航线主要是因为（）'

# 方案 2：把中文文本内容单独存入变量，用 json.dumps 处理转义
import json
text = '开通\u201c中欧快航\u201d航线主要是因为（）'

# 方案 3：纯构造字典 → json.dump，完全避开源码中的中文
data = {"stem": "\u5f00\u901a\u201c\u4e2d\u6b27\u5feb\u822a\u201d\u822a\u7ebf"}
```

**记住**：`json.dump(data, f, ensure_ascii=False)` 输出到文件后，中文会正确显示。问题只出现在 `.py` 源码阶段。
