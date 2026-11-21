# LaTeX 排版配方（方式 B 兜底 / 手工调整时读）

> 只在两种情况下需要本文件：① 用「方式 B：直接写 LaTeX」；② 渲染结果需要手工微调。
> 走 `render_tex.py` 时，下面的编号、列数、间距、答题空间都由脚本按规则自动决定。

## 题型结构速查

```latex
% 单选
\begin{enumerate}[itemsep=0.3em]
    \item 题目内容
    \begin{tasks}(4)  % 简短选项4列，长选项2列
        \task A \task B \task C \task D
    \end{tasks}
\end{enumerate}

% 多选
\begin{enumerate}[start=9, itemsep=0.5em]
    \item 题目内容
    \begin{tasks}(2)
        \task A \task B \task C \task D
    \end{tasks}
\end{enumerate}

% 填空
\begin{enumerate}[start=12, itemsep=0.8em]
    \item 题目内容 \blank.
\end{enumerate}

% 解答
\begin{examenum}[start=15, itemsep=2.5cm]
    \item （13分）题目描述．
    \begin{examenum}
        \item 第1问；
        \item 第2问．
    \end{examenum}
\end{examenum}
```

## 图片排版

核心三条：

- 一般场景用 `\centering`，禁止 `\raggedleft`（`IMG-ALIGN-001`，图注必须居中于图片正下方）；
  **例外**：立体几何解答题单个立体图用 `flushright` 靠右、多图并排仍居中
  （`IMG-ALIGN-002`；LaTeX 无 `right` 环境）
- 单张硬上限 `0.35\textwidth`，默认 `0.30\textwidth`；选项图 `0.12\textwidth`
  （`IMG-W-001` / `IMG-W-002` / `IMG-W-004`）
- 多图并排必须限高 `height=Xcm,keepaspectratio`（`IMG-W-003`：2 张 3cm / 3 张 2.5cm）

8 种场景选择与「图片 + 选项」布局决策见规则 `IMG-SCENE-001`，完整 LaTeX 示例见
[conversion-rules.md](conversion-rules.md) 的「图片场景示例」章节。

## 答题空间

命令定义在 `templates/math/gaokao-template.tex` 导言区：`\answern`(3em)（`ANS-001`），
由 `render_tex.py` 按 `meta.answer_space: normal`（默认）自动插入。

插入位置：每道解答题的 `\item` 内容结束后、下一 `\item` 之前：

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

规则（`ANS-002` / `ANS-003`）：

- 最后一道解答题后**不插入**答题空间（避免尾部留白过多）
- 答题空间命令前需有空行（`\par` 已包含在命令内）
- 纯留白，**禁止** `\rule`、`tcolorbox`、`\fbox` 等任何带线条的命令

## itemsep 与页数控制

经验值见 `PAGE-003`：4 页卷 3 题 2.0~2.5cm、4 题 1.8~2.2cm、5 题 1.5~2.0cm、6 题 1.2~1.5cm。

调整顺序（`PAGE-002`）：先调 itemsep → 仍超页加 `\linespread{1.05}\selectfont` → 最后才动 margin。
编译后可交给 `scripts/quality/auto_adjust.py` 自动迭代到目标页数。

## tasks 列数

规则见 `TASKS-COL-001`。`scripts/render/render_tex.py` 已实现该判定，走渲染器时无需手算。
下面是手工写时的对照：

```latex
% 简短选项 → tasks(4)
\begin{tasks}(4)
    \task $\dfrac{1}{2}$ \task $\dfrac{\sqrt{2}}{2}$ \task $\dfrac{\sqrt{3}}{2}$ \task $1$
\end{tasks}

% 长选项/含公式 → tasks(2)
\begin{tasks}(2)
    \task 双曲正弦函数是增函数
    \task $\tanh(x+y) = \dfrac{\tanh x + \tanh y}{1 + \tanh x \tanh y}$
\end{tasks}

% 图片选项 → tasks(4)
\begin{tasks}(4)
    \task \includegraphics[width=0.12\textwidth]{a.jpg}
    \task \includegraphics[width=0.12\textwidth]{b.jpg}
    \task \includegraphics[width=0.12\textwidth]{c.jpg}
    \task \includegraphics[width=0.12\textwidth]{d.jpg}
\end{tasks}
```

## 答案文档特殊处理

- `\graphicspath` 必须对齐图片目录
- 答案块结构：题目文本 → `\daan{...}` → `\jieti` → `\xijie`
- 解答题多问：`\xiaoI` / `\xiaoII` / `\xiaoIII`
- 选项为图片时用 `\eqimg[0.15]{imageN.png}`
- **不需要 `itemsep` 间距**
