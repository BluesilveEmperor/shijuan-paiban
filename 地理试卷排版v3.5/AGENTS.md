# AGENTS.md — 地理试卷排版 AI 代理指令

> 本文件是所有 AI 编码代理的统一入口。各平台通过符号链接引用此文件。

## 项目概述

地理试卷排版系统（v3.6），采用六步解耦流水线架构，将原始地理试卷 .docx 转换为排版精美的 Word 文档。

**核心策略**：代码 + AI 双轨。代码处理确定性逻辑（内嵌图片），AI 仅介入不确定性场景（浮动图片）。v3.6 新增增量编辑和脚本优先策略。

## 技术栈

- **语言**：Python 3.10+
- **文档处理**：python-docx, lxml
- **数据格式**：JSON（Schema: `schemas/exam_paper.schema.json`）
- **样式模板**：`assets/template.dotx`（21 种预设样式）

## 关键命令

```bash
# 清洗原始 docx
python scripts/clean_docx.py --input <input.docx> --output <output.docx>

# 提取图片
python scripts/extract_images.py --input <cleaned.docx> --output <no_images.docx>

# Schema 校验
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json <target.json>

# 合规检查
python scripts/check_compliance.py --work-dir <work_dir> --step <step> --json <target.json>

# 双轨映射（脚本优先，零 AI token）
python scripts/map_images.py --placeholders <structure.json> --images-manifest <manifest.json> --output <final.json>

# 排版生成
python scripts/typeset_exam.py --json <final.json> --template assets/template.dotx --images <images_dir> --output <output.docx>
```

## 流水线步骤

```
Step1: clean_exam          → 清洗产物/ (content.md + images/ + image_manifest.json)
Step2: tag_structure       → 中间数据/structure.json              (AI)
Step3: tag_placeholders_anchor → 中间数据/with_placeholders.json  (AI, 增量编辑)
Step4: tag_images_anchor   → 中间数据/anchor_descriptions.json   (AI, 可与 Step2 并行)
Step5: map_images          → 试卷数据/final_exam.json            (脚本优先 + AI 兜底)
Step6: typeset_exam        → 排版后 .docx                        (脚本)
```

**Step3/4 跳过条件**：当 `image_manifest.json` 中 `anchor_count == 0` 时，跳过 Step3 和 Step4。

## 目录结构

```
地理试卷排版v3.5/
├── scripts/           # Python 脚本（禁止修改，禁止在工作目录创建 .py）
├── schemas/           # exam_paper.schema.json 统一数据契约
├── templates/         # 打标参考模板和案例
├── assets/            # template.dotx 样式模板
├── docs/              # 流水线文档和重构方案
├── tests/             # 测试用 .docx 文件
└── .trae/skills/      # Trae IDE 技能定义（SKILL.md 格式）
```

## 严格禁止的行为

1. **禁止在工作目录创建 .py 文件** — 所有脚本在 `scripts/` 中
2. **禁止绕过合规检查** — Step2/3/5 后必须运行 `check_compliance.py`
3. **禁止自行编写排版脚本** — Step6 必须调用 `scripts/typeset_exam.py`
4. **禁止修改 `scripts/` 下的任何现有脚本**
5. **禁止为 inline 图创建占位符** — `{{image:img_xxx}}` 已由代码生成
6. **禁止全量重写大型 JSON** — Step3 用 Edit 增量修改，Step5 AI 只输出 delta

## v3.6 Token 优化策略

| 步骤 | 优化方式 | 效果 |
|------|---------|------|
| Step3 | 增量编辑：先 copy 再 Edit，禁止 Write 全量输出 | 节省 ~94% 输出 token |
| Step5 | 脚本优先：先运行 map_images.py（零 token），AI 仅处理未映射项 | happy path 零 AI token |
| Step5c | Delta 输出：AI 只输出 image_mapping_overrides.json（~10-30 行） | 节省 ~87% token |

## 图片处理核心规则

- **inline 图**：`paragraph_index` 可靠，代码直接映射，零 AI 依赖
- **anchor 图**：`paragraph_index` 不可靠，需 AI 介入判断位置
- **符号小图**（< 2KB）：标记 `{{symbol:img_xxx}}`，不做内容映射
- **图片尺寸**：基准 = 原卷 extent 真值（来自 `image_manifest.json`）；原宽 < 6cm 才放大到 12cm
- **一行多图**：用 `image_manifest.json` 的 `paragraph_index` 判断同段落，横排嵌入

## 数据流关键字段

| 字段 | 位置 | 说明 |
|------|------|------|
| `original_type` | image_manifest.json | `"inline"` / `"anchor"` / `"vml"` / `"unknown"` |
| `track` | final_exam.json → image_mapping | `"code"` / `"ai"`，映射来源标识 |
| `_source` | placeholders | `"anchor"`，占位符来源（v3.5 双轨分流） |
| `position_hint` | anchor_descriptions.json | AI 对 anchor 图应放位置的分析 |
| `extent_w_cm` / `extent_h_cm` | image_manifest.json | 图片原始 EMU 尺寸转厘米 |
