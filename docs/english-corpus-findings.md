# 英语 52 套样本：从实例中沉淀的经验

> 数据源：`evals/fixtures_english/`（52 套 OCR md + 人工校准 tex + `_报告.txt` + `_质检.txt`）。
> 机器可读结果：`evals/fixtures_english/corpus_analysis.json`（含 16 条 EC 规则与逐卷特征）。
> 再生成：`python scripts/ops/analyze_english_corpus.py --check`（只读样本，重写 JSON 并跑门禁）。

## 1. 样本版图

| 指标 | 结果 |
|---|---|
| 总套数 | 52（编号 1–52，md/tex 一一对应） |
| 完整卷 / 无听力卷 | 47 / 5（无听力：4、15、29、34、51） |
| `\question` 数量 | 35 题 ×41 卷，34 题 ×4，33 题 ×2，15 题 ×5（无听力卷） |
| `\blanknum` 去重后数量 | 30 ×28 卷；29 ×9；28 ×5；27 ×3；≤25 ×7 |
| `\cz` 完形行数 | 15 ×45 卷，14 ×4，13 ×2，16 ×1 |
| `\writinglines` | `8+8` ×47 卷；缺失 ×2；仅一节 ×2；拆成 6 块 ×1 |
| `tabular` | 21 卷有表（15 卷 1 张、6 卷 2 张），源 md 均为 `<table>` |
| 图片 | md 7 处 / 3 卷（14、26、40），tex `\includegraphics` **0 处** |
| `\par` | 共 7824 个（约 150/卷），逐行断开的转换副产物 |
| 报告页数 | 22 卷记为 0（`pdfinfo` 失败），不可用于页数门禁 |

## 2. 题号地图（最重要的结构规律）

| 板块 | 题号 | 承载命令 | 备注 |
|---|---|---|---|
| 第一部分 听力 | 1–20 | `\question` + `choices(3)` | 1–5 短对话 5 题；6–20 长对话/独白 15 题 |
| 第二部分 阅读 | 21–35 | `\question` + `choices(2)` | A/B/C/D 三篇，各 5 题；`\passagelabel` 标 A/B/C/D |
| 第二部分第二节 七选五 | 36–40 | `choices(1)`（A–G）+ 文中 `\blanknum{36..40}` | **没有 `\question`**；质检「断档 36–40」属正常 |
| 第三部分第一节 完形 | 41–55 | `\cz{题号}{A}{B}{C}{D}` 每行一题；短文中可再有 `\blanknum{41..55}` | 题号双通道；短文空位缺失不算漏题 |
| 第三部分第二节 语法填空 | 56–65 | 文中 `\blanknum{56..65}` | 每空 1 题，共 10 题 |
| 第四部分 写作 | 66 / 67（不编号） | `\writinglines{8}` ×2（应用文 + 读后续写） | `Paragraph 1:` / `Paragraph 2:` 用 `\writingpara` |

**无听力卷**：注意事项明写「笔试不考听力，试卷从第二部分开始，试题序号从 21 开始」。
只有 3 个板块、题号 21–35、`choices(3)` 为 0。**不要补 1–20 题**。

## 3. OCR Markdown → LaTeX 的转换规律

| md 形态 | 目标 LaTeX | 经验 |
|---|---|---|
| `# <考试名>` / `# 英语` | `\examtitle{考试名}{英语}` | `#` 也用于文章标题与 passage 标题，**不能只看 heading 级别** |
| `注意事项：` + `1. …` | `notice` 环境 | 52 卷 md 都有，4 卷成品 tex 漏掉（5、8、10、31） |
| `## 第一部分 …` / `第X节（…）` | `\parttitle` / `\sectitle` | 标题有 16 种 part 写法、大量 sect 标点变体，须归一后再匹配 |
| `N. 题干` + 独立 `A. B. C.` 行 | `\question{N. …}` + `choices(3)` | 也有四选项挤在同一行的写法，需按行内 `A.…B.…` 再切分 |
| `41. A. … B. … C. … D. …` | `\cz{41}{…}{…}{…}{…}` | 完形固定 4 列；每卷 13–16 行，理想 15 |
| `\_\_\_\_41\_\_\_\_` / `\_41\_` | `\blanknum{41}` | MinerU 会转义下划线；共 1435 处，下划线数量 1–4 不等 |
| `<table>` | 两列 `tabular`，第二列 `p{…}` + 竖线 | 跨栏宽表需人工调列宽；保留 raw_tex 逃生舱 |
| `Paragraph 1: …` | `\writingpara` + `\writinglines{8}` | 作文两节固定，行数异常 5 卷 |
| `听第 N 段材料，回答第…题` | 普通 `\par` 段落 | 不是标题，不生成结构块 |
| `![](images/xxx.jpg)` | `\includegraphics` | **当前未实现**：7 处图片全部丢失 |

## 4. 16 条 EC 规则（摘要）

完整定义与证据在 `corpus_analysis.json` 的 `rules` 字段。

| ID | 经验 | 对实现的硬约束 |
|---|---|---|
| EC-001 | 卷式二分：完整卷 4 板块 / 无听力卷 3 板块 | 先判 variant，不凭空补题 |
| EC-002 | 题号地图（见第 2 节） | 按题号段分派块类型，不用全局计数器 |
| EC-003 | `choices` 列数由小节决定，数量会漂移 | 先读 part/section 再判题型 |
| EC-004 | 36–40 断档正常 | 缺 `\question` 不报错，只查 `\blanknum` |
| EC-005 | 完形题号双通道 | 以 `\cz` 为完形题量来源 |
| EC-006 | 填空缺号/重号常态化 | 只 WARN，禁止自动补题 |
| EC-007 | 写作区形态有 4 种变体 | IR 记「节次+行数」，渲染归一 |
| EC-008 | 表格来自 HTML `<table>` | 表格走 raw_tex，不强行结构化 |
| EC-009 | 图片全部丢失 | 图片卷暂不作为基准；补提取规则 |
| EC-010 | 水印/垃圾串/正文渗入标题 | md→IR 前加清洗层，sectitle 超长即异常 |
| EC-011 | 标题标点/写法变体多 | 用 `canon_part()` 归一后匹配 |
| EC-012 | `\par` 是换行副产物 | IR 不保留 `\par`，由渲染器生成段落 |
| EC-013 | 22 卷报告页数为 0 | 页数门禁改为实时编译 + pdfinfo |
| EC-014 | 本批没有答案卷 | 答案流水线需另采样本 |
| EC-015 | md/tex 文件名不可互推 | 一律读 manifest |
| EC-016 | 听力例题无题号（`例：How much is the shirt?`） | 题量统计含例题，题号集合排除 |

## 5. 异常卷清单（实现时的排除/告警依据）

| 异常 | 卷编号（1-based） |
|---|---|
| 无听力（合法变体） | 4, 15, 29, 34, 51 |
| 听力无题号例题 | 2, 9, 20, 21, 24, 27 |
| 图片丢失 | 14, 26, 40（7 处图） |
| 公众号水印渗入标题 | 5, 6, 14, 17, 19, 22, 23, 25, 26, 33, 34, 37, 46, 47, 50, 51 |
| `ladnepen` 垃圾串 | 36, 38, 41, 42, 45 |
| 正文整段混入 sectitle | 36 |
| `notice` 缺失 | 5, 8, 10, 31 |
| `\blanknum` 缺号 | 2, 3, 4, 7, 9, 10, 17, 19, 21, 28, 30, 32, 33, 34, 35, 38, 39, 40, 41, 44, 47, 48 |
| `\blanknum` 重号 | 5, 7, 31 |
| 选项块数量漂移 | 2, 5, 6, 9, 10, 12, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 37, 40, 43, 45, 46, 49, 50 |
| 完形行数 < 15 | 6, 12, 16, 18, 26, 33 |
| 写作行数异常 | 16, 18, 19, 31, 42 |
| 报告页数为 0 | 31–52（22 卷） |

典型漂移：43 卷为 `choices(3)=22 / choices(2)=13`（2 道阅读题被识别成听力列数）；
02 卷七选五被拆成 5 项 + 7 项两个 `choices(1)`。
**结论：选项数量不能作为题型判据，必须依赖小节上下文。**

## 6. 对后续实现的建议

### 6.1 IR 块类型（已从 52 份成品反推并实现）

实际落地的 12 种 block：
`exam_title` / `para` / `notice` / `part` / `section` / `question` / `choices` /
`cloze` / `passage_label` / `writing_para` / `writing_lines` / `raw`。

- `question` 只用于 1–35（或 21–35）；`例：` 开头的听力例题无题号（EC-016），
  计入题量但不进题号集合。
- `\blanknum` 36–65 **嵌在 `para.text` 内**，块内 `blanks` 字段记录题号，不单独成块。
- `choices` 带 `columns` 字段（3/2/1）与 `indent`，由 section 决定，不从选项数猜。
- `cloze` 每行一题，字段 `number + 4 options`。
- `writing_para` + `writing_lines` 两块配对，`writing_lines.count` 通常是 8。
- 表格等复杂结构整块进 `raw.lines`，逐字保留；图片先标记 `image_loss`，暂不生成块。

### 6.2 基准分层

严格排除所有硬异常后，只剩 **5 套干净卷：1、11、13、15、29**（均不含表格）。
建议分三层使用：

- **A 层（5 套）**：做 `tex → IR → tex → PDF` 精确往返（已实现，见第 8 节）。
- **B 层（无图片、无标题污染者）**：做结构回归（板块序列、题号段、环境配对）。
- **C 层（其余）**：只做清洗/告警规则的负例，不做逐字节基准。

### 6.3 落地顺序

1. ✅ `tex2english.py`（保真反解）+ `render_english.py`（确定性渲染）→ IR schema 已定。
2. ✅ 52/52 套 `tex → IR → tex` 逐字节往返；A 层 5 套渲染结果真编译通过。
3. 实现 `md2english.py` + 清洗层（水印、`ladnepen`、sectitle 正文泄漏、转义下划线），
   以 52 份成品 tex 为监督目标；按 EC-002/003/004/016 分派块，缺号只告警。
4. 补图片提取与 `\includegraphics` 规则后，把 14/26/40 纳入基准。
5. 另采答案卷样本，补 `[answers]` 模式与评分细则回归。

## 7. 门禁

`python scripts/ops/analyze_english_corpus.py --check` 已把以下不变量固化：
样本 52 套、文档类正确、环境配对、题号起号 1/21、板块序列、题号数量、
blanknum 值域 36–65、cz 不少于 13 行、阅读/七选五选项块存在、编译报告 2/2。
`python tests/test_english_corpus_rules.py` 在回归套件中复用同一门禁。

## 8. IR 往返已落地

```bash
python scripts/render/tex2english.py evals/fixtures_english/tex/01_2402武汉二调.tex -o english.json
python scripts/render/render_english.py english.json --compare-with evals/fixtures_english/tex/01_2402武汉二调.tex
python tests/test_english_roundtrip.py --compile
```

- **52/52 套**成品 tex 经 `tex → IR → tex` 逐字节一致——证明 12 种块足以无损表达这批样本。
- A 层 5 套的 IR 基准在 `evals/fixtures_english/ir/`，渲染结果均能独立 XeLaTeX 编译。
- 最关键的保真点：`para` 保留 `\par … \par` 原文与行内 `\blanknum`；
  `choices` 保留列数与两空格缩进；`raw` 整块保留表格；`preamble` / `postamble` 原样带出。
- 校验器缺号只告警（EC-006 / EC-016），不会为了「补齐」而改动题量。

## 9. OCR Markdown → IR 已落地

```bash
python scripts/render/md2english.py evals/fixtures_english/md/01_2402武汉二调.md -o english.json
python scripts/render/eval_md2english.py               # 52 套保真度指标
python scripts/render/eval_md2english.py --detail 9    # 单卷差异
python tests/test_md2english.py                        # 清洗/结构/保真度门禁
```

三段式：`english_clean.py`（清洗）→ `md2english.py`（解析）→ `eval_md2english.py`（评估）。
以 52 套成品 tex 的 IR 为监督目标，逐卷比对 q/blank/cloze/part/section/notice/passage/cols/blocks。

从 md 侧反推、在解析器中新增的两条**实现层规则**（区别于语料分析器沉淀的 EC-001~016）：

| ID | 经验 | 落地方式 |
|---|---|---|
| EC-017 | 监督 IR 中 1718/1718 个 `question` 后必跟 `choices` | 据此修正 OCR 误判：无选项编号条款降级为 `para`；被识成题号的选项（如 `3. By taxi.` 夹在 `A./C.` 间）还原并合并 |
| EC-018 | 七选五/语法填空的 OCR 常丢 `\_` 标记，只剩裸数字 | 在该 section 上下文内（`共5小题2.5分`→36–40、`共10小题1.5分`→56–65）把独立裸数字补成 `\blanknum` |

其他关键实现规律：`choices` 列数按 section 题型推断（听力 3 / 阅读 2 / 七选五 1，见 EC-003）；
完形选项可同行 4 项 / 首项同行其余续行 / 被 OCR 识成题号，题号固定 41–55（EC-002/005）；
水印「微信公众号 IAI English」有带空格与不带空格两种形态，须整串清洗（EC-010）。

保真度现状与「差异为何可接受」的说明见
[docs/english-branch.md](docs/english-branch.md)「OCR Markdown → IR 流水线」一节。
核心结构 exact：题号 48/52、part 52/52、notice 52/52、passage 51/52、填空 44/52、完形 45/52。
