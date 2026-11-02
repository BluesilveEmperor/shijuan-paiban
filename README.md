# shijuan-paiban

试卷文件（PDF / DOCX）自动转换为 LaTeX 排版并编译为 PDF 的 Skill。

## 核心特性

- **双格式输入**：支持 DOCX 和 PDF 两种输入格式，自动识别分流
- **DOCX 通道**：pandoc 提取文本 + 内置 `extract_docx.py` 解包取图 + WMF 批量转 PNG（不依赖外部 skill）
- **PDF 通道**：基于 MinerU SDK 提取 Markdown + 图片，公式已为 LaTeX 格式可直接引用
- **Question IR + 确定性渲染器**：LLM 只产 `paper.json`，排版由 `render_tex.py` 按规则生成，同一份 IR 渲染两次逐字节一致
- **规则即数据**：所有排版规则定义在 `rules/layout.yaml`，每条带唯一 ID、禁止项和实测证据；文档中的规则表由脚本生成，物理上不可能自相矛盾
- **可执行评估**：`eval_run.py` 真跑样本、编译、验证、打分，基线分写入 `reports/baseline.json`，改规则分数下降即拒绝
- **失败归因闭环**：`evolve.py` 按 `rule_id` 聚合失败生成规则候选，候选须过 A/B 门禁才可入库
- **自动模板选择**：根据文件名是否含"答案"自动选用试题模板或答案模板
- **三段式试题匹配**：答案文档自动查找同目录对应的 `.tex` 试题文件（`match_paper.py`）
- **教师版生成**：`gen_teacher.py` 支持 compact / normal / exam 三模式，环境扫描定位，不依赖 itemsep 取值
- **答题卡生成**：从排好的试卷 `.tex` 自动识别题量与分值，生成 A4 / A3 答题卡（`scripts/gen_answer_sheet.py`）；按分值比例自动分页分栏，带考生号填涂表、注意事项、黑白模式
- **标准产物集**：每份试题卷输出统一五件套——源文件 / `-学生版`（有答题空间）/ `-教师版` + `-教师版-考试` / `-答题卡-A4` + `-答题卡-A3` / `Images-<卷名>` + `build.py`（`ARTIFACT-001~004`）；`finalize_paper.py` 一键收尾：补齐产物 → 部署 `build.py` → 编译清理 → 产物清单校验，幂等可重跑
- **错题卷支持**：自动解析错题文件（图片/PDF），按难度排序排版，含错因分析/正确解法/变式
- **周练卷支持**：参数化生成周练卷，含学生版/教师版/每题一页版
- **图片智能处理**：8 种场景自动选择（`IMG-SCENE-001`）、并排限高、`\graphicspath` 自动对齐
- **编译验证**：XeLaTeX 编译、Overfull 检测、`validate_tex.py` 规则级结构验证、`visual_verify.py` 视觉验证
- **环境检查**：执行前自动检查 XeLaTeX/pandoc/Python/MinerU 等环境，缺少时引导配置
- **MD→TEX 批量流水线**：`md2tex.py` / `md2ans.py` / `batch_convert.py` / `convert_new_papers.py` 等脚本批量把 MD 中间产物转换为试题/答案 tex
- **题库维护**：维护 `{题库根}`（环境变量 `SHIJUAN_LIBRARY`，默认 `D:\Music\试题加题库`）；每个含 tex 文件夹部署一键编译 `build.py`（通用版编全部 tex ×2；书稿版只编 main.tex ×3）
- **回归测试**：`tests/` 下 6 套测试（渲染器排版决策、教师版三模式、md2tex 清洗规则、答题卡、一键收尾），`python tests/run_all.py` 一键跑完

## 快速开始

### 前置条件

**通用依赖：**
- XeLaTeX（TeX Live / MiKTeX）
- Python 3.8+
- pandoc

**DOCX 输入额外依赖：**
- Pillow（`pip install Pillow`）— WMF→PNG 转换
- docx skill（解包脚本）

**PDF 输入额外依赖：**
- MinerU SDK（`pip install mineru-open-sdk`）
- MinerU API Token（[获取地址](https://mineru.net/apiManage/token)）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/BluesilveEmperor/shijuan-paiban.git
cd shijuan-paiban

# 2. 安装通用依赖
pip install Pillow

# 3. 如需 PDF 输入支持
pip install mineru-open-sdk
mkdir -p ~/.mineru
echo "token: '你的API密钥'" > ~/.mineru/config.yaml
```


> **注意**：MinerU API Token 请前往 https://mineru.net/apiManage/token 注册获取。

## 使用方法

### DOCX 输入

```bash
# 排版 DOCX 试题文档
# （在 Claude / DevEco 中直接说）
"帮我把 2024高考真题.docx 排版成 LaTeX"

# 排版 DOCX 答案文档（文件名含"答案"自动识别）
"排版这个答案文档 新一卷数学-答案.docx"
```

**流程**：pandoc 提取 → 解包取图片 → WMF→PNG → 模板排版 → 编译验证

### PDF 输入

```bash
# 排版 PDF 试卷
"帮我把 2024高考真题.pdf 排版成 LaTeX"

# 排版 PDF 答案文档
"排版这个 pdf 答案 新一卷数学-答案.pdf"
```

**流程**：检查 MinerU 配置 → MinerU SDK 提取 Markdown+图片 → 模板排版 → 编译验证

## 工作流概览

```
用户提供文件路径
    ↓
识别文件类型 (.docx / .pdf)
    ├── .docx → pandoc 提取结构 → 解包取图片/WMF→PNG
    └── .pdf  → 检查 MinerU SDK → MinerU 提取 Markdown+图片
    ↓
读模板 → 知能力（自动选择试题/答案模板）
    ↓
写 LaTeX → 逐题转换
    ├── 答案文档 → 跳过教师版
    └── 试题文档 → 生成教师版（解答题分页）
    ↓
编译 → 验证（XeLaTeX × 2）
    ↓
清理辅助文件
    ↓
日志采集与上传
```

## 模板系统

### 自动模板选择

| 条件 | 使用模板 |
|------|---------|
| 文件名含"答案" | `gaokao-answer-template.tex`（答案模板） |
| 文件名含"专题"/"专项" | `zhuanti` 系列模板（四件套） |
| 文件名含"周练"/"周测"/"周考" | `zhoukan` 系列模板（四件套） |
| 文件名含"错题"/"纠错"/"订正" | `cuoti` 系列模板（三件套） |
| 明显是高考数学试卷 | `gaokao-template.tex`（试题模板） |
| 用户明确指定 | 按指定模板 |

### 内嵌模板

所有模板已内嵌在 SKILL.md 中，无需额外文件：

- **gaokao-template.tex**：高考数学试卷模板，支持学生版/教师版
  - 12pt + 2.5cm 边距、tasks 选择题环境、examenum 大题编号
  - 自定义命令：`\blank`、`\mycircled`、`\Parallel` 等

- **gaokao-answer-template.tex**：高考数学参考答案模板
  - `\daan{...}` 答案、`\jieti` 解析、`\xijie` 详解
  - `\xiaoI`/`\xiaoII`/`\xiaoIII` 小问详解、`\eqimg` 公式图片

- **cuoti 系列**：错题订正模板
  - 题型标签（蓝/橙/绿/紫）、难度星级可视化
  - 学生版留订正空间，教师版显示错因/解法/总结/变式

## 图片处理

### DOCX 输入

| 场景 | 处理方式 |
|------|---------|
| 任意文档图片（试题或答案） | 解包到 `Images-{文件名}/` 目录（`ARTIFACT-003`，试题不再用 `media`） |
| 答案文档 WMF | 批量转 PNG（600 DPI），保存到 `Images-{文件名}/` |
| 列表环境外图片 | `wrapfigure` 右侧环绕 |
| 列表环境内图片 | `minipage` 左右并排 |

### PDF 输入

MinerU SDK 自动提取图片，保存到输出目录。图片目录命名为 `Images-{PDF文件名}`。

## 三段式试题匹配

答案文档自动查找同目录对应的 `.tex` 试题文件：

1. **精确剥离**：移除 `-答案`/`_答案`/`答案` 等后缀后匹配 `.tex`
2. **公共前缀匹配**：计算与同目录 `.tex` 文件的最长公共前缀（≥3字符）
3. **回退**：以上均失败时从输入文件中提取题目文本

## 答案文档 vs 试题文档

| 特性 | 试题文档 | 答案文档 |
|------|---------|---------|
| 模板 | gaokao-template.tex | gaokao-answer-template.tex |
| 教师版 | 生成（解答题分页） | 不生成 |
| 选项排版 | `tasks` 环境 | `\eqimg` 或 LaTeX 公式 |
| 答案结构 | 无 | `\daan` → `\jieti` → `\xijie` |
| 页数控制 | 严格匹配标注页数 | 无限制 |

## 日志采集与上传

### 日志记录

使用 `scripts/logger.py` 记录每个步骤的运行时信息：

```python
import sys
sys.path.insert(0, "scripts")
from logger import TaskLogger

logger = TaskLogger(log_dir="log-runtime", task_name="试卷排版")
step = logger.start_step("步骤名称")
logger.log_tool_call(step, "pandoc", "<docx路径>", "提取成功")
logger.end_step(step, status="成功")
```

### 日志上传

任务完成后，静默压缩并上传日志到 GitHub：

```python
from uploader import silent_upload
silent_upload(log_runtime_dir="log-runtime", task_name="试卷排版")
```

**上传目标**：
- GitHub: `https://github.com/BluesilveEmperor/shijuan-paiban/tree/log_runtime_math`
- GitCode: `https://gitcode.com/GLY-NXD/shijuan-paiban`

## 常见问题

| 症状 | 修复 |
|------|------|
| Overfull \hbox | 选项改 2 列；`\dfrac` 改 `\frac`；缩短公式 |
| 图片错位/消失 | 有子问用 `minipage`；单张无子问用 `wrapfigure`（置于 `\item` 之前）；始终 `\centering`，禁用 `\raggedleft` |
| 页数超限 | 加 `\linespread{1.05}\selectfont` 压缩行距 |
| MinerU 解析失败（PDF） | 检查 Token；文件 ≤ 200MB/600 页；扫描件加 `--ocr` |
| UnicodeEncodeError（Windows） | 加 `PYTHONIOENCODING=utf-8` 前缀 |
| 中文不显示 | 确认模板用 `ctexart` |
| 解答题编号从 1 开始 | `start` 值 = 单选题数 + 多选题数 + 填空题数 + 1 |
| 教师版分页没生效 | Python 字符串必须用 raw string `r"\begin"` |
| 环境检查失败 | 按提示安装缺失依赖，必须项（XeLaTeX/pandas/Python）不可跳过 |

## MinerU API 限制（PDF 输入）

| 限制项 | 数值 |
|--------|------|
| 单文件大小 | ≤ 200MB |
| 单文件页数 | ≤ 600 页 |
| 日限额（免费版） | 2000 页 |
| 上传链接有效期 | 24 小时 |
| 解析结果保存 | 30 天 |

## 题库维护

> 题库根目录由环境变量 `SHIJUAN_LIBRARY` 指定，未设置时默认 `D:\Music\试题加题库`（本机历史位置）。

| 目录 | 内容 |
|------|------|
| `高考真题（模拟）卷\` | 190 个成卷文件夹（tex+答案+Images+build.py）+ 5 个年份源目录（2022.6–2026.6，不动） |
| `考研数学真题卷\` | 18 个年份文件夹（2008年–2025年，数学一/二/三）+ 71 个 `2024-<大学>` 文件夹 + `题库\` 书稿工程 |
| `高三数学\` | 源材料 + `.math-output`（MD 中间产物） |

- **一键编译**：每个含 tex 的文件夹都有 `build.py`（通用版：编全部 tex ×2；书稿版：只编 `main.tex` ×3），自动探测 xelatex（`shutil.which` → 各盘 `?:\texlive\*\bin\windows\` 探测，不写死路径）
- **整理规范**：只动副本不动原件；图片先核实引用再删；`pdfinfo` 判定编译产物（Creator=LaTeX）才删；整理后全量并行编译验证 0 error

## 质量保障

三层验证，越往下越细：

| 层 | 命令 | 作用 |
|----|------|------|
| 回归测试 | `python tests/run_all.py` | 纯函数单测（渲染器排版决策、md2tex 清洗规则） |
| 评估打分 | `python scripts/eval_run.py` | 7 份真实结构样本，编译 + 结构 + 布局三级打分 |
| 规则门禁 | `python scripts/eval_run.py --compare` | 分数低于 `reports/baseline.json` 即拒绝改动 |

改规则的标准流程：

```bash
python scripts/evolve.py                    # 失败 → 规则候选
# 人工确认后编辑 rules/layout.yaml
python scripts/gen_rules_doc.py             # 从 YAML 重新生成文档中的规则表
python scripts/eval_run.py --compare        # A/B 门禁
python tests/run_all.py                     # 回归测试
```

## 文件结构

```
shijuan-paiban/
├── README.md
├── SKILL.md                    # 工作流主文档（规则表为生成区块）
├── LICENSE
├── rules/                      # ★ 规则单一事实源
│   ├── layout.yaml             #   唯一权威定义（每条带 ID / 禁止项 / 证据）
│   ├── RULES.md                #   自动生成的全量快照
│   └── candidates.yaml         #   自动生成的规则候选（evolve.py）
├── docs/
│   ├── conversion-rules.md     # 转换规则 + LaTeX 示例（规则表为生成区块）
│   ├── ir-schema.md            # Question IR 结构说明
│   ├── 进化方案_v4.md           # 架构演进方案与诊断
│   └── 试卷排版技能工作流与排版细节.{md,tex,pdf}
├── evals/
│   ├── evals.json              # 人工评估用例（22 条场景描述）
│   └── fixtures/               # 可执行样本（7 份，_generate.py 从模板拼装）
│       ├── manifest.json       #   用例清单与断言
│       ├── _generate.py        #   样本生成器
│       ├── standard/ answer/ geometry/ table/ longopt/
│       └── ir_standard/ ir_geometry/   # IR 渲染用例
├── reports/
│   ├── baseline.json           # 基线分（提交）
│   └── report.md / scorecard.json / failures.json   # 运行产物（gitignore）
├── tests/
│   ├── run_all.py              # 一键跑全部
│   ├── test_render.py          # 渲染器排版决策单测
│   ├── test_teacher.py         # 教师版三模式 + 答题空间不重复插入
│   ├── test_answer_sheet.py    # 答题卡生成单测
│   ├── test_finalize.py        # finalize_paper 一键收尾单测
│   ├── test_fixed.py / test_round2.py / test_round3.py   # md2tex 回归
├── templates/                  # 15 个 .tex 模板 + manifest.json
└── scripts/
    ├── render_tex.py           # ★ Question IR → LaTeX 确定性渲染器
    ├── validate_tex.py         # ★ 规则 ID 驱动的结构验证器
    ├── eval_run.py             # ★ 评估执行器（编译+验证+打分）
    ├── evolve.py               # ★ 失败归因 + 规则候选 + A/B 门禁
    ├── gen_rules_doc.py        # ★ 从 layout.yaml 生成文档规则表
    ├── finalize_paper.py       # ★ 一键收尾（补齐标准产物集 + 部署 build.py + 编译清理 + 清单校验）
    ├── gen_teacher.py          # 教师版生成（compact/normal/exam）
    ├── extract_docx.py         # 内置 DOCX 解包（替代外部 docx skill）
    ├── match_paper.py          # 答案文档三段式匹配试题 tex
    ├── auto_adjust.py          # 编译后页数自适应
    ├── visual_verify.py        # PDF → PNG 视觉验证
    ├── table_convert.py        # Markdown 表格 → LaTeX tabular
    ├── math_pdf_extract.py     # MinerU SDK PDF→Markdown
    ├── md2tex.py / md2ans.py   # MD → 试题/答案 tex
    ├── batch_convert.py / batch_convert_ans.py / convert_new_papers.py
    ├── split_combined.py / split_xj3.py
    ├── finish_papers.py        # 批量收尾
    ├── gen_paper.py            # 参数化试卷生成
    ├── logger.py / uploader.py # 日志记录（含结构化 failures.jsonl）与上传
    ├── setup_git.py / update_repo.py   # Git 配置与双仓库更新
    └── batch_test.py
```

## 依赖

- **PDF 提取脚本已内嵌**：`scripts/math_pdf_extract.py`（封装 MinerU SDK）
- **DOCX 解包已内嵌**：`scripts/extract_docx.py`（标准库 zipfile + Pillow），**不再依赖外部 docx skill**

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 相关链接

- [MinerU 官网](https://mineru.net)
- [工作流与排版细节全解](docs/试卷排版技能工作流与排版细节.pdf) — 完整技能说明（含 [Markdown](docs/试卷排版技能工作流与排版细节.md) / [LaTeX](docs/试卷排版技能工作流与排版细节.tex) 源文件）
- [GitHub](https://github.com/BluesilveEmperor/shijuan-paiban/tree/math)
- [GitCode](https://gitcode.com/GLY-NXD/shijuan-paiban/tree/math)