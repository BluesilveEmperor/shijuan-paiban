---
name: "geo-exam-formatting"
description: "Full pipeline for geography exam paper formatting: dual-track (code + AI) approach with token-optimized incremental editing. Invoke when user provides a raw geography exam .docx file."
---

# 地理试卷排版 v3.6 — 代码+AI 双轨 + Token 优化

六步解耦流水线，代码处理确定性逻辑（内嵌图片），AI 仅介入不确定性场景（浮动图片），v3.6 新增增量编辑和脚本优先策略，最大化降低 token 消耗。

## 版本对比

| 版本 | 策略 | 定位 |
|------|------|------|
| **v3.0** | 纯 AI 驱动 | 留给未来 AI 足够强大时使用 |
| **v3.5** | 代码 + AI 双轨 | inline 图代码处理，anchor 图 AI 介入 |
| **v3.6** | 代码 + AI 双轨 + Token 优化 | 当前版本——在 v3.5 基础上新增增量编辑、脚本优先、delta 输出 |

## 流水线架构

```
原始试卷.docx
    │
    ▼
[Step1] clean_exam          → 清洗产物/content.md + images/ + image_manifest.json
    │                          （含 original_type 字段）
    ▼
[Step2] tag_structure       → 中间数据/structure.json              (AI)
    │
    ├─ inline 图 → 代码路径 → {{image:img_xxx}} 即占位符           (零 AI)
    │
    └─ anchor 图 → AI 路径
         [Step4] tag_images_anchor      → 中间数据/anchor_descriptions.json     (AI)
         [Step3] tag_placeholders_anchor → 中间数据/with_placeholders.json       (AI)
    │
    ▼
[Step5] map_images          → 试卷数据/final_exam.json             (代码+AI双轨)
    │
    ▼
[Step6] typeset_exam        → {试卷名称}-排版后.docx           (脚本)
```

## 子技能

| 技能 | 路径 | 职责 |
|------|------|------|
| master_exam_layout | `.trae/skills/master_exam_layout/SKILL.md` | 主编排调度，逐步骤检查产物与 Schema 校验，含 v3.6 token 优化策略 |
| clean_exam | `.trae/skills/clean_exam/SKILL.md` | 清洗原始 docx，提取正文和图片，记录 original_type |
| tag_structure | `.trae/skills/tag_structure/SKILL.md` | 识别试卷结构（分区/题号/题干/选项/材料/子问题） |
| tag_placeholders_anchor | `.trae/skills/tag_placeholders_anchor/SKILL.md` | **仅对 anchor 浮动图**标注需插入图片的位置（增量编辑模式） |
| tag_images_anchor | `.trae/skills/tag_images_anchor/SKILL.md` | **仅对 anchor 浮动图**进行内容理解 |
| map_images | `.trae/skills/map_images/SKILL.md` | **脚本优先 + AI 兜底**：map_images.py 锁定 inline + 匹配 anchor，AI 仅修正未映射项 |
| typeset_exam | `.trae/skills/typeset_exam/SKILL.md` | 调用排版脚本生成最终 Word 文档 |

> **注意**：`.trae/skills/pipeline_token_saver/` 是 v3.6 token 优化策略的参考文档，其内容已整合到 `master_exam_layout` 和各子技能中，不是独立的流水线步骤。

## 核心设计原则

- **单一职责**：每个子技能只做一件事
- **落盘传递**：步骤间通过文件传递数据，不依赖上下文记忆
- **Schema 先行**：所有产物通过 `schemas/exam_paper.schema.json` 校验
- **代码优先**：能确定的事交给代码，不确定的事才让 AI 介入
- **兜底优先**：无法确定时标记 `uncertain`，不硬猜
- **增量输出**：AI 只输出 delta（增量），脚本负责合并（v3.6 新增）

## v3.6 核心改进

| 改进 | 影响步骤 | 效果 |
|------|---------|------|
| **Step3 增量编辑** | tag_placeholders_anchor | 用 Edit 工具逐占位符修改，禁止全量输出 JSON，节省 ~94% 输出 token |
| **Step5 脚本优先** | map_images | 先运行 map_images.py（零 token），仅在脚本有未映射项时 AI 才介入 |
| **Step5 delta 输出** | map_images (5c) | AI 只输出 image_mapping_overrides.json（~10-30 行），由脚本合并 |
| **Step4 可与 Step2 并行** | tag_images_anchor | anchor 图理解与结构打标无依赖，可并行启动 |

## AI 执行约束

### 强制检查机制

每步结束后，主编排**必须**运行合规检查。非零退出码 = 流水线中断，不得进入下一步：

| 步骤 | 合规检查命令 |
|------|-------------|
| Step2 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step2 --json 中间数据/structure.json` |
| Step3 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step3 --json 中间数据/with_placeholders.json` |
| Step5 完成后 | `python scripts/check_compliance.py --work-dir {工作目录} --step step5 --json 试卷数据/final_exam.json` |

### 严格禁止的行为

1. ❌ **禁止在工作目录创建 .py 文件**
2. ❌ **禁止绕过合规检查**
3. ❌ **禁止自行编写排版脚本** —— Step6 必须调用 `scripts/typeset_exam.py`
4. ❌ **禁止修改 `scripts/` 下的任何现有脚本**
5. ❌ **禁止为 inline 图创建占位符** —— inline 图的 `{{image:img_xxx}}` 标记已由代码生成

## 关键资源

| 资源 | 路径 |
|------|------|
| 重构方案 | `REFACTOR_PLAN.md` |
| 统一 Schema | `schemas/exam_paper.schema.json` |
| 格式样板 | `templates/exam_reference.json` |
| 样式模板 | `assets/template.dotx` |
| 流水线文档 | `docs/pipeline.md` |

## 快速开始

```
请按 master_exam_layout 执行流水线：
输入文件: <原始 docx 绝对路径>
```

主编排将自动调度 Step1→Step6，每步检查产物并报告状态。
