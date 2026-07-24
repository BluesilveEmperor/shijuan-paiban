---
name: "geo-exam-formatting"
description: "地理试卷排版完整流水线：代码+AI双轨，含增量编辑与脚本优先的token优化。用户提供原始.docx时触发，推荐作为首选入口。"
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
[Step1] clean-exam          → 清洗产物/content.md + images/ + image_manifest.json
    │                          （含 original_type 字段）
    ▼
[Step2] tag-structure       → 中间数据/structure.json              (AI)
    │
    ├─ inline 图 → 代码路径 → {{image:img_xxx}} 即占位符           (零 AI)
    │
    └─ anchor 图 → AI 路径
         [Step4] tag-images-anchor      → 中间数据/anchor_descriptions.json     (AI)
         [Step3] tag-placeholders-anchor → 中间数据/with_placeholders.json       (AI)
    │
    ▼
[Step5] map-images          → 试卷数据/final_exam.json             (代码+AI双轨)
    │
    ▼
[Step6] typeset-exam        → {试卷名称}-排版后.docx           (脚本)
```

## 子技能

| 技能 | 路径 | 职责 |
|------|------|------|
| master-exam-layout | `.trae/skills/master-exam-layout/SKILL.md` | 主编排调度，逐步骤检查产物与 Schema 校验，含 v3.6 token 优化策略 |
| clean-exam | `.trae/skills/clean-exam/SKILL.md` | 清洗原始 docx，提取正文和图片，记录 original_type |
| tag-structure | `.trae/skills/tag-structure/SKILL.md` | 识别试卷结构（分区/题号/题干/选项/材料/子问题） |
| tag-placeholders-anchor | `.trae/skills/tag-placeholders-anchor/SKILL.md` | **仅对 anchor 浮动图**标注需插入图片的位置（增量编辑模式） |
| tag-images-anchor | `.trae/skills/tag-images-anchor/SKILL.md` | **仅对 anchor 浮动图**进行内容理解 |
| map-images | `.trae/skills/map-images/SKILL.md` | **脚本优先 + AI 兜底**：map_images.py 锁定 inline + 匹配 anchor，AI 仅修正未映射项 |
| typeset-exam | `.trae/skills/typeset-exam/SKILL.md` | 调用排版脚本生成最终 Word 文档 |

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
| **Step3 增量编辑** | tag-placeholders-anchor | 用 Edit 工具逐占位符修改，禁止全量输出 JSON，节省 ~94% 输出 token |
| **Step5 脚本优先** | map-images | 先运行 map_images.py（零 token），仅在脚本有未映射项时 AI 才介入 |
| **Step5 delta 输出** | map-images (5c) | AI 只输出 image_mapping_overrides.json（~10-30 行），由脚本合并 |
| **Step4 可与 Step2 并行** | tag-images-anchor | anchor 图理解与结构打标无依赖，可并行启动 |

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
| 统一 Schema | `schemas/exam_paper.schema.json` |
| 格式样板 | `templates/exam_reference.json` |
| 样式模板 | `assets/template.dotx` |

## 快速开始

```
请按 master-exam-layout 执行流水线：
输入文件: <原始 docx 绝对路径>
```

主编排将自动调度 Step1→Step6，每步检查产物并报告状态。