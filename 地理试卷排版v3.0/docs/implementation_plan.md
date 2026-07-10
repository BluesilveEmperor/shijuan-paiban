# 地理试卷排版技能重构实施计划 v3.0

> **文档版本**：v1.0
> **编制日期**：2026-07-09
> **编制依据**：[重构方案.md](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v3.0/docs/refactor_plan.md)
> **现状基线**：[地理试卷排版v2.0](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0)
> **目标产物**：[地理试卷排版v3.0](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v3.0)

---

## 一、重构背景与现状分析

### 1.1 v2.0 架构现状

v2.0 采用"AI 主导编排"架构，通过 [SKILL.md](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/SKILL.md) 的 `description` 字段自动触发子技能，形成"清洗→打标→排版"三阶段流水线：

```
geo-exam-formatting（主编排）
  ├─ geo-exam-clean（清洗阶段）
  │   ├─ clean_docx.py        清洗 docx
  │   ├─ extract_images.py    提取图片
  │   ├─ geo-exam-image-analysis   AI 图片理解
  │   └─ geo-exam-image-insertion  AI 插入占位符
  ├─ geo-exam-tag（打标阶段）
  │   ├─ tag_docx.py          正则打标
  │   ├─ geo-exam-ai-tagging       AI 语义打标
  │   └─ geo-exam-merge-validation 双轨融合验证
  └─ geo-exam-format（排版阶段）
      └─ format_docx.py       模板排版
```

**现有数据契约**：
- 清洗输出：`插入图片后.docx` + `images/` + `images_analysis.json` + `image_manifest.json`
- 打标输出：`tagged_script.json` + `tagged_ai.json` → `tagged_final.json`
- 排版输出：`formatted.docx` + `quality_report.html`
- 现有 Schema：见 [json_schema.json](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/geo-exam-tag/ai-skills/geo-exam-ai-tagging/references/json_schema.json)，含 `exam_info` / `sections` / `question_groups` / `questions` / `confidence`

### 1.2 v2.0 核心问题诊断

经系统遍历 v2.0 全部 SKILL 与脚本，诊断出以下关键问题：

| 编号 | 问题 | 证据 | 影响 |
|------|------|------|------|
| P1 | **AI 打标过度聚合** | [geo-exam-ai-tagging/SKILL.md](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/geo-exam-tag/ai-skills/geo-exam-ai-tagging/SKILL.md) 一次完成结构识别+图片占位识别+图片引用 | 错误无法定位，单点失败波及全链路 |
| P2 | **触发依赖 description 隐式约定** | [SKILL.md](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/SKILL.md) L216-219 "子skills通过description自动触发" | 流程不稳定，依赖 AI 自觉，易跳步或漏步 |
| P3 | **图片占位符格式不统一** | 清洗用 `【图片：xxx - 描述】`，排版用 `{{IMAGE:xxx}}`，需三层向后兼容 | 格式混乱，防御性代码冗余 |
| P4 | **双轨并行增加复杂度** | [validation_rules.md](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/geo-exam-tag/ai-skills/geo-exam-merge-validation/references/validation_rules.md) 脚本轨+AI轨融合逻辑复杂 | 维护成本高，置信度判定模糊 |
| P5 | **Schema 与排版脚本耦合不彻底** | [format_docx.py](file:///c:/Users/Deledy_02/Desktop/GeoPaperFormat/地理试卷排版v2.0/geo-exam-format/scripts/format_docx.py) 同时支持格式A/B/旧字段三种图片表示 | 排版脚本需做语义判断，违背"纯样式应用"原则 |
| P6 | **兜底字段不系统** | Schema 仅有 `confidence`，缺 `uncertain` / `unclassified_blocks` / `warnings` 统一规范 | AI 倾向硬猜而非标注不确定 |
| P7 | **缺少占位符↔图片映射独立环节** | 图片理解(image-analysis)与图片插入(image-insertion)在清洗阶段完成，未与结构解耦 | 图文分离时上下文错位无法纠正 |

### 1.3 重构必要性

v2.0 已验证"清洗→打标→排版"主链路可行，但**单点聚合与隐式触发**导致：错误难定位、扩展难推进、结果不稳定。重构的核心不是推翻重写，而是**拆解聚合点、显式化契约、落盘化数据流**，使每一步可控、可验证、可回滚。

---

## 二、重构目标

（完整内容请参考原始 `实施计划.md`）
