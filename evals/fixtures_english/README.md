# 英语回归样本（52 套）

`english` 分支的训练/回归样本集：52 份高中英语试题的 OCR Markdown 与人工校准后的 LaTeX 成品。

## 目录

| 路径 | 内容 |
|---|---|
| `manifest.json` | 52 套卷的权威索引：编号、考试名、md / tex 文件名、外部原卷 PDF 相对路径 |
| `corpus_analysis.json` | 从 52 套样本沉淀的经验库：逐卷特征、异常标记、汇总统计、16 条 EC 规则；由 `scripts/ops/analyze_english_corpus.py` 生成 |
| `ir/*.english.json` | A 层 5 套干净卷的块流 IR 基准（1、11、13、15、29） |
| `md/*.md` | MinerU `vlm` 精准模式 OCR 的原始 Markdown（52 份）+ `_progress.txt` |
| `tex/*.tex` | 转排后的 XeLaTeX 源（52 份），与 `md/` 一一对应 |
| `tex/英语试卷.cls` / `英语试卷.sty` | 编译时随卷的模板快照，应与 `templates/english/` 逐字节一致 |
| `_报告.txt` / `_质检.txt` | 原始转排的题量、页数、编译结果与题号连续性检查 |
| `SOURCE_README.md` | 源目录 `52份转排/README.md` 原文：MD→TEX 识别规则与已知人工核对项 |

## 命名差异（重要）

`md/` 保留原考试名里的 `+` 和空格，`tex/` 把它们替换成 `_`：

- `md/08_2411浙江9+1高二期中考.md` → `tex/08_2411浙江9_1高二期中考.tex`
- `md/11_2412  3+3+3.md` → `tex/11_2412_3_3_3.tex`

**不要用字符串替换猜映射**，一律读 `manifest.json`。

## 原卷 PDF

原卷与答案 PDF 共约 1.4 GB，**不入库**。根目录默认 `D:/Documents/01_Study_Research/高中英语`，
可用环境变量 `SHIJUAN_ENGLISH_CORPUS` 覆盖；具体相对路径见 `manifest.json` 的
`source_dir` / `source_pdf` / `source_answer_pdf`。

模板本体在 `templates/english/`；答题卡模板与两个 A4 样例在
`templates/english/answer-sheet/`。

## 编译单卷

```bash
cd evals/fixtures_english/tex
xelatex -interaction=nonstopmode 01_2402武汉二调.tex
xelatex -interaction=nonstopmode 01_2402武汉二调.tex   # 页脚「共 N 页」需连编两次
```

## 经验沉淀

```bash
python scripts/ops/analyze_english_corpus.py --check   # 重新生成 corpus_analysis.json + 跑不变量门禁
python tests/test_english_corpus_rules.py             # 回归门禁
```

结论与异常卷清单见 [docs/english-corpus-findings.md](../../docs/english-corpus-findings.md)：
题号地图、md→tex 映射、16 条 EC 规则、A/B/C 三层基准（A 层干净卷：1、11、13、15、29）。

IR 往返（已实现）：

```bash
python scripts/render/tex2english.py tex/01_2402武汉二调.tex -o english.json
python scripts/render/render_english.py english.json --compare-with tex/01_2402武汉二调.tex
python tests/test_english_roundtrip.py --compile
```

52/52 套 tex 逐字节一致；A 层 5 套渲染结果可独立编译。

## 状态

- 已入库：模板、52 套 md/tex、质检记录、索引、样本经验库、A 层 IR 基准。
- 已实现：`english.json` 块流 IR、`tex2english.py` / `render_english.py` 往返、编译门禁。
- 未实现：`md2english.py`（OCR→IR）、批量流水线、答案卷流水线、图片提取。
  当前 `tex/*.tex` 是人工校准后的成品，用作 OCR→IR 实现的**目标基准**，不是流水线输出。
- 已知局限见 `SOURCE_README.md`：OCR 选项丢失、作文作答行数估算、跨栏宽表列宽、
  七选五 36–40 题号埋在短文中导致质检「断档」属正常。
