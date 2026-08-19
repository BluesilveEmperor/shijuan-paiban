# 地理试卷排版系统 v3.6

基于代码+AI 双轨策略的地理试卷自动排版流水线，采用六步解耦架构，实现确定性逻辑由代码处理、不确定性场景由AI介入的高效排版方案。

## 项目简介

本系统将原始地理试卷 .docx 文件转换为排版精美的 Word 文档，支持：

- **双轨处理**：inline 图片由代码直接处理，anchor 浮动图片由 AI 智能判断
- **Token 优化**：采用增量编辑和脚本优先策略，降低 65% 的 token 消耗
- **Schema 校验**：统一的 JSON 数据契约，确保每步产物符合规范
- **双版本输出**：同时生成标准版式和封面版式两个版本

## 技能结构

本项目采用**单入口 + 内部步骤**结构，顶层 `SKILL.md` 是唯一入口，6 个 reference 文档描述各步骤详细规则。

### 顶层入口

| 文件 | 功能 |
|------|------|
| **SKILL.md** | 唯一入口，融合流水线总览 + 编排调度 + 运行约定，agent 只需识别此文件 |

### 流水线步骤文档（references/）

| 文件 | 步骤 | 功能 | 触发条件 |
|------|-----|------|---------|
| **01-clean-exam.md** | Step1 | 清洗原始 .docx，提取文本和图片 | 启动试卷排版流水线时 |
| **02-tag-structure.md** | Step2 | 识别试卷结构（分区/题号/选项等） | Step1 完成后 |
| **03-tag-placeholders-anchor.md** | Step3 | 为 anchor 浮动图创建占位符（增量编辑） | Step2 完成且存在 anchor 图片时 |
| **04-tag-images-anchor.md** | Step4 | 理解 anchor 浮动图内容 | 可与 Step2 并行，存在 anchor 图片时 |
| **05-map-images.md** | Step5c | AI 兜底修正未映射项（仅 delta） | Step5a 脚本映射有未映射项时 |
| **06-typeset-exam.md** | Step6 | 生成最终排版 Word 文档（双版本） | Step5 完成后 |

> 兼容说明：`.trae/skills/` 目录保留旧版 8 技能定义供本地 Trae IDE 使用，验证新结构后将移除。

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
GeoPaperFormat/
├── SKILL.md                 # 顶层入口（唯一入口，融合总览+调度+约定）
├── references/              # 流水线步骤详细规则
│   ├── 01-clean-exam.md            # Step1 清洗
│   ├── 02-tag-structure.md         # Step2 结构打标
│   ├── 03-tag-placeholders-anchor.md  # Step3 anchor 占位（增量编辑）
│   ├── 04-tag-images-anchor.md     # Step4 anchor 图理解
│   ├── 05-map-images.md            # Step5c AI 兜底修正
│   └── 06-typeset-exam.md          # Step6 排版
├── scripts/                 # Python 脚本（禁止修改）
├── schemas/                 # JSON Schema 定义
├── templates/               # 打标参考模板和案例
├── assets/                  # 样式模板（template.dotx）
├── .trae/skills/            # 旧版 8 技能定义（兼容本地 Trae IDE，验证后移除）
├── AGENTS.md                # AI 代理统一指令
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

## ZIP 分发与打包

本项目支持作为单入口 skill 包以 ZIP 形式分发。打包时 agent 只需识别 `SKILL.md` 作为唯一入口。

### 打包方式

**方式一：含外层目录（推荐）**

```powershell
# zip 内部结构：GeoPaperFormat/SKILL.md, GeoPaperFormat/references/, ...
Compress-Archive -Path .\SKILL.md, .\references, .\scripts, .\schemas, .\templates, .\assets, .\requirements.txt, .\README.md -DestinationPath GeoPaperFormat.zip
```

**方式二：flat 包（zip 根目录直接是 SKILL.md）**

```powershell
# zip 内部结构：SKILL.md, references/, scripts/, ...
Compress-Archive -Path .\SKILL.md, .\references, .\scripts, .\schemas, .\templates, .\assets, .\requirements.txt, .\README.md -DestinationPath GeoPaperFormat-flat.zip
```

### 打包前检查清单

```
[ ] 根目录存在 SKILL.md（含 name 和 description frontmatter）
[ ] references/ 包含 6 个步骤文档（01-06）
[ ] scripts/ 中被引用的脚本全部存在
[ ] assets/template.dotx 存在
[ ] schemas/exam_paper.schema.json 存在
[ ] templates/ 中的示例文件存在
[ ] requirements.txt 包含脚本运行所需依赖
```

### 打包后验证

解压后确认能直接找到 `SKILL.md`，且其中引用的 `references/`、`scripts/`、`schemas/`、`templates/`、`assets/` 路径均从 skill 根目录出发。

## 许可证

本项目仅供教育和研究使用。

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。