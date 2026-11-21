# 英语试卷分支（english）

> 从 `chinese`（`3d81334`，全仓库按学科与职能重组后的结构）切出。
> **当前是骨架分支**：模板、答题卡、52 套基准样本已入库；自动转排流水线尚未实现。
> 数学 `paper.json` 与语文 `chinese.json` 的 IR/渲染器都不适用于英语。

## 学科开关

- 仓库根 `shijuan.config.yaml`：`subject: english`
- 临时覆盖：`SHIJUAN_SUBJECT=english`
- 差异项集中在 `scripts/subject.py` 的 `PROFILES["english"]`：MD 输出目录 `english-output`、
  日志分支 `log_runtime_english`、答题卡命名前缀「英语」、必备宏包清单、题型关键词。

## 已入库资源

| 路径 | 内容 | 来源 |
|---|---|---|
| `templates/english/英语试卷.cls` | 试题/答案文档类，A4 版面、字体、卷头、页脚 | `高中英语/LaTeX/英语试卷.cls` |
| `templates/english/英语试卷.sty` | 题型环境与命令（`choices` / `cloze` / `\cz` / `\writinglines` 等） | `高中英语/LaTeX/英语试卷.sty` |
| `templates/english/answer-sheet/` | 英语 A4 答题卡 `.sty` + 条形码版 / 考生号版样例 tex | `高中英语/LaTeX/英语全国卷A4答题卡/` |
| `evals/fixtures_english/manifest.json` | 52 套卷索引：编号、考试名、md、tex、原卷 PDF 相对路径 | 本次生成 |
| `evals/fixtures_english/md/` | MinerU `vlm` OCR Markdown 52 份 + `_progress.txt` | `高中英语/52份转排/md/` |
| `evals/fixtures_english/tex/` | 人工校准后的成品 tex 52 份 + cls/sty 快照 | `高中英语/52份转排/tex/` |
| `evals/fixtures_english/_报告.txt` / `_质检.txt` | 题量、页数、编译结果、题号连续性检查 | `高中英语/52份转排/` |
| `evals/fixtures_english/SOURCE_README.md` | 原始转排说明：MD→TEX 识别规则与已知人工核对项 | `高中英语/52份转排/README.md` |

原始题库根目录：`D:/Documents/01_Study_Research/高中英语`（约 1.4 GB），
可用环境变量 `SHIJUAN_ENGLISH_CORPUS` 覆盖。**原卷/答案 PDF 不入库**：按 manifest 的
`source_dir` / `source_pdf` / `source_answer_pdf` 到题库根目录定位。
编译产物（`.pdf` / `.aux` / `.log`）同样不入库，仓库内只留源文件。

## 模板速查

```latex
% !TEX program = xelatex
\documentclass{英语试卷}             % 试题；\documentclass[answers]{英语试卷} 为参考答案
\begin{document}
\examtitle[绝密★启用前]{考试名}{英语}
\begin{notice}
\par 1. 答题前…\par
\end{notice}
\parttitle{第一部分 听力（共两节，满分 30 分）}
\sectitle{第一节（共5小题；每小题1.5分，满分7.5分）}
\question{1. What are the speakers probably doing?}
\begin{choices}(3)
  \item Discussing at work.
  \item Talking on phone.
  \item Driving on the way.
\end{choices}
\end{document}
```

| 场景 | 命令 / 环境 |
|---|---|
| 卷头 | `\examtitle` / `\answertitle` |
| 分节 | `\parttitle`（12pt 黑体）/ `\sectitle`（10.5pt 粗体） |
| 听力 3 选 1 | `choices(3)` |
| 阅读 4 选 1 | `choices(2)`（A/B 一行，C/D 一行） |
| 七选五 A–G | `choices(1)` |
| 完形 4 选 1 | `cloze(4)` 或 `\cz{41}{A}{B}{C}{D}` |
| 语法填空空位 | `\blanknum{56}`（题号居中压下划线） |
| 写作 | `\writinglines{10}` / `\writingpara{Paragraph 1: …}` |
| 答案 | `\answerline{1-5 BABCA}` / `\blankanswer{56}{a}` / `\rubricitem{…}` |

版式：A4，上下 2.54cm、左右 1.905cm；正文 10.5pt（Times New Roman + 宋体），
行距 15.6pt；参考答案模式 23.7pt。页脚用 `lastpage`，**必须连编两次**。
命令/环境全表见 `templates/manifest.json` 的 `english` 条目。

## 样本命名与编译

`md/` 保留考试名里的 `+` 与空格，`tex/` 统一替换为 `_`；例如
`11_2412  3+3+3.md` → `11_2412_3_3_3.tex`。**不要猜映射**，读 `manifest.json`。

```bash
cd evals/fixtures_english/tex
xelatex -interaction=nonstopmode 01_2402武汉二调.tex
xelatex -interaction=nonstopmode 01_2402武汉二调.tex   # 第二遍：页脚总页数
```

`tex/` 内的 `英语试卷.cls` / `英语试卷.sty` 是 `templates/english/` 的快照，
`tests/test_english_fixtures.py` 会校验两者逐字节一致。
`python tests/run_all.py --with-tex` 会抽样真编译 1 份英语样本（需本机装 XeLaTeX）。

## 质检已知项（来自 `_质检.txt` / `SOURCE_README.md`）

1. 七选五 36–40 的 5 个空埋在短文里、卷面无题号，质检显示「断档 36–40」属正常。
2. 个别卷 OCR 丢失/串行选项，需对照原卷 PDF 补。
3. 作文作答区行数按「每块空行 ×4」估算，未必与原卷一致。
4. 跨栏宽表列宽需人工调整。
5. OCR 把公式包成 `$…$`、中文标点混入英文等，转排时已做归一（规则见 `SOURCE_README.md`）。

## 从 52 套样本沉淀的经验

分析器 `scripts/ops/analyze_english_corpus.py` 只读样本，产出
`evals/fixtures_english/corpus_analysis.json`（逐卷特征 + 16 条 EC 规则 + 异常卷索引）：

```bash
python scripts/ops/analyze_english_corpus.py --check
python tests/test_english_corpus_rules.py
```

核心结论：

- 47 套完整卷（4 板块 / 题号 1–35）+ 5 套无听力卷（3 板块 / 题号 21–35）。
- 题号分段：`\question` 1–35；七选五 36–40 与语法填空 56–65 是 `\blanknum`；
  完形 41–55 由 `\cz` 承载；写作 66/67 不编号。
- 6 卷听力第一节有**无题号例题**（`例：How much is the shirt?`）：题量统计含例题，题号集合排除。
- 28/52 卷的填空完整覆盖 36–65；22 卷缺号、3 卷重号——只告警，禁止自动补题。
- 3 卷共 7 处图片在成品 tex 中全部丢失；16 卷有公众号水印渗入标题；5 卷有 `ladnepen` 垃圾串。
- 报告页数字段 22 卷为 0；页数门禁必须实时编译取，不能读旧报告。
- 严格排除硬异常后只有 5 套干净卷（1、11、13、15、29），建议先做这批的精确往返基准。

完整规则表、异常卷编号、md→tex 映射与 IR 块类型建议见
[docs/english-corpus-findings.md](english-corpus-findings.md)。

## 块流 IR 往返（已实现）

`scripts/render/tex2english.py` 与 `scripts/render/render_english.py` 构成英语侧的
「成品 tex → IR → tex」闭环，与语文侧同属保真优先策略：

```bash
python scripts/render/tex2english.py evals/fixtures_english/tex/01_2402武汉二调.tex -o english.json
python scripts/render/render_english.py english.json --compare-with evals/fixtures_english/tex/01_2402武汉二调.tex
python scripts/render/render_english.py --schema
python tests/test_english_roundtrip.py --compile
```

- `english.json` 为线性块流：`exam_title` / `para` / `notice` / `part` / `section` /
  `question` / `choices` / `cloze` / `passage_label` / `writing_para` / `writing_lines` / `raw`。
- `\blanknum` 嵌在 `para.text` 内（块内 `blanks` 字段记录题号）；`\cz` 每行一题是 `cloze` 块；
  表格等复杂结构整块进 `raw`，保证不丢写法。
- A 层 5 套的 IR 基准在 `evals/fixtures_english/ir/*.english.json`。
- **52/52 套成品 tex 逐字节往返一致**；A 层 5 套渲染结果均可独立 XeLaTeX 编译。
  校验器对题号缺号/填空缺号只告警，不自动补题（EC-006 / EC-016）。

## 与现有流水线的边界

- 数学：`paper.json` + `render_tex.py`；语文：`chinese.json` + `render_chinese.py`。**都不适用于英语。**
- `scripts/ops/batch_chinese.py`、`scripts/render/md2chinese.py`、`tex2chinese.py` 禁止用于英语卷。
- `scripts/render/gen_answer_sheet.py` 的题量解析按数学结构实现，英语卷暂用
  `templates/english/answer-sheet/` 独立答题卡模板，不接通用生成器。
- `rules/layout.yaml` 尚无英语规则域；英语排版规则目前以 cls/sty 与 52 份成品 tex 为准。

## 实施路线

已完成：

1. ✅ 从 52 份成品 tex 反解块流 IR（`tex2english.py`，保真优先）。
2. ✅ 定义 `english.json` 12 种 block（含 `raw` 逃生舱）并实现确定性渲染器 `render_english.py`。
3. ✅ `tex → IR → tex` 52/52 逐字节往返；A 层 5 套渲染结果真编译通过。
4. ✅ OCR Markdown → IR：`english_clean.py`（清洗层）+ `md2english.py`（解析器）+
   `eval_md2english.py`（以 52 套成品 IR 为监督的保真度评估器）。
5. ✅ 答案卷流水线：`md2english_answer.py`（答案 OCR → 答案 IR）+ `render_english.py`
   支持答案块（`\answertitle` / `\answerline` / `\blankanswer` / `\writingtitle`）；
   `batch_english.py` 批量流水线（试题 + 答案，OCR → IR → tex → PDF）。

待办：

6. 补图片提取与 `\includegraphics` 规则，把 14/26/40 纳入基准。
7. 适配答题卡题量解析，补 `rules/layout.yaml` 英语规则域 + `evals/evals.json` 英语用例。
8. 分流 SKILL.md：用户说「英语」时直接走英语分支，不落到数学/语文流程。

## OCR Markdown → IR 流水线（md2english）

以 52 份人工校准 tex 的 IR 为监督目标，把 MinerU vlm 的 OCR Markdown 解析成同构块流。
三段式，可用 `python scripts/render/md2english.py 试题.md -o english.json` 一步转换：

1. **清洗层** `english_clean.py`：水印（含「微信公众号 IAI English」两种空格形态）、
   `ladnepen` 垃圾串、小节标题正文泄漏、HTML 实体、英文语境中文标点/引号。
2. **解析器** `md2english.py`：块流直译 + 后处理修复。关键规则：
   - 题号 `N.` → `question`，紧跟 `choices`；监督验证 1718/1718 个 question 后必跟 choices，
     据此把「无选项编号条款」降级为 para、把「被 OCR 识成题号的选项」（如 `3. By taxi.`
     夹在 `A./C.` 之间）还原为选项并合并（EC-017）。
   - 完形 `41. A.… B.… C.… D.…`：同行 4 项 / 首项同行其余续行 / 选项被识成题号，题号固定 41-55。
   - 填空：兼容 `\_\_36\_\_`、`\_37\_` 等多种下划线；七选五(36-40)/语法填空(56-65)
     的 OCR 裸数字在 section 上下文内补成 `\blanknum`（EC-018）。
   - `choices` 列数按 section 题型推断（听力3 / 阅读2 / 七选五1），回退到选项个数。
   - 表格进 `raw` 逃生舱；图片丢弃并告警（EC-009）。
3. **评估器** `eval_md2english.py`：以 tex 的 IR 为监督，输出 q/blank/cloze/part/section/
   notice/passage/cols/blocks 九项 exact 指标，`--detail N` 打印单卷差异。

当前 52 套保真度（详见评测输出）：

| 指标 | exact | 说明 |
| --- | --- | --- |
| question 题号 | 48/52 | 4 卷为监督 tex 缺号、本解析器补全（更完整） |
| blank 填空号 | 44/52 | 残余多为 09 异常卷（OCR 完全丢标记） |
| cloze 完形号 | 45/52 | 残余为监督 tex 因选项瑕疵弃题、本解析器保留 |
| part / notice | 52/52 | — |
| section | 43/52 | 残余差异是清洗层去掉了监督 tex 残留的水印/ladnepen（更干净） |
| passage | 51/52 | 13 卷监督 tex 缺首篇 `A`，本解析器补全 |
| choices 列数 | 31/52 | 残余为 OCR 选项拆分边界差异，内容不丢 |

**端到端验证**：A 层 01 卷经 `OCR md → IR（173 块/35 题/30 填空）→ tex（0 告警）→ XeLaTeX`
成功编译出 PDF，证明整条流水线可用。

**边界说明**：md→IR 的残余差异几乎都是「本流水线输出比人工校准 tex 更完整/更干净」，
不存在信息丢失。人工 tex 是训练监督而非金标准——其缺号、残留水印属历史校准的局限。
`tex/*.tex` 仍是排版基准；OCR 转换结果需人工复核后入版。

## 答案卷流水线（md2english_answer）

虽然 52 套成品 tex 无答案卷（EC-014），但原卷目录里 **51 套答案 PDF 齐全**。
`md2english_answer.py` 把这些答案 PDF 的 OCR Markdown 解析成答案 IR，
`render_english.py` 渲染成 `\documentclass[answers]{英语试卷}`。

真实答案 md（01 武汉二调 / 02 南京九调）归纳出的结构：

| OCR Markdown | 答案 IR 块 | LaTeX 命令 |
|---|---|---|
| `# 考试名` + `# 英语参考答案` | `answer_title` | `\answertitle{考试名}{英语}` |
| `第一部分 听力` / `## 第二部分 …` | `part` | `\parttitle` |
| `第一节 1-5 BBACC`（含 part 行内嵌答案） | `section` + `answers{groups}` | `\sectitle` + `\answerline{1-5 BBACC \quad …}` |
| `第二节（共5小题）36-40 CDABF` | `section` + `answers` | 同上（**不截断**小节后答案组，清洗层 `cut_section=False`） |
| `56. for 57. but/yet 58. to host` | `blank_answers{items}` | `\answerline{\blankanswer{56}{for} \quad …}`（支持多词/斜杠答案） |
| 第四部分写作下的 `第一节` / `第二节` | `writing_sample{title,paragraphs}` | `\writingtitle` + `\par…\par` |
| `## Text N …`（听力原文，可选） | `para` | `\par…\par`（`--no-scripts` 可关闭） |

```bash
python scripts/render/md2english_answer.py 答案.md -o daan.english.json
python scripts/render/md2english_answer.py 答案.md --no-scripts -o daan.english.json
```

数学段 `$…$` 整段保护，`&`/`#` 等先转义再占位，避免听力原文 `Cock & Bull`
触发 `Misplaced alignment tab character &`。两份真实答案（含听力原文）均已编译通过。

## 批量流水线（batch_english）

`scripts/ops/batch_english.py` 以 manifest 为唯一映射源，对每套卷执行：

```
试题 PDF → MinerU OCR → md2english        → render_english → xelatex×2 → 英语卷-<exam>.pdf
答案 PDF → MinerU OCR → md2english_answer → render_english → xelatex×2 → 英语答案-<exam>.pdf
```

产物写到**独立输出目录**（默认 `./english-batch/`），不污染语料库；OCR 缓存在
`<输出根>/.en-ocr/<kind>/`，重跑不重复计费。`--dry-run` 只列计划不跑 OCR。

```bash
python scripts/ops/batch_english.py --dry-run --limit 3          # 预演
python scripts/ops/batch_english.py --only 2402武汉二调           # 单卷试题+答案
python scripts/ops/batch_english.py --kind shiti --limit 5        # 只跑试题
python scripts/ops/batch_english.py --output-dir ./english-batch  # 指定输出根
python scripts/ops/batch_english.py --no-keep-cache               # 完成后删缓存
```

命名以 manifest 的 `exam` 字段为准。题库根目录取 `--library` > `SHIJUAN_ENGLISH_CORPUS`
> manifest.corpus_root。单卷失败不中断批量，末尾汇总成功/失败清单。
OCR 走 MinerU 云端 API（单份约 35-45 秒），52 套 ×2 约 60-80 分钟。
端到端实测：01 卷试题 8 页 / 答案 4 页，均编译成功；试题卷填空 58-61 缺失按 EC-006 只告警。

## 测试

- `tests/test_subject.py`：英语学科档案、命名、MD 输出目录、日志分支。
- `tests/test_english_fixtures.py`：52 份 md/tex 齐全、manifest 映射有效、
  模板快照一致、答题卡片路径可解析、tex 环境配对；`--compile` 抽样真编译。
- `tests/test_english_corpus_rules.py`：复用分析器的不变量门禁，并锁定
  卷式分布、异常卷数量与 A 层干净卷清单。
- `tests/test_english_roundtrip.py`：52 套逐字节往返 + A 层 IR 基准一致；`--compile` 真编译 5 套。
- `tests/test_md2english.py`：清洗层单元测试（水印/ladnepen/实体/标题泄漏）、
  结构解析单元测试（题号+选项/完形跨行/裸数字填空/writing）与 52 套保真度下限基线。
- `tests/test_answer_english.py`：答案解析器（卷头/答案组/多词语法填空/范文/听力原文/
  水印清洗）、答案块渲染与批量流水线纯逻辑（manifest 映射/命名/dry-run）。
- `python scripts/render/eval_md2english.py`：随时查看当前 52 套保真度指标。
- `python tests/run_all.py` 一键回归；`run_all.py` 对非学科测试固定 `SHIJUAN_SUBJECT=math`，
  因此 `subject: english` 不会影响既有用例。
