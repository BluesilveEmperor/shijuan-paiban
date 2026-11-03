# 试卷 → LaTeX 转换规则

> 本文档由 SKILL.md 引用，包含逐题转换时的详细规则与 LaTeX 示例。
>
> **规则数值的唯一权威定义在 [`rules/layout.yaml`](../rules/layout.yaml)。**
> 下文的规则表由 `scripts/gen_rules_doc.py` 自动生成，请勿手改生成区块；
> 需要改规则时编辑 YAML 后运行 `python scripts/gen_rules_doc.py`。

## 输入类型判断

### 扫描件 DOCX 识别

当 pandoc 输出仅包含 `![](media/imageN.png)` 图片标记而无文本内容时，判定为扫描件 DOCX
（见 `EXTRACT-002`）。此时直接采用 MinerU SDK 对每张页面图片进行 OCR 识别，输出 Markdown 包含 LaTeX 公式。

---

## 规则总表

<!-- RULES:BEGIN full -->
<!-- 本区块由 scripts/gen_rules_doc.py 从 rules/layout.yaml 生成，请勿手改 -->

### 结构约束

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `STRUCT-ENV-001` | 选择题外层容器 | 外层 enumerate + 内层 tasks | 禁止：单独使用 tasks 作为题目列表容器<br>tasks 环境无编号能力，单独使用导致题目无序号 |
| `STRUCT-ENV-002` | 解答题环境 | examenum | 模板以 newlist 定义三级嵌套 examenum，普通 enumerate 无法复用模板缩进体系 |
| `STRUCT-BLANK-001` | 填空题空位 | \blank（模板已定义，下划线 2cm） | 自造下划线导致同一份试卷内空位宽度不一致 |
| `STRUCT-GLYPH-001` | 圈号字符 ①-⑩ 字形映射 | 导言区用 newunicodechar 把 ①-⑩ 映射到 \mycircled | ctexart 默认字体缺 ①-⑩ 字形，直接写会静默丢字——题干「如图①②③所示」渲染成「如图 所示」且编译不报错（ir_geometry 实测） |

### 图片排版

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `IMG-W-001` | 单张图片宽度硬上限 | 0.35\textwidth | 超过 0.35 时图注被挤出页边（2024 新课标Ⅱ卷第 19 题实测） |
| `IMG-W-002` | 单张题目配图默认宽度 | 0.30\textwidth | 0.30 在 4 页卷中留出足够文本环绕空间，与 IMG-W-001 的硬上限不冲突 |
| `IMG-W-003` | 并排图片宽度与高度 | 2 张并排：minipage 0.42\textwidth，图高 3cm<br>3 张并排：minipage 0.28\textwidth，图高 2.5cm | 并排不限高时三视图会把整道题顶到下一页 |
| `IMG-W-004` | 选项图片宽度 | 0.12\textwidth | 4 × 0.12 = 0.48，为 label 与 column-sep 留出余量 |
| `IMG-ALIGN-001` | 图片对齐方式 | \centering | 禁止：`\raggedleft`<br>raggedleft 使图注与图片左边缘错位，图注必须居中于图片正下方 |
| `IMG-SCENE-001` | 图片场景选择 | 小装饰图（行内） → \includegraphics[height=0.6em]<br>列表内单图（无论有无子问） → minipage 左右并排（0.62 文字 + 0.30 图片）<br>图片作为选项 → tasks(4)，图宽 0.12\textwidth<br>图片与长选项并排 → minipage 左选项右图片<br>多张图片并排 → figure[H] + minipage，必须限高<br>TikZ 图 → \resizebox{0.35\textwidth}{!}{...}<br>图片位于 \\begin{examenum} 之前（列表外） → wrapfigure{r}{0.30\textwidth} 右侧环绕 | 实测 wrapfigure 放在 examenum 列表内会静默丢图——图片完全不渲染且编译不报错（evals/fixtures/ir_geometry 第 2 题）。因此列表内单图一律走 minipage，wrapfigure 仅限列表外场景 |

### 选项排版

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `TASKS-COL-001` | tasks 列数判定 | 含图片且平均长度 < 80 字符 → 4 列<br>含图片且平均长度 ≥ 80 字符 → 2 列<br>平均可见长度 > 25 字符（含公式或纯文字） → 2 列<br>默认（简短选项，含短公式如 $\{0\}$） → 4 列 | 原规则「含公式即 2 列」会把 $\{0\}$ 这类短选项也判成 2 列，与真实试卷排版不符（evals/fixtures/standard 实测）；改为只看可见长度 |
| `TASKS-COL-002` | 禁止竖排图片选项 | 禁止图片选项使用 tasks(1) | 图片竖排浪费半页空间，且与相邻题目间距失衡。注：纯文字选项因单个选项过长而用 tasks(1) 不受此限（见 TASKS-COL-003） |
| `TASKS-COL-003` | 宽度兜底——放不下就退列 | 意图列数的单列宽度放不下最长选项 → 退到 2 列<br>2 列仍放不下 → 退到 1 列（纯文字选项允许） | 只按字符数判列会低估不可断行公式的真实宽度。实测 $\dfrac{\tanh x+\tanh y}{1+\tanh x\tanh y}$ 渲染宽 86.53pt（newtxmath 12pt），整体选项 286.3pt，而 tasks(2) 每列仅 200.4pt → 溢出 51.46pt（route_cmp 双路线对比测试）。改为按实测宽度模型（scripts/tex_width.py）判定，放不下就退列 |

### 题目编号

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `ENUM-START-001` | 解答题起始编号 | start = 单选题数 + 多选题数 + 填空题数 + 1 | 8+3+3 配置 → start=15；手算错误是历史最高频问题 |
| `ENUM-RESUME-001` | 答案文档编号衔接 | 第一个 enumerate 不带 start，后续统一用 [resume] | 各题型独立计数会使答案文档编号从 1 反复重新开始 |

### 间距与页数

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `PAGE-001` | 试卷页数 | 严格匹配试卷标注页数 | 试卷标注「共 4 页」而实际 5 页属硬伤 |
| `PAGE-002` | 超页压缩手段（按优先级） | 减小解答题 itemsep；导言区加 \linespread{1.05}\selectfont；最后手段：调整 margin | 先动行距会破坏整体观感，应优先调 itemsep |
| `PAGE-003` | 解答题 itemsep 经验值 | 4 页 3 题：2.0 ~ 2.5cm<br>4 页 4 题：1.8 ~ 2.2cm<br>4 页 5 题：1.5 ~ 2.0cm<br>4 页 6 题：1.2 ~ 1.5cm<br>itemsep < 1.0cm 仍超页：降 linespread 至 0.95 | 10 份高考试卷实测区间 |

### 答题空间

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `ANS-001` | 答题空间命令与留白量 | \answern：3em，normal 模式（作业，默认） | 命令定义在 templates/gaokao-template.tex 导言区 |
| `ANS-002` | 答题空间插入位置 | 每道解答题 \item 内容结束后；最后一道解答题不插入 | 末题插入会在页尾留大片空白 |
| `ANS-003` | 答题空间禁止线条 | 仅用 \vspace 留白 | 禁止：`\rule`、tcolorbox、`\fbox`、虚线、角标<br>用户明确要求纯留白，保持试卷整洁 |

### 输入提取

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `EXTRACT-001` | 图片目录命名 | 任意输入（DOCX / PDF，试题或答案）：Images-<文件名去扩展名>（与 ARTIFACT-003 一致，试题不再用 media） | graphicspath 与目录名不一致时图片全部丢失且不报错；统一 Images-<卷名> 与题库既有约定对齐 |
| `EXTRACT-002` | 扫描件判定 | pandoc 输出仅含 ![](media/imageN.png) 且无正文 → 走 MinerU OCR | 扫描件 DOCX 用 pandoc 只能拿到整页图片，提取不到任何文字 |
| `EXTRACT-003` | WMF 转 PNG | Pillow 渲染，600 DPI | xelatex 不直接支持 WMF，残留 WMF 会导致编译失败 |

### 产物规范

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `ARTIFACT-001` | 试题卷标准产物集 | 试卷：<卷名>.tex / .pdf（含 \answern 答题空间，学生版/教师版合并后的唯一版本）<br>答题卡：<卷名>-答题卡-A4.tex / .pdf + <卷名>-答题卡-A3.tex / .pdf<br>图片文件夹：Images-<卷名>/<br>编译脚本：build.py | 用户确认的三件套需求；学生版与教师版合并为唯一试卷版本（render_tex.py 直接产出，含 \answern 答题空间），-学生版/-教师版 后缀废止；与题库每卷 Images-* + build.py 的既有整理约定一致；答案文档（文件名含答案）只出 tex/.pdf + Images + build.py 三件 |
| `ARTIFACT-002` | 产物命名后缀表 | 答题卡 A4：-答题卡-A4<br>答题卡 A3：-答题卡-A3 | 禁止：-学生版（学生版/教师版已合并，后缀废止）、-教师版（学生版/教师版已合并，后缀废止）、-答题空间（旧名，已废弃）<br>学生版与教师版合并为唯一试卷版本 <卷名>.tex，不再有版本后缀；仅答题卡保留 A4/A3 后缀 |
| `ARTIFACT-003` | 图片文件夹统一命名 | Images-<卷名>（试题与答案一致，替代旧约定 media） | 题库每卷 Images-* 目录的既有约定；试题用 media 与答案用 Images-* 双标准增加记忆负担 |
| `ARTIFACT-004` | 收尾与部署 | 每个含 tex 的试卷目录部署通用版 build.py；排版完成后用 scripts/finalize_paper.py 一键补齐产物集、编译并清理 preview-*.png | finalize_paper.py 端到端实测（生成答题卡、部署 build.py、编译成功、清单全 OK）；学生版/教师版合并后收尾仅补答题卡与编译 |

> 规则版本 v3，更新于 2026-11-02。修改规则请编辑 `rules/layout.yaml` 后运行 `python scripts/gen_rules_doc.py`。
<!-- RULES:END full -->

---

## 数学公式核心规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 行内公式 | `$...$` | 集合 $A=\{x \mid x^2-3x+2=0\}$ |
| 行间公式 | `\[...\]` | `\[a^2+b^2=c^2\]` |
| 分数 | `\frac{}{}`，太长用 `\dfrac{}{}` | `\frac{1}{3}` |
| 三角函数 | `\sin` `\cos` `\tan` | `\sin\theta` |
| 对数 | `\ln` `\lg` | `\ln x` |
| 分段函数 | `\begin{cases} ... \end{cases}` | 每行 `&` 对齐，`\\` 换行 |
| 集合 | `\{` `\}` 转义，`\mid` 表示「使得」 | `\{x \mid x>0\}` |
| 向量 | `\vec{a}` 或 `\mathbf{a}` | `\vec{AB}` |
| 圆周率 | `\pi` | |
| 自然底数 | `\mathrm{e}` 或 `\me` | |
| 虚数单位 | `\mathrm{i}` 或 `\mi` | |

## 题型结构示例

> 编号规则见 `ENUM-START-001`、`ENUM-RESUME-001`；列数见 `TASKS-COL-001`。

### 选择题（单选）

```latex
\begin{enumerate}[itemsep=0.3em]
    \item 题目内容
    \begin{tasks}(4)
        \task 选项A
        \task 选项B
        \task 选项C
        \task 选项D
    \end{tasks}
\end{enumerate}
```

### 选择题（多选）

```latex
\begin{enumerate}[start=9, itemsep=0.5em]
    \item 题目内容
    \begin{tasks}(2)
        \task 选项A
        \task 选项B
        \task 选项C
        \task 选项D
    \end{tasks}
\end{enumerate}
```

### 填空题

```latex
\begin{enumerate}[start=12, itemsep=0.8em]
    \item 题目内容 \blank.
\end{enumerate}
```

### 解答题

```latex
\begin{examenum}[start=15, itemsep=2.5cm]
    \item （13分）题目描述．
    \begin{examenum}
        \item 第1问；
        \item 第2问．
    \end{examenum}
\end{examenum}
```

**⚠️ `start` 值 = 单选题数 + 多选题数 + 填空题数 + 1**（见 `ENUM-START-001`）

## 图片场景示例

> 宽度与场景选择见 `IMG-W-001` ~ `IMG-SCENE-001`。

### 场景1：小装饰图（行内）

```latex
\includegraphics[height=0.6em]{file.png}
```

### 场景2：几何/示意图在列表环境外

```latex
\begin{wrapfigure}{r}{0.35\textwidth}
\centering
\includegraphics[width=\linewidth]{file.png}
\end{wrapfigure}
```

### 场景3：几何/示意图在列表环境中（有子问）

`wrapfigure` 会失效，改用 `minipage` 左右并排：

```latex
\item （12分）如图，... 题目描述 ...

\medskip
\noindent
\begin{minipage}[t]{0.62\textwidth}
\begin{examenum}
    \item 第1问
    \item 第2问
\end{examenum}
\end{minipage}
\hfill
\begin{minipage}[t]{0.30\textwidth}
\vspace{0pt}
\centering
\includegraphics[width=\linewidth]{file.png}
\captionof{figure}{图注}
\end{minipage}
```

### 场景4：单张插图（无子问）— 环绕排布

```latex
% 图片在 examenum 之前，使用 wrapfigure 环绕
\begin{wrapfigure}{r}{0.30\textwidth}
\centering
\includegraphics[width=\linewidth]{file.png}
\caption{第15题图}
\end{wrapfigure}
\item （13分）如图所示，在四棱锥 $Q-ABCD$ 中...
\begin{examenum}
    \item 证明：$BQ \perp AD$；
    \item 若 $QB = \sqrt{6}$，求平面 $QAD$ 与 $QBC$ 夹角的余弦值。
\end{examenum}
\answern
```

**注意**：
- `wrapfigure` 必须放在 `\item` 之前，不能放在 `examenum` 内部
- 如果图片在题目描述之后、子问之前，改用 `minipage` 左右并排

### 场景5：TikZ 图

```latex
\resizebox{0.35\textwidth}{!}{...}
```

### 场景6：图片作为选项（绳结图、电路图、三视图等）

```latex
\begin{tasks}(4)
    \task \includegraphics[width=0.12\textwidth]{imageA.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageB.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageC.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageD.jpg}
\end{tasks}
```

- 图片宽度控制在 `0.12\textwidth` 以内（见 `IMG-W-004`）
- **禁止** `tasks(1)` 竖排图片选项（见 `TASKS-COL-002`）

### 场景7：图片与选项并排

```latex
\item 题目描述，如下图所示，则

\medskip
\noindent
\begin{minipage}[t]{0.60\textwidth}
\begin{tasks}(2)
    \task 选项A（长内容）
    \task 选项B（长内容）
    \task 选项C
    \task 选项D
\end{tasks}
\end{minipage}
\hfill
\begin{minipage}[t]{0.32\textwidth}
\vspace{0pt}
\centering
\includegraphics[width=0.85\linewidth]{image.jpg}
\captionof{figure}{第9题图}
\end{minipage}
```

### 场景8：多张图片并排

**关键**：并排图片必须添加 `height=Xcm,keepaspectratio` 限制高度（见 `IMG-W-003`）。

```latex
\begin{figure}[H]
\centering
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{img1.jpg}
\caption*{①}
\end{minipage}
\hfill
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{img2.jpg}
\caption*{②}
\end{minipage}
\hfill
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{img3.jpg}
\caption*{③}
\end{minipage}
\end{figure}
```

## 答案文档特殊规则

### 答案块结构

```
题目文本 → \daan{...}（答案）→ \jieti（解析）→ \xijie（详解）
```

### 解答题多问

用 `\xiaoI` / `\xiaoII` / `\xiaoIII` 分别标记【小问 N 详解】

### 选项排版

- **DOCX 输入**：答案文档的选项通常是图片（WMF 公式），用 `\eqimg` 命令插入
- **PDF 输入**：MinerU 提取的选项可能已有 LaTeX 公式，优先直接使用 LaTeX 格式

### 编号规则

见 `ENUM-RESUME-001`：第一个 `enumerate` 不带 `start`，后续统一 `[resume]`。

## 表格规则

用标准 `tabular` + `booktabs` 三线表：

```latex
\begin{table}[H]
\centering
\begin{tabular}{ccc}
\toprule
列1 & 列2 & 列3 \\
\midrule
值1 & 值2 & 值3 \\
\bottomrule
\end{tabular}
\captionof{table}{表标题}
\end{table}
```

列数 > 6 时加 `\small`；> 8 时用 `\resizebox{\textwidth}{!}{...}` 包裹。

## 答题空间

见 `ANS-001` ~ `ANS-003`。要点：

- 答题空间命令 `\answern`（3em）定义在 `templates/gaokao-template.tex`
- 插入在每道解答题 `\item` 内容结束后，**最后一道不插入**
- 纯留白，禁止任何线条

```latex
\begin{examenum}[start=15, itemsep=1.5em]
    \item （13分）题目描述．
    \begin{examenum}
        \item 第1问；
        \item 第2问．
    \end{examenum}
    \answern  % ← 在此处插入答题空间

    \item （15分）下一题...
\end{examenum}
```

## 页数控制

见 `PAGE-001` ~ `PAGE-003`。要点：

- 学生版页数严格匹配标注
- 超页优先调 `itemsep`，其次 `\linespread`，最后才动 margin
- 教师版不受标注页数约束，通常 ≤ 7 页

## 与模板一致性原则

- 标题格式完全沿用模板
- 注意事项文字直接复制模板
- 各题型标题直接复制模板
- 大题分值标注格式保持一致
