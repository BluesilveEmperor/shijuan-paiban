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

| 技能 | 职责 |
|------|------|
| master_exam_layout | 主编排调度，逐步骤检查产物与 Schema 校验 |
| clean_exam | 清洗原始 docx，提取正文 Markdown 和图片 |
| tag_structure | 识别试卷结构（分区/题号/题干/选项/材料/子问题） |
| tag_placeholders | 标注需要图片的位置，创建占位符 |
| tag_images | 逐张理解图片（类型/关键词/OCR/学科特征） |
| map_images | 占位符与图片的语义匹配 |
| typeset_exam | 调用排版脚本生成最终 Word 文档 |

## 核心设计原则

- **单一职责**：每个子技能只做一件事
- **落盘传递**：步骤间通过文件传递数据，不依赖上下文记忆
- **Schema 先行**：所有产物通过 `schemas/exam_paper.schema.json` 校验
- **兜底优先**：无法确定时标记 `uncertain`，不硬猜

## AI执行约束

### 强制检查机制

每步结束后，主编排**必须**运行合规检查。非零退出码 = 流水线中断，不得进入下一步：

| 步骤 | 合规检查命令 |
|------|-------------|
| Step2 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step2 --json 中间数据/structure.json` |
| Step3 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step3 --json 中间数据/with_placeholders.json` |
| Step5 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step5 --json 试卷数据/final_exam.json` |

`check_compliance.py` 会自动检测以下违规并**拒绝进入下一步**：
1. 工作目录中是否存在 AI 自行创建的 `.py` 文件
2. 预期产物是否缺失
3. JSON 产物是否通过 Schema 校验

### 严格禁止的行为

1. ❌ **禁止在工作目录创建 .py 文件** —— JSON 产物只能通过 `Write`/`Edit` 工具生成
2. ❌ **禁止绕过合规检查** —— 不运行 `check_compliance.py` 或忽略其失败结果
3. ❌ **禁止自行编写排版脚本** —— Step6 必须调用 `scripts/typeset_exam.py`，不得自创
4. ❌ **禁止修改 `scripts/` 下的任何现有脚本**

### JSON 写入方式

生成 JSON 产物（structure.json / with_placeholders.json / image_descriptions.json / final_exam.json）时：

- **唯一正确方式**：使用 `Write` 工具直接写入 JSON 内容
- **唯一例外**：Step3 的增量修改使用 `Edit` 工具（见 tag_placeholders 技能文档）
- **严禁方式**：创建 `.py` 脚本调用 `json.dump()` —— 这会被 `check_compliance.py` 检测并拒绝

## 快速开始

```
请按 master_exam_layout 技能执行流水线：
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
| 实施计划 | `docs/implementation_plan.md` |
| 重构方案 | `docs/refactor_plan.md` |
| 修复方案 | `docs/fix_plan_curly_quotes.md` |
| Bug 报告 | `docs/bug_report.md` |
