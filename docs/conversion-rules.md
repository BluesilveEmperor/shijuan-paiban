# 试卷 → LaTeX 转换规则

> 本文档由 SKILL.md 引用，包含逐题转换时的详细规则。

## 输入类型判断

### 扫描件 DOCX 识别
当 pandoc 输出仅包含 `![](media/imageN.png)` 图片标记而无文本内容时，判定为扫描件 DOCX。
此时直接采用 MinerU SDK 对每张页面图片进行 OCR 识别，输出 Markdown 包含 LaTeX 公式。

## 数学公式核心规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 行内公式 | `$...$` | 集合 $A=\{x \mid x^2-3x+2=0\}$ |
| 行间公式 | `\[...\]` | `\[a^2+b^2=c^2\]` |
| 分数 | `\frac{}{}`，太长用 `\dfrac{}{}` | `\frac{1}{3}` |
| 三角函数 | `\sin` `\cos` `\tan` | `\sin\theta` |
| 对数 | `\ln` `\lg` | `\ln x` |
| 分段函数 | `\begin{cases} ... \end{cases}` | 每行 `&` 对齐，`\\` 换行 |
| 集合 | `\{` `\}` 转义，`\mid` 表示"使得" | `\{x \mid x>0\}` |
| 向量 | `\vec{a}` 或 `\mathbf{a}` | `\vec{AB}` |
| 圆周率 | `\pi` | |
| 自然底数 | `\mathrm{e}` 或 `\me` | |
| 虚数单位 | `\mathrm{i}` 或 `\mi` | |

## 题型结构规则

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

### tasks 列数自动判断

| 条件 | 列数 | 示例 |
|------|------|------|
| 选项含图片，平均长度 < 80 字符 | 4 列 | 绳结图、电路图 |
| 选项含图片，平均长度 ≥ 80 字符 | 2 列 | 带文字说明的图 |
| 选项含公式或平均长度 > 25 字符 | 2 列 | 三角函数、不等式 |
| 选项简短（< 15 字符） | 4 列 | 纯数字、简单字母 |

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

**⚠️ 关键规则：**
- `start` 值 = 单选题数 + 多选题数 + 填空题数 + 1
- 示例：8+3+3 配置 → `start=15`
- `itemsep` 默认值 2.5cm，根据页数调整：
  - 4页试卷且5道解答题 → `itemsep=1.5cm` ~ `2.0cm`
  - 4页试卷且解答题较少 → `itemsep=2.0cm` ~ `2.5cm`
  - 目标是让5道解答题均匀分布在2-3页内
- 教师版移除 `itemsep`（分页替代了间隙作用）

## 图片插入规则

**所有图片宽度不得超过 `0.35\textwidth`，图片显示在题目内容右侧。**

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

**规则**：解答题若只有一张题目配图，该图靠右并与题目成环绕排布。

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
    \item 若 $QB = \sqrt{6}$，求平面 $QAD$ 与平面 $QBC$ 夹角的余弦值。
\end{examenum}
\answern
```

**注意**：
- `wrapfigure` 必须放在 `\item` 之前，不能放在 `examenum` 内部
- 图片宽度 `0.30\textwidth`，右侧环绕
- 如果图片在题目描述之后、子问之前，改用 `minipage` 左右并排

### 场景5：TikZ 图
```latex
\resizebox{0.35\textwidth}{!}{...}
```

### 场景6：图片作为选项（如绳结图、电路图、三视图等）
当选择题的选项是图片时，使用 `tasks(4)` 将4张图片排成一行：
```latex
\begin{tasks}(4)
    \task \includegraphics[width=0.12\textwidth]{imageA.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageB.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageC.jpg}
    \task \includegraphics[width=0.12\textwidth]{imageD.jpg}
\end{tasks}
```
- 图片宽度控制在 `0.12\textwidth` 以内，确保4张图总宽度不超过 `0.48\textwidth`
- 如果图片较大，改用 `tasks(2)` 每行2张
- **禁止**使用 `tasks(1)` 将图片选项竖排（浪费空间且不美观）

### 场景7：图片与选项并排（如概率分布图+选项、函数图象+选项）

**何时使用**：选项内容较长（> 15字）或含公式时，使用 `minipage` 左右并排，避免选项重叠。

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

**判断规则**：
| 条件 | 布局方式 |
|------|---------|
| 选项简短（< 10字） | 图片在上，选项在下 |
| 选项较长（> 15字）或含公式 | `minipage` 左右并排 |
| 选项与图片高度相当 | `minipage` 左右并排 |

### 场景8：多张图片并排（如三视图、示意图组、残差图）
**关键**：并排图片必须添加 `height=Xcm,keepaspectratio` 限制高度，避免图片过高。

| 图片数量 | minipage 宽度 | 图片高度 |
|---------|-------------|---------|
| 2 张并排 | `0.42	extwidth` | `3cm` |
| 3 张并排 | `0.28	extwidth` | `2.5cm`
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
用 `\xiaoI` 和 `\xiaoII` 分别标记【小问 1 详解】和【小问 2 详解】

### 选项排版
- **DOCX 输入**：答案文档的选项通常是图片（WMF公式），用 `\eqimg` 命令插入
- **PDF 输入**：MinerU 提取的选项可能已有 LaTeX 公式，优先直接使用 LaTeX 格式

### 编号规则
- 选择题：`\begin{enumerate}`
- 多选题：`\begin{enumerate}[resume]`
- 填空题：`\begin{enumerate}[resume]`
- 解答题：`\begin{enumerate}[resume]`

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

## 答题空间（纯留白，无线条无边框）

**模板已定义三个命令**：

| 命令 | 留白量 | 适用模式 |
|------|--------|---------|
| `\answerc` | 1.5em | compact（自学） |
| `\answern` | 3em | normal（作业） |
| `\answere` | 5em | exam（测试） |

**插入规则**：
- 每道解答题的 `\item` 内容结束后、下一 `\item` 之前插入
- 最后一道解答题后**不插入**
- **禁止**使用 `\rule`、`tcolorbox`、`\fbox` 等任何带线条的命令

**示例**：
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

- 学生版试卷页数必须严格匹配标注（如"本试卷共4页"）
- 超页时：在导言区添加 `\linespread{1.05}\selectfont`
- 教师版不受试卷标注页数约束，通常控制在 7 页内
- 教师版不需要 `itemsep=2.5cm`
- **itemsep 经验值**：4页5题 → 1.5~2.0cm；4页3题 → 2.0~2.5cm

## 与模板一致性原则

- 标题格式完全沿用模板
- 注意事项文字直接复制模板
- 各题型标题直接复制模板
- 大题分值标注格式保持一致
