---
name: "geo-exam-formatting"
description: "Full pipeline for geography exam paper formatting: clean, tag structure, place images, understand images, map images, and typeset to .docx. Invoke when user provides a raw geography exam .docx file."
---

# 地理试卷排版 v3.0

六步解耦流水线，将原始 .docx 地理试卷自动排版为规范格式的 Word 文档。

## 流水线架构

```
原始试卷.docx
    │
    ▼
[Step1] clean_exam          → 清洗产物/content.md + images/
    │
    ▼
[Step2] tag_structure       → 中间数据/structure.json
    │
    ▼
[Step3] tag_placeholders    → 中间数据/with_placeholders.json
    │
    ▼
[Step4] tag_images          → 中间数据/image_descriptions.json  (可并行)
    ▼
[Step5] map_images          → 试卷数据/final_exam.json
    │
    ▼
[Step6] typeset_exam        → 排版文档/final_exam.docx
```

## 子技能

| 技能 | 路径 | 职责 |
|------|------|------|
| master_exam_layout | `.trae/skills/master_exam_layout/SKILL.md` | 主编排调度，逐步骤检查产物与 Schema 校验 |
| clean_exam | `.trae/skills/clean_exam/SKILL.md` | 清洗原始 docx，提取正文 Markdown 和图片 |
| tag_structure | `.trae/skills/tag_structure/SKILL.md` | 识别试卷结构（分区/题号/题干/选项/材料/子问题） |
| tag_placeholders | `.trae/skills/tag_placeholders/SKILL.md` | 标注需要图片的位置，创建占位符 |
| tag_images | `.trae/skills/tag_images/SKILL.md` | 逐张理解图片（类型/关键词/OCR/学科特征） |
| map_images | `.trae/skills/map_images/SKILL.md` | 占位符与图片的语义匹配 |
| typeset_exam | `.trae/skills/typeset_exam/SKILL.md` | 调用排版脚本生成最终 Word 文档 |

## 核心设计原则

- **单一职责**：每个子技能只做一件事
- **落盘传递**：步骤间通过文件传递数据，不依赖上下文记忆
- **Schema 先行**：所有产物通过 `schemas/exam_paper.schema.json` 校验
- **兜底优先**：无法确定时标记 `uncertain`，不硬猜

## AI执行约束

**严格禁止以下行为**：

1. ❌ **禁止自行创建新的Python脚本文件**
   - AI不得在执行过程中创建任何 `.py` 文件
   - 已有的核心脚本（`clean_docx.py`、`extract_images.py`、`validate_json.py`、`typeset_exam.py`等）不得修改

2. ❌ **禁止自行运行生成的Python脚本**
   - AI不得通过 `RunCommand` 工具执行自行生成的脚本
   - 仅允许调用项目已定义的核心脚本（见 `scripts/` 目录）

3. ❌ **禁止绕过Schema校验直接生成最终产物**
   - Step2-5的产物必须通过 `validate_json.py` 校验后才能进入下一步
   - 绝不允许忽略Schema校验直接进入Step6

4. ❌ **禁止生成临时工具脚本**
   - 不允许创建 `generate_*.py`、`sanitize_*.py` 等辅助工具
   - 所有验证和修复应通过现有工具完成

**正确执行方式**：

- ✅ **Step2 (tag_structure)**：AI应直接通过 `Write` 工具生成 `structure.json`，而非生成Python脚本
- ✅ **Step3 (tag_placeholders)**：AI应直接通过 `Write` 工具生成 `with_placeholders.json`
- ✅ **Step4 (tag_images)**：AI应直接通过 `Write` 工具生成 `image_descriptions.json`
- ✅ **Step5 (map_images)**：AI应直接通过 `Write` 工具生成 `final_exam.json`，或调用 `scripts/map_images.py`
- ✅ **所有产物必须通过 `validate_json.py` 校验**

**违反后果**：

- 生成的Python脚本将被立即删除
- 未通过Schema校验的产物将被拒绝进入下一步
- 违规执行将导致流水线中断并报错

## 快速开始

```
请按 master_exam_layout 执行流水线：
输入文件: <原始 docx 绝对路径>
```

主编排将自动调度 Step1→Step6，每步检查产物并报告状态。

## 关键资源

| 资源 | 路径 |
|------|------|
| 统一 Schema | `schemas/exam_paper.schema.json` |
| 格式样板 | `templates/exam_reference.json` |
| 样式模板 | `assets/template.dotx` |
| 流水线文档 | `docs/pipeline.md` |
| 异常手册 | `docs/error_cases.md` |
| 实施计划 | `实施计划.md` |
| 重构方案 | `重构方案.md` |
