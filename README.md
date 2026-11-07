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
- **答题卡生成**：从排好的试卷 `.tex` 自动识别题量与分值，生成 A4 / A3 答题卡（`scripts/gen_answer_sheet.py`）；按分值比例自动分页分栏，带考生号填涂表、注意事项、黑白模式
- **标准产物集**：每份试题卷输出统一产物集——试卷 `<卷名>.tex/.pdf`（学生版/教师版合并后的唯一版本，含 `\answern` 答题空间）/ `2611数学答题卡（A4）-<考试名>` + `（A3）` / `Images-<卷名>` + `build.py`（`ARTIFACT-001~004`）；`finalize_paper.py` 一键收尾：补齐答题卡 → 部署 `build.py` → 编译清理 → 隐藏 `temp_scripts/` → 产物清单校验，幂等可重跑
- **只读运行**：使用期间技能安装目录 `{SKILL_DIR}` 只读；每卷一次性提取/排版脚本放工作目录 `temp_scripts/`，收尾自动隐藏为 `.temp_scripts/`（Windows 同时设置隐藏属性，资源管理器默认不可见；`ACCESS-001` / `ACCESS-002`）
- **错题卷支持**：自动解析错题文件（图片/PDF），按难度排序排版，含错因分析/正确解法/变式
- **周练卷支持**：参数化生成周练卷，含学生版/教师版/每题一页版
- **图片智能处理**：8 种场景自动选择（`IMG-SCENE-001`）、并排限高、`\graphicspath` 自动对齐
- **编译验证**：XeLaTeX 编译、Overfull 检测、`validate_tex.py` 规则级结构验证、`visual_verify.py` 视觉验证
- **pip 同款进度条**：`build.py` 编译时用 rich 渲染彩色进度条（粉色进行中 / 绿色完成），未装 rich 自动回退 tqdm 彩色条，再回退纯文本；输出重定向时自动关闭
- **环境检查**：执行前自动检查 XeLaTeX/pandoc/Python/MinerU 等环境，缺少时引导配置
- **MD→TEX 批量流水线**：`md2tex.py` / `md2ans.py` / `batch_convert.py` / `convert_new_papers.py` 等脚本批量把 MD 中间产物转换为试题/答案 tex
- **题库维护**：维护 `{题库根}`（环境变量 `SHIJUAN_LIBRARY`，默认 `D:\Music\试题加题库`）；每个含 tex 文件夹部署一键编译 `build.py`（通用版编全部 tex ×2；根目录只有 `main.tex` 时自动按书稿版编 3 遍；可从任意位置运行）
- **回归测试**：`tests/` 下 7 套测试（渲染器排版决策、md2tex 清洗规则、答题卡、一键收尾、tex 宽度），`python tests/run_all.py` 一键跑完

## 快速开始

### 前置条件

**通用依赖：**
- XeLaTeX（TeX Live / MiKTeX）
- Python 3.8+
- pandoc

**DOCX 输入额外依赖：**
- Pillow（`pip install Pillow`）— WMF→PNG 转换

**可选依赖：**
- rich（`pip install rich`）— `build.py` 的 pip 同款彩色进度条；未安装时自动回退 tqdm / 纯文本

**PDF 输入额外依赖：**
- MinerU SDK（`pip install mineru-open-sdk`）
- MinerU API Token（[获取地址](https://mineru.net/apiManage/token)）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/BluesilveEmperor/shijuan-paiban.git
cd shijuan-paiban

# 2. 安装通用依赖（rich 可选，用于 build.py 彩色进度条）
pip install Pillow rich

# 3. 如需 PDF 输入支持
pip install mineru-open-sdk
mkdir -p ~/.mineru
echo "token: '你的API密钥'" > ~/.mineru/config.yaml
```


> **注意**：MinerU API Token 请前往 https://mineru.net/apiManage/token 注册获取。

## 使用方法

### 三种入口

| 入口 | 适合场景 | 用法 |
|------|----------|------|
| **对话触发**（推荐） | 单份/少量试卷，自动跑完整流程 | 在 Claude / DevEco 中给出文件路径和需求 |
| **命令行** | 批量、自动化、调试单个步骤 | 直接调用 `scripts/` 下的脚本 |
| **IR 渲染** | 需要可复现的结构化排版 | 写 `paper.json` → `render_tex.py` |

> `{SKILL_DIR}` 指本仓库（`SKILL.md` 所在目录）。下面所有命令都在**试卷工作目录**执行，产物也写在这里。

### 1. 对话触发（最省事）

直接把文件拖进对话，或给出绝对路径，再说一句要做什么即可。技能会自动识别文件类型、试题/答案、模板，不需要手动指定。

#### 常用说法

| 需求 | 示例说法 |
|------|----------|
| 排版 DOCX 试卷 | `把 D:\试卷\2026模拟卷.docx 排版成 LaTeX，输出到同目录` |
| 排版 PDF 试卷 | `把 D:\试卷\2026模拟卷.pdf 转成 tex 并编译` |
| 排版答案 | `排版这个答案：D:\试卷\新一卷数学-答案.docx` |
| 生成答题卡 | `给 D:\试卷\2026模拟卷.tex 配一份 A4+A3 答题卡` |
| 只重编已有 tex | `重新编译 D:\试卷\2026模拟卷.tex，检查页数和 Overfull` |
| 调整页数 | `这份卷子要压到 4 页，帮我调一下` |
| 批量处理 | `把 D:\试卷\2025\ 下所有 docx 都排版了` |
| 错题/专题/周练 | `把这些错题整理成错题卷` / `排成专题卷` |

> 文件名含「答案」会自动使用答案模板；含「专题/专项」「周练/周测/周考」「错题/纠错/订正」会自动选择对应模板（见下文「模板系统」）。

#### 对话触发后技能会做什么

1. 检查 XeLaTeX / pandoc / Python / Pillow / MinerU 等环境。
2. 读取源文件：DOCX 用 pandoc + 内置 `extract_docx.py`；PDF 用 MinerU SDK。
3. 提取图片到 `Images-<卷名>/`，WMF/EMF 转 PNG。
4. 生成 `paper.json` 并用 `render_tex.py` 渲染（或按模板直接写 `.tex`）。
5. XeLaTeX 连编两遍，跑结构验证 + 视觉验证；页数不符时自动调 `itemsep` / 行距 / 边距。
6. `finalize_paper.py` 收尾：生成答题卡 → 部署 `build.py` → 编译清理 → 隐藏 `temp_scripts/`。

### 2. 命令行：完整流程

#### 2.1 DOCX → PDF

```bash
SKILL_DIR="/path/to/shijuan-paiban"   # 本仓库目录
WORK="/path/to/试卷目录"               # 建议与源文件同目录
DOCX="/path/to/2026模拟卷.docx"

cd "$WORK"

# 1) 先看结构：有文本就正常排版；只有图片说明是扫描件，需要走 OCR
pandoc "$DOCX" -t markdown --wrap=none --track-changes=all -o "2026模拟卷.md"

# 2) 解包取图（默认 Images-<文件名>/；WMF/EMF 转 PNG，600 DPI）
python "$SKILL_DIR/scripts/extract_docx.py" "$DOCX" "$WORK" --convert-wmf

# 3) 写 paper.json 后渲染（格式见 docs/ir-schema.md；--schema 可打印示例）
python "$SKILL_DIR/scripts/render_tex.py" paper.json -o "2026模拟卷.tex" --validate

# 4) 编译两遍（第二遍保证页码/目录/交叉引用正确）
xelatex -interaction=nonstopmode "2026模拟卷.tex"
xelatex -interaction=nonstopmode "2026模拟卷.tex"

# 5) 结构与视觉验证
python "$SKILL_DIR/scripts/validate_tex.py" "2026模拟卷.tex" --expected-pages 4
python "$SKILL_DIR/scripts/visual_verify.py" "2026模拟卷.pdf" --dpi 150

# 6) 页数不符时自动调整（按 itemsep → linespread → margin 顺序）
python "$SKILL_DIR/scripts/auto_adjust.py" "2026模拟卷.tex" --target-pages 4

# 7) 一键收尾：答题卡 + build.py + 编译清理 + 隐藏 temp_scripts
python "$SKILL_DIR/scripts/finalize_paper.py" "2026模拟卷.tex"
```

> 扫描件 DOCX（pandoc 只能提取 `![](media/imageN.png)`）先解包页面图，再用 MinerU OCR；命令见 `SKILL.md` 步骤 1-A。

#### 2.2 PDF → PDF

```bash
WORK="/path/to/试卷目录"
PDF="/path/to/2026模拟卷.pdf"
python "$SKILL_DIR/scripts/math_pdf_extract.py" "$PDF" --output-dir "$WORK/math-output" --language ch
# 扫描件加 --ocr；只解析部分页加 --pages 1-10
```

提取得到 Markdown + 图片后，从第 3 步开始同上（写 `paper.json` → 渲染 → 编译 → 验证 → 收尾）。

#### 2.3 答案文档

```bash
WORK="/path/to/试卷目录"
ANSWER="/path/to/新一卷数学-答案.docx"
python "$SKILL_DIR/scripts/extract_docx.py" "$ANSWER" "$WORK" --convert-wmf

# 写答案版 paper.json（meta.template = "answer"）后渲染
python "$SKILL_DIR/scripts/render_tex.py" answer.json -o "新一卷数学-答案.tex" --validate
python "$SKILL_DIR/scripts/finalize_paper.py" "新一卷数学-答案.tex" --skip-answersheet
```

- 答案文档不生成答题卡；`finalize_paper.py` 会自动识别文件名中的「答案」并跳过。
- 同一目录下已有试题 tex 时，可用 `match_paper.py` 查找对应关系：

```bash
python "$SKILL_DIR/scripts/match_paper.py" "$ANSWER" --json
```

#### 2.4 生成答题卡

```bash
# A4 + A3 两版一起生成（不加 --layout 时只出 A4）
python "$SKILL_DIR/scripts/gen_answer_sheet.py" "2026模拟卷.tex" --layout both

# 只要 A4，且暂时不编译
python "$SKILL_DIR/scripts/gen_answer_sheet.py" "2026模拟卷.tex" --layout a4 --no-compile

# 题量/分值解析不准时手动覆盖
python "$SKILL_DIR/scripts/gen_answer_sheet.py" "2026模拟卷.tex" --layout a4 \
  --single 8 --multi 3 --blanks 3 --solves "15/13,16/15,17/15"
```

- 从试卷 `.tex` 自动识别题量与分值；输出 `2611数学答题卡（A4）-<考试名>.tex/.pdf` 与 `（A3）` 版。
- `--force` 允许覆盖已有手工答题卡；`--bw` 黑白；`--print-spec` 只打印解析结果。

#### 2.5 只重编/调整已有 tex

```bash
cd "$WORK"

python build.py                 # 编译当前目录全部 *.tex ×2
python build.py "试卷.tex"       # 只编指定文件
python build.py --book          # 书稿根：只编 main.tex ×3
python build.py --times 3       # 自定义连编次数
python build.py --no-bar        # 关闭进度条
python build.py --keep-build    # 保留 _build/ 中间目录
```

`build.py` 以脚本所在目录为工作目录，可以从任意位置运行；根目录只有 `main.tex` 时会自动按书稿版编 3 遍。

#### 2.6 IR 最小示例

`paper.json`：

```json
{
  "meta": {
    "title": "2026 届高三模拟考试",
    "template": "gaokao",
    "total_pages": 4,
    "images_dir": "Images-2026模拟卷",
    "answer_space": "normal"
  },
  "sections": [
    {
      "heading": "一、选择题：本题共 1 小题，每小题 5 分，共 5 分。",
      "type": "choice_single",
      "questions": [
        {
          "stem": "已知集合 $A=\\{1,2\\}$，则 $A \\cup \\varnothing=$",
          "options": [
            {"label": "A", "text": "$\\varnothing$"},
            {"label": "B", "text": "$\\{1\\}$"},
            {"label": "C", "text": "$\\{2\\}$"},
            {"label": "D", "text": "$\\{1,2\\}$"}
          ]
        }
      ]
    }
  ]
}
```

渲染与检查：

```bash
python "$SKILL_DIR/scripts/render_tex.py" paper.json -o "试卷.tex" --validate
python "$SKILL_DIR/scripts/render_tex.py" paper.json --stdout   # 只看输出，不写文件
python "$SKILL_DIR/scripts/render_tex.py" --schema             # 打印完整字段说明
```

复杂 TikZ / 特殊表格用 `raw_tex` 逃生舱；其余尽量用 IR，编号、环境嵌套、图片场景、答题空间由渲染器统一决定。

#### 2.7 批量处理

```bash
# 收尾整个目录（处理目录内全部源 .tex；答案文档自动跳过答题卡）
python "$SKILL_DIR/scripts/finalize_paper.py" "/path/to/试卷目录"

# MD 批量转 tex（先 --help 看参数）
python "$SKILL_DIR/scripts/batch_convert.py" --help
python "$SKILL_DIR/scripts/convert_new_papers.py" --help
```

### 3. 输出位置与产物

所有产物写在**试卷工作目录**（源文件所在目录，或命令中显式指定的 `WORK`）：

| 产物 | 文件名 | 说明 |
|------|--------|------|
| 试卷 | `<卷名>.tex` / `.pdf` | 唯一版本（学生版/教师版已合并），含 `\answern` 答题空间 |
| 答题卡 | `2611数学答题卡（A4）-<考试名>.tex` / `.pdf` + `（A3）` | 试题卷才生成 |
| 图片 | `Images-<卷名>/` | 无图片时可缺席 |
| 编译脚本 | `build.py` | 收尾时自动部署 |
| 临时脚本 | `.temp_scripts/` | 隐藏保留，不属于交付产物 |

答案文档只出 `tex` / `pdf` + `Images-<卷名>/` + `build.py`，不生成答题卡。

### 4. 常用参数速查

| 脚本 | 常用参数 | 作用 |
|------|----------|------|
| `render_tex.py` | `-o`、`--template gaokao/answer`、`--validate`、`--schema` | IR → tex |
| `validate_tex.py` | `--expected-pages N`、`--is-answer`、`--quiet` | 规则级结构验证 |
| `visual_verify.py` | `--dpi 150`、`--output-dir DIR` | PDF → PNG 视觉检查 |
| `auto_adjust.py` | `--target-pages N`、`--max-rounds N` | 页数自适应 |
| `gen_answer_sheet.py` | `--layout a4/a3/both`、`--no-compile`、`--force`、`--bw` | 答题卡 |
| `finalize_paper.py` | `--force`、`--skip-answersheet` | 一键收尾；传目录处理全部 |
| `build.py` | `--book`、`--times N`、`--no-bar`、`--keep-build` | 批量/逐卷编译 |
| `math_pdf_extract.py` | `--output-dir`、`--ocr`、`--language ch`、`--pages 1-10` | PDF 提取 |
| `extract_docx.py` | `--convert-wmf`、`--dpi 600`、`--images-dir` | DOCX 解包取图 |

### 5. 使用提示

- **工作目录与临时脚本**：技能目录只读、`temp_scripts/` 生命周期见下方「运行时约定」。
- **Windows 编码**：PowerShell 下先执行 `$env:PYTHONIOENCODING='utf-8'`，避免中文/公式输出乱码。
- **页数**：把试卷标注页数写进 `paper.json` 的 `meta.total_pages`，验证时用 `--expected-pages`；不一致可跑 `auto_adjust.py`。
- **编译失败**：先看 `.log` 中以 `!` 开头的行和 `Overfull \hbox`，也可直接跑 `build.py` 看错误摘要。

## 运行时约定

- **技能安装目录只读**（`ACCESS-001`）：处理试卷期间不在 `{SKILL_DIR}` 内新建、修改、删除任何文件（含临时脚本、`paper.json`、`.tex`/`.pdf`、图片、日志、`__pycache__`）；所有可写内容只放试卷工作目录。调用脚本时建议设置 `PYTHONDONTWRITEBYTECODE=1`。
- **临时脚本集中存放**（`ACCESS-002`）：每卷一次性提取/转换/排版脚本统一放 `<试卷工作目录>/temp_scripts/` 并从该目录运行，不散落在试卷根目录；收尾时由 `finalize_paper.py` 自动重命名为 `.temp_scripts/`，Windows 下同时设置隐藏属性，资源管理器默认不可见。目录保留备查，不进入交付产物清单。

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
    ├── 答案文档 → 跳过答题卡
    └── 试题文档 → 生成答题卡（A4/A3）
    ↓
编译 → 验证（XeLaTeX × 2）
    ↓
清理辅助文件 → 隐藏 temp_scripts/（Windows 设置隐藏属性）
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

- **gaokao-template.tex**：高考数学试卷模板（唯一版本，含 `\answern` 答题空间）
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
| 答题卡 | 生成（A4/A3） | 不生成 |
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
| 分页/定位逻辑没生效 | Python 字符串必须用 raw string `r"\begin"` |
| 环境检查失败 | 按提示安装缺失依赖，必须项（XeLaTeX/pandas/Python）不可跳过 |
| 看不到 `temp_scripts/` | 收尾已重命名为 `.temp_scripts/` 并设置 Windows 隐藏属性；开启「显示隐藏的项目」或先 `attrib -h` 再改名 |
| 进度条没有颜色 | `pip install rich`（或 `tqdm`）；输出被重定向到文件时会自动关闭进度条 |

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
| `高考真题（模拟）卷\` | 190 个成卷文件夹（tex+答案+Images+build.py）+ 5 个年份目录（2022.6–2026.6，已补 build.py） |
| `考研数学真题卷\` | 18 个年份文件夹（2008年–2025年，数学一/二/三）+ 71 个 `2024-<大学>` 文件夹 + `题库\` 书稿工程 |
| `高三数学\` | 源材料 + `.math-output`（MD 中间产物） |

- **一键编译**：每个含 tex 的文件夹都有 `build.py`（通用版：编全部 tex ×2；根目录只有 `main.tex` 时自动按书稿版编 ×3），自动探测 xelatex（`shutil.which` → 各盘 `?:\texlive\*\bin\windows\` 探测，不写死路径），可从任意位置运行；终端显示 pip 同款彩色进度条
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
│   └── 试卷排版技能工作流与排版细节.{md,tex}
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
    ├── finalize_paper.py       # ★ 一键收尾（补齐产物集 + 部署 build.py + 编译清理 + 隐藏 temp_scripts）
    ├── hide_temp_scripts.py    # ★ temp_scripts/ → .temp_scripts/（Windows 隐藏属性；ACCESS-002）
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
- **rich（可选）**：`pip install rich` 启用 `build.py` 的 pip 同款彩色进度条；未安装时回退 tqdm / 纯文本

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 相关链接

- [MinerU 官网](https://mineru.net)
- [工作流与排版细节全解](docs/试卷排版技能工作流与排版细节.md) — 完整技能说明（含 [LaTeX](docs/试卷排版技能工作流与排版细节.tex) 源文件）
- [GitHub](https://github.com/BluesilveEmperor/shijuan-paiban/tree/math)
- [GitCode](https://gitcode.com/GLY-NXD/shijuan-paiban/tree/math)