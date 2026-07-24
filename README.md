# 地理试卷排版系统 v3.6

基于代码+AI 双轨策略的地理试卷自动排版流水线，采用六步解耦架构，实现确定性逻辑由代码处理、不确定性场景由AI介入的高效排版方案。

## 项目简介

本系统将原始地理试卷 .docx 文件转换为排版精美的 Word 文档，支持：

- **双轨处理**：inline 图片由代码直接处理，anchor 浮动图片由 AI 智能判断
- **Token 优化**：采用增量编辑和脚本优先策略，降低 65% 的 token 消耗
- **Schema 校验**：统一的 JSON 数据契约，确保每步产物符合规范
- **双版本输出**：同时生成标准版式和封面版式两个版本

## 技能列表

本项目包含 8 个技能模块：

### 主技能

| 技能名称 | 功能 | 触发条件 |
|---------|------|---------|
| **geo-exam-formatting** | 完整的地理试卷排版流水线（v3.6） | 用户提供原始地理试卷 .docx 文件时 |
| **master-exam-layout** | 编排 6 步试卷排版流水线 | 用户需要对完整流水线进行排版时 |

### 子技能（流水线步骤）

| 技能名称 | 步骤 | 功能 | 触发条件 |
|---------|-----|------|---------|
| **clean-exam** | Step1 | 清洗原始 .docx，提取文本和图片 | 启动试卷排版流水线时 |
| **tag-structure** | Step2 | 识别试卷结构（分区/题号/选项等） | Step1 完成后 |
| **tag-placeholders-anchor** | Step3 | 为 anchor 浮动图创建占位符 | Step2 完成且存在 anchor 图片时 |
| **tag-images-anchor** | Step4 | 理解 anchor 浮动图内容 | 可与 Step2 并行，存在 anchor 图片时 |
| **map-images** | Step5 | 双轨映射图片到占位符 | Step3/Step4 完成后 |
| **typeset-exam** | Step6 | 生成最终排版 Word 文档 | Step5 完成后 |

## 技术栈

- **语言**：Python 3.10+
- **文档处理**：python-docx, lxml
- **数据格式**：JSON（Schema: `schemas/exam_paper.schema.json`）
- **样式模板**：`assets/template.dotx`（21 种预设样式）
- **IDE 技能系统**：.trae/skills/（符合 skill-creator 规范）

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 验证安装
python scripts/clean_docx.py --help
```

## 快速开始

### 使用主技能（推荐）

在 Trae IDE 中：

```
请按 geo-exam-formatting 技能执行流水线：
输入文件: <原始 docx 绝对路径>
```

### 使用编排技能

```
请按 master-exam-layout 技能执行流水线：
输入文件: <原始 docx 绝对路径>
```

### 手动执行各步骤

```bash
# Step1: 清洗原始 docx
python scripts/clean_docx.py --input <input.docx> --output <output.docx>

# Step2: 提取图片
python scripts/extract_images.py --input <cleaned.docx> --output <no_images.docx>

# Step5: 双轨映射（脚本优先）
python scripts/map_images.py --placeholders <structure.json> --images-manifest <manifest.json> --output <final.json>

# Step6: 排版生成
python scripts/typeset_exam.py --json <final.json> --template assets/template.dotx --images <images_dir> --output <output.docx>
```

## 项目结构

```
地理试卷排版v3.5/
├── .trae/
│   └── skills/              # 技能定义目录（符合 skill 规范）
│       ├── clean-exam/      # Step1: 清洗技能
│       ├── geo-exam-formatting/  # 主技能（完整流水线）
│       ├── map-images/      # Step5: 映射技能
│       ├── master-exam-layout/  # 编排技能
│       ├── tag-images-anchor/  # Step4: anchor 图理解
│       ├── tag-placeholders-anchor/  # Step3: anchor 图占位
│       ├── tag-structure/   # Step2: 结构打标
│       └── typeset-exam/    # Step6: 排版技能
├── scripts/                 # Python 脚本（禁止修改）
├── schemas/                 # JSON Schema 定义
├── templates/               # 打标参考模板和案例
├── assets/                  # 样式模板
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

## 流水线架构

```
原始试卷.docx
    │
    ▼
[Step1] clean-exam          → 清洗产物/content.md + images/ + image_manifest.json
    │
    ▼
[Step2] tag-structure       → 中间数据/structure.json              (AI)
    │
    ├─ inline 图 → 代码路径 → {{image:img_xxx}} 即占位符           (零 AI)
    │
    └─ anchor 图 → AI 路径
         [Step4] tag-images-anchor      → 中间数据/anchor_descriptions.json     (AI)
         [Step3] tag-placeholders-anchor → 中间数据/with_placeholders.json       (AI, 增量编辑)
    │
    ▼
[Step5] map-images          → 试卷数据/final_exam.json             (脚本优先 + AI 兜底)
    │
    ▼
[Step6] typeset-exam        → {试卷名称}-版式一.docx + {试卷名称}-版式二.docx
```

## 核心设计原则

- **单一职责**：每个子技能只做一件事
- **落盘传递**：步骤间通过文件传递数据，不依赖上下文记忆
- **Schema 先行**：所有产物通过 `schemas/exam_paper.schema.json` 校验
- **代码优先**：能确定的事交给代码，不确定的事才让 AI 介入
- **兜底优先**：无法确定时标记 `uncertain`，不硬猜
- **增量输出**：AI 只输出 delta（增量），脚本负责合并（v3.6 新增）

## 严格禁止的行为

1. **禁止在工作目录创建 .py 文件** — 所有脚本在 `scripts/` 中
2. **禁止绕过合规检查** — Step2/3/5 后必须运行 `check_compliance.py`
3. **禁止自行编写排版脚本** — Step6 必须调用 `scripts/typeset_exam.py`
4. **禁止修改 `scripts/` 下的任何现有脚本**
5. **禁止为 inline 图创建占位符** — `{{image:img_xxx}}` 已由代码生成
6. **禁止全量重写大型 JSON** — Step3 用 Edit 增量修改，Step5 AI 只输出 delta

## v3.6 Token 优化效果

| 步骤 | 优化方式 | Token 节省 |
|------|---------|----------|
| Step3 | 增量编辑：先 copy 再 Edit，禁止 Write 全量输出 | ~94% |
| Step5 | 脚本优先：先运行 map_images.py（零 token），AI 仅处理未映射项 | Happy path: 100% |
| Step5c | Delta 输出：AI 只输出 image_mapping_overrides.json（~10-30 行） | ~87% |

## 图片处理核心规则

- **inline 图**：`paragraph_index` 可靠，代码直接映射，零 AI 依赖
- **anchor 图**：`paragraph_index` 不可靠，需 AI 介入判断位置
- **符号小图**（< 2KB）：标记 `{{symbol:img_xxx}}`，不做内容映射
- **图片尺寸**：基准 = 原卷 extent 真值（来自 `image_manifest.json`）；原宽 < 6cm 才放大到 12cm
- **一行多图**：用 `image_manifest.json` 的 `paragraph_index` 判断同段落，横排嵌入

## 许可证

本项目仅供教育和研究使用。

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。