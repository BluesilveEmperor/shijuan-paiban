## 🤖 Assistant

下面是一份针对你当前 `GeoPaperFormat` 项目的迁移报告。目标是：**不再考虑本地 Trae 的 `.trae/skills/` 兼容性，只迁移成一个可以作为 ZIP 分发、由通用 agent 更容易识别的单入口 skill 包。**

**迁移结论**

你当前结构不是不能打包，而是**不适合直接作为单个 skill 包上传**。

当前问题集中在这里：

```text
GeoPaperFormat/
└── .trae/
    └── skills/
        ├── clean-exam/SKILL.md
        ├── geo-exam-formatting/SKILL.md
        ├── map-images/SKILL.md
        ├── master-exam-layout/SKILL.md
        ├── tag-images-anchor/SKILL.md
        ├── tag-placeholders-anchor/SKILL.md
        ├── tag-structure/SKILL.md
        └── typeset-exam/SKILL.md
```

这表示你的项目包含 8 个并列技能。对本地 Trae 来说，这可能是合理的；但对 ZIP 分发型 skill loader 来说，它通常期望的是：

```text
GeoPaperFormat/
├── SKILL.md
├── scripts/
├── references/
├── assets/
├── schemas/
├── templates/
└── requirements.txt
```

也就是：**一个顶层 `SKILL.md` 作为唯一入口，其他内容作为该 skill 的资源。**

所以迁移方向应该是：

> 从“多个子 skill”迁移为“一个主 skill + 多个内部步骤文档 + 脚本资源”。

---

**目标结构**

建议迁移后的最终目录如下：

```text
GeoPaperFormat/
├── SKILL.md
├── references/
│   ├── 01-clean-exam.md
│   ├── 02-tag-structure.md
│   ├── 03-tag-placeholders-anchor.md
│   ├── 04-tag-images-anchor.md
│   ├── 05-map-images.md
│   ├── 06-geo-exam-formatting.md
│   ├── 07-typeset-exam.md
│   └── 08-final-layout-and-compliance.md
├── assets/
│   └── template.dotx
├── schemas/
│   └── exam_paper.schema.json
├── scripts/
│   ├── __init__.py
│   ├── batch_process.py
│   ├── check_compliance.py
│   ├── clean_docx.py
│   ├── e2e_test.py
│   ├── extract_images.py
│   ├── map_images.py
│   ├── sanitize_json.py
│   ├── test_answer_table.py
│   ├── typeset_exam.py
│   ├── utils.py
│   └── validate_json.py
├── templates/
│   ├── exam_reference.json
│   ├── tag_examples_choice.md
│   ├── tag_examples_general.md
│   ├── tag_examples_quick_ref.md
│   └── tag_examples_subjective.md
├── README.md
└── requirements.txt
```

迁移完成后，打包时应该打包整个 `GeoPaperFormat/` 目录，且 zip 内部应该能看到：

```text
GeoPaperFormat/SKILL.md
GeoPaperFormat/references/
GeoPaperFormat/scripts/
GeoPaperFormat/assets/
GeoPaperFormat/schemas/
GeoPaperFormat/templates/
```

或者某些平台要求更严格时，zip 解压后直接看到：

```text
SKILL.md
references/
scripts/
assets/
schemas/
templates/
```

具体采用哪一种，取决于目标 agent 的上传规范。保守做法是准备两种包：

```text
GeoPaperFormat.zip              # zip 内含 GeoPaperFormat/ 文件夹
GeoPaperFormat-flat.zip         # zip 根目录直接是 SKILL.md
```

---

**文件迁移映射**

你现在的 8 个 `SKILL.md` 应该这样迁移：

```text
.trae/skills/master-exam-layout/SKILL.md
→ SKILL.md
```

说明：  
`master-exam-layout` 看名字像总控技能，最适合作为顶层入口。但它不能只是原样搬过去，应该改造成整个流水线的主说明文件。

```text
.trae/skills/clean-exam/SKILL.md
→ references/01-clean-exam.md

.trae/skills/tag-structure/SKILL.md
→ references/02-tag-structure.md

.trae/skills/tag-placeholders-anchor/SKILL.md
→ references/03-tag-placeholders-anchor.md

.trae/skills/tag-images-anchor/SKILL.md
→ references/04-tag-images-anchor.md

.trae/skills/map-images/SKILL.md
→ references/05-map-images.md

.trae/skills/geo-exam-formatting/SKILL.md
→ references/06-geo-exam-formatting.md

.trae/skills/typeset-exam/SKILL.md
→ references/07-typeset-exam.md
```

如果 `master-exam-layout/SKILL.md` 里除了总控流程外，也有最终检查、版式合规、输出规则等内容，可以拆成两部分：

```text
.trae/skills/master-exam-layout/SKILL.md
→ SKILL.md
→ references/08-final-layout-and-compliance.md
```

也就是说：

- 顶层 `SKILL.md` 只保留“什么时候使用、整体流程、调度顺序、输入输出、关键约束”
- 具体细节放入 `references/08-final-layout-and-compliance.md`

---

**顶层 SKILL.md 建议内容**

顶层 `SKILL.md` 应该是整个 skill 的唯一入口。它不应该太长，也不应该塞满所有细节。它的职责是让 agent 明白：

1. 这个 skill 是做什么的
2. 什么时候应该调用
3. 按什么顺序执行
4. 每一步参考哪个文档
5. 哪些脚本可以使用
6. 最终应该产出什么

建议结构如下：

```markdown
---
name: geo-paper-format
description: Clean, tag, validate, map images, and typeset geography exam papers through a structured document processing pipeline.
---

# Geo Paper Format

Use this skill when the user needs to process a geography exam paper, especially when the task involves cleaning DOCX content, tagging exam structure, mapping images, validating structured JSON, or typesetting the final paper.

## Required Inputs

The user may provide one or more of the following:

- A source exam document, usually DOCX
- Extracted text from an exam paper
- Image files extracted from the document
- Existing JSON following `schemas/exam_paper.schema.json`
- A formatting or layout requirement

## Pipeline

Follow the pipeline in order unless the user explicitly asks to run only a specific stage.

### 1. Clean the source document

Read `references/01-clean-exam.md`.

Use `scripts/clean_docx.py` when a DOCX file needs structural cleanup.

### 2. Tag exam structure

Read `references/02-tag-structure.md`.

Use the examples in:

- `templates/tag_examples_quick_ref.md`
- `templates/tag_examples_choice.md`
- `templates/tag_examples_subjective.md`
- `templates/tag_examples_general.md`

### 3. Tag placeholder anchors

Read `references/03-tag-placeholders-anchor.md`.

Use this stage to mark answer blanks, missing content slots, and layout placeholders.

### 4. Tag image anchors

Read `references/04-tag-images-anchor.md`.

Use this stage to identify where maps, charts, figures, and other images belong in the exam structure.

### 5. Extract and map images

Read `references/05-map-images.md`.

Use scripts when applicable:

- `scripts/extract_images.py`
- `scripts/map_images.py`

### 6. Apply geography exam formatting rules

Read `references/06-geo-exam-formatting.md`.

Apply subject-specific formatting rules for maps, figures, answer spaces, sections, and question numbering.

### 7. Typeset the final paper

Read `references/07-typeset-exam.md`.

Use:

- `scripts/typeset_exam.py`
- `assets/template.dotx`

### 8. Run final layout and compliance checks

Read `references/08-final-layout-and-compliance.md`.

Use scripts when applicable:

- `scripts/validate_json.py`
- `scripts/check_compliance.py`
- `scripts/sanitize_json.py`

Validate structured data against:

- `schemas/exam_paper.schema.json`

## Output

Produce the requested final artifact, such as:

- A cleaned document
- A tagged structure
- A validated JSON file
- A mapped image manifest
- A formatted exam paper
- A compliance report

When errors or ambiguities are found, report them clearly and stop before generating an invalid final document.
```

这个顶层文件的关键点是：**它承认流水线存在，但把流水线作为一个 skill 内部流程，而不是 8 个独立 skill。**

---

**references 目录设计**

`references/` 里的文件应该承接原来每个子技能的详细规则。

建议每个 reference 文件都采用统一格式：

```markdown
# Step Name

## Purpose

说明这个步骤负责什么。

## Inputs

列出这个步骤需要什么输入。

## Procedure

列出具体执行流程。

## Rules

列出必须遵守的规则。

## Scripts

列出可用脚本。

## Output

列出这个步骤应该产生什么结果。

## Failure Conditions

列出什么时候应该停止、询问用户或报告错误。
```

例如：

```text
references/01-clean-exam.md
```

建议包含：

```markdown
# Clean Exam

## Purpose

Clean the source exam document before structure tagging.

## Inputs

- Source DOCX file
- Optional user cleanup requirements

## Procedure

1. Inspect the document structure.
2. Remove irrelevant metadata or temporary content.
3. Normalize paragraphs, tables, and image placeholders.
4. Preserve question numbering and original educational content.
5. Save a cleaned working copy.

## Scripts

Use `scripts/clean_docx.py` when processing DOCX files.

## Output

A cleaned document ready for structure tagging.
```

再比如：

```text
references/05-map-images.md
```

建议包含：

```markdown
# Map Images

## Purpose

Map extracted image files to their correct positions in the exam structure.

## Inputs

- Extracted images
- Tagged image anchors
- Exam structure JSON

## Procedure

1. Read the image anchors from the tagged document.
2. Match images by order, caption, nearby text, or explicit anchor ID.
3. Generate or update the image mapping.
4. Report unmatched or ambiguous images.

## Scripts

- `scripts/extract_images.py`
- `scripts/map_images.py`

## Output

A complete image mapping that can be used during typesetting.
```

这样 agent 在主 `SKILL.md` 里知道去哪找细节，不需要一次性读完整个项目。

---

**scripts 目录处理建议**

你的 `scripts/` 目录可以基本保留，但建议做几项整理。

当前脚本：

```text
scripts/
├── __init__.py
├── batch_process.py
├── check_compliance.py
├── clean_docx.py
├── e2e_test.py
├── extract_images.py
├── map_images.py
├── sanitize_json.py
├── test_answer_table.py
├── typeset_exam.py
├── utils.py
└── validate_json.py
```

建议分类理解如下：

```text
核心流水线脚本：
- clean_docx.py
- extract_images.py
- map_images.py
- sanitize_json.py
- validate_json.py
- typeset_exam.py
- check_compliance.py

批处理脚本：
- batch_process.py

测试或开发验证脚本：
- e2e_test.py
- test_answer_table.py

公共工具：
- utils.py
```

如果你要作为正式 skill 包共享，建议考虑是否保留测试脚本：

```text
scripts/e2e_test.py
scripts/test_answer_table.py
```

保留也可以，但它们不应该被主 `SKILL.md` 描述成正常用户流程的一部分。更合适的是新增：

```text
tests/
├── e2e_test.py
└── test_answer_table.py
```

如果目标平台不喜欢多余目录，继续留在 `scripts/` 也可以，但建议在 `SKILL.md` 里明确只调用核心脚本。

---

**assets、schemas、templates 处理建议**

这些目录可以保留。

```text
assets/template.dotx
```

这个是正式资源，应该保留。主 `SKILL.md` 和 `references/07-typeset-exam.md` 都应该明确提到它。

```text
schemas/exam_paper.schema.json
```

这个是结构校验核心文件，应该保留。建议在以下文件中引用：

```text
SKILL.md
references/02-tag-structure.md
references/08-final-layout-and-compliance.md
```

```text
templates/
├── exam_reference.json
├── tag_examples_choice.md
├── tag_examples_general.md
├── tag_examples_quick_ref.md
└── tag_examples_subjective.md
```

这些也应该保留。它们应该作为 tagging 阶段的示例和参考，而不是单独技能。

建议映射：

```text
templates/exam_reference.json
→ 给结构化输出作为参考

templates/tag_examples_quick_ref.md
→ 给 agent 快速查看标注规则

templates/tag_examples_choice.md
→ 选择题标注示例

templates/tag_examples_subjective.md
→ 主观题标注示例

templates/tag_examples_general.md
→ 通用题型标注示例
```

---

**需要删除的内容**

因为你明确说“不需要考虑兼容本地 Trae 使用”，所以迁移完成后可以删除整个 `.trae/` 目录：

```text
删除：
GeoPaperFormat/.trae/
```

也就是删除：

```text
.trae/skills/clean-exam/
.trae/skills/geo-exam-formatting/
.trae/skills/map-images/
.trae/skills/master-exam-layout/
.trae/skills/tag-images-anchor/
.trae/skills/tag-placeholders-anchor/
.trae/skills/tag-structure/
.trae/skills/typeset-exam/
```

但注意：**删除前必须先把每个 `SKILL.md` 的有效内容迁移到顶层 `SKILL.md` 或 `references/`。**

---

**推荐迁移步骤**

建议按下面顺序迁移，风险最低。

1. 新建顶层 `SKILL.md`

从 `.trae/skills/master-exam-layout/SKILL.md` 提取总控逻辑，整理成新的顶层入口。

不要直接全文复制。应该保留：

- skill 名称
- skill 描述
- 使用场景
- 输入要求
- 流水线步骤
- 每步引用的 reference 文件
- 输出要求
- 异常处理规则

2. 新建 `references/` 目录

创建：

```text
references/01-clean-exam.md
references/02-tag-structure.md
references/03-tag-placeholders-anchor.md
references/04-tag-images-anchor.md
references/05-map-images.md
references/06-geo-exam-formatting.md
references/07-typeset-exam.md
references/08-final-layout-and-compliance.md
```

3. 迁移 8 个子技能内容

把每个 `.trae/skills/*/SKILL.md` 的详细内容搬到对应 reference 文件。

迁移时要做两类改写：

原来可能写：

```markdown
# clean-exam skill
Use this skill when...
```

迁移后应该改成：

```markdown
# Clean Exam

This reference describes step 1 of the Geo Paper Format pipeline.
```

也就是说，reference 文件不要再自称是独立 skill，而是自称为主 skill 的一个步骤。

4. 修正路径引用

原来子技能里如果有类似路径：

```text
../../scripts/clean_docx.py
../../../templates/tag_examples_choice.md
```

迁移后应该统一改成从 skill 根目录出发的路径：

```text
scripts/clean_docx.py
templates/tag_examples_choice.md
assets/template.dotx
schemas/exam_paper.schema.json
```

这是非常重要的一步。否则打包后 agent 会找不到资源。

5. 检查脚本调用说明

确认 `SKILL.md` 和 references 中提到的脚本都真实存在：

```text
scripts/clean_docx.py
scripts/extract_images.py
scripts/map_images.py
scripts/typeset_exam.py
scripts/validate_json.py
scripts/check_compliance.py
scripts/sanitize_json.py
```

不要在文档里引用不存在的脚本名。

6. 删除 `.trae/`

完成迁移并确认内容没有遗漏后，删除：

```text
.trae/
```

7. 更新 README.md

`README.md` 应该从“项目说明”改成“skill 使用说明”。

建议包括：

```markdown
# Geo Paper Format

## What It Does

## Package Structure

## Requirements

## Scripts

## Expected Inputs

## Expected Outputs

## Packaging
```

8. 打包验证

打包后检查 zip 内部结构，确保顶层入口存在。

理想结构：

```text
GeoPaperFormat.zip
└── GeoPaperFormat/
    ├── SKILL.md
    ├── references/
    ├── scripts/
    ├── assets/
    ├── schemas/
    ├── templates/
    ├── README.md
    └── requirements.txt
```

如果平台要求 zip 根目录直接是 skill 内容，则使用 flat 包：

```text
GeoPaperFormat-flat.zip
├── SKILL.md
├── references/
├── scripts/
├── assets/
├── schemas/
├── templates/
├── README.md
└── requirements.txt
```

---

**迁移后的执行逻辑**

迁移前：

```text
agent 需要识别多个 skill：
clean-exam
tag-structure
tag-placeholders-anchor
tag-images-anchor
map-images
geo-exam-formatting
typeset-exam
master-exam-layout
```

问题是 agent 不一定知道这些技能之间的关系。

迁移后：

```text
agent 只需要识别一个 skill：
geo-paper-format
```

然后主 `SKILL.md` 告诉它：

```text
Step 1 → references/01-clean-exam.md
Step 2 → references/02-tag-structure.md
Step 3 → references/03-tag-placeholders-anchor.md
Step 4 → references/04-tag-images-anchor.md
Step 5 → references/05-map-images.md
Step 6 → references/06-geo-exam-formatting.md
Step 7 → references/07-typeset-exam.md
Step 8 → references/08-final-layout-and-compliance.md
```

这样 agent 的识别成本大幅降低，ZIP 分发也更稳定。

---

**打包前检查清单**

迁移完成后，请逐项检查：

```text
[ ] 根目录存在 SKILL.md
[ ] 根目录不再依赖 .trae/skills/
[ ] SKILL.md 中有 name 和 description
[ ] SKILL.md 中明确写出完整流水线
[ ] references/ 中包含 8 个步骤文档
[ ] 每个 references 文件都不再自称独立 skill
[ ] 所有路径都从 skill 根目录开始引用
[ ] scripts/ 中被引用的脚本全部存在
[ ] assets/template.dotx 存在
[ ] schemas/exam_paper.schema.json 存在
[ ] templates/ 中的示例文件存在
[ ] requirements.txt 包含脚本运行所需依赖
[ ] README.md 已更新为分发说明
[ ] ZIP 解压后能直接找到 SKILL.md
```

---

**最终建议**

你的项目最适合迁移为：

```text
一个主 skill：GeoPaperFormat
多个内部步骤：references/01-08
多个执行工具：scripts/
多个资源文件：assets/、schemas/、templates/
```

不要再把 `clean-exam`、`map-images`、`typeset-exam` 等作为独立 skill 打包进同一个 ZIP。它们在逻辑上仍然是“子技能”，但在分发结构上应该变成**主 skill 的内部步骤文档**。

一句话总结：

> 迁移后，agent 只识别 `GeoPaperFormat/SKILL.md`；流水线由这个入口统一调度；其他原子能力全部下沉为 references 和 scripts。
