# 地理试卷图表 LaTeX 重绘参考

> 本文档是 geo-paper-format 技能的图表重绘指南，列出可用 TikZ/pgfplots 重绘的地理图表类型及示例代码。

## 重绘策略

在 Step 4（写 LaTeX → 逐题转换）时，遇到以下类型的图片，**优先考虑用 LaTeX 代码重绘**而非插入图片：

- ✅ **完全重绘**：图表完全由 TikZ/pgfplots 生成，无需插入图片文件
- ⚠️ **混合方式**：框架用 TikZ 绘制，底图用 `\includegraphics` 插入
- ❌ **不可重绘**：照片、卫星图、真实地图 → 直接插入原图

## 大小和位置约束

重绘图表必须遵守以下约束，确保排版一致：

| 约束项 | 规则 | 说明 |
|--------|------|------|
| **最大宽度** | `≤ 0.35\textwidth` | 与图片插入规则一致 |
| **最大高度** | `≤ 0.4\textheight` | 避免图表占据过多页面 |
| **水平位置** | 题目内容右侧 | 使用 `wrapfigure` 或 `minipage` 实现环绕 |
| **垂直位置** | 与引用处对齐 | 图表顶部与引用行对齐 |
| **字体大小** | `≥ \small`（约 10.5pt） | 确保图中文字可读 |
| **配色方案** | 全卷统一 | 同一类型的图表使用相同配色 |
| **线宽** | `≥ 0.6pt` | 确保打印后清晰可见 |
| **标注位置** | 与原文一致 | 海拔、温度、百分比等标注位置不变 |

### 位置代码模板

**列表环境外（wrapfigure 环绕）：**
```latex
\begin{wrapfigure}{r}{0.35\textwidth}
\centering
\begin{tikzpicture}[scale=0.8]
    % 重绘内容
\end{tikzpicture}
\captionof{figure}{图注}
\end{wrapfigure}
```

**列表环境内（minipage 并排）：**
```latex
\noindent
\begin{minipage}[t]{0.62\textwidth}
    % 题目内容
\end{minipage}
\hfill
\begin{minipage}[t]{0.35\textwidth}
    \vspace{0pt}
    \centering
    \begin{tikzpicture}[scale=0.8]
        % 重绘内容
    \end{tikzpicture}
    \captionof{figure}{图注}
\end{minipage}
```

## 多模态模型依赖

重绘图表需要多模态大模型的视觉能力，按场景分为：

| 场景 | 是否需要视觉 | 原因 | 处理方式 |
|------|-------------|------|---------|
| 原图是统计图/数据图表 | ✅ **需要** | 需从原图读取数据值 | 模型读取图片 → 提取数据 → 生成 pgfplots 代码 |
| 原图是示意图/流程图 | ✅ **需要** | 需理解图形结构和逻辑关系 | 模型读取图片 → 理解结构 → 生成 TikZ 代码 |
| 数据已在 Markdown 中 | ❌ 不需要 | pandoc/MinerU 已提取表格数据 | 直接用 `\begin{tabular}` 或 pgfplots 绘制 |
| 原图是照片/卫星图 | ❌ 不可重绘 | 无法用矢量图重现 | 直接 `\includegraphics` 插入原图 |

### 重绘工作流

```
原图 → 多模态模型读取 → 提取数据/结构 → 生成 TikZ/pgfplots 代码
    ↓
数据已在 Markdown 中？ → 是 → 直接用表格数据生成图表
    ↓ 否
生成 LaTeX 代码 → 编译验证 → 对比原图 → 调整至一致
```

### 注意事项

1. **数据准确性**：从原图提取数据时，必须确保数值与原图一致
2. **标注完整性**：原图中的所有文字标注、图例、单位必须保留
3. **风格一致性**：同一试卷中的同类图表保持统一风格
4. **编译测试**：重绘后必须编译验证，确保无报错、无溢出

---

## 1. 等高线地形图

用 TikZ 绘制等值线，可标注海拔、河流、村镇等要素。

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{tikz}
\begin{document}

\begin{center}
\begin{tikzpicture}[scale=0.6]
    % 等高线（从低到高）
    \draw[thick] (0,0) ellipse (5 and 3);
    \draw[thick] (0,0) ellipse (4.2 and 2.5);
    \draw[thick] (0,0) ellipse (3.4 and 2);
    \draw[thick] (0,0) ellipse (2.6 and 1.5);
    \draw[thick] (0,0) ellipse (1.8 and 1.1);
    \draw[thick] (0,0) ellipse (1.0 and 0.6);
    \draw[thick, red] (0,0) ellipse (0.4 and 0.25);

    % 海拔标注
    \node at (4.6,0) {200};
    \node at (3.8,0) {300};
    \node at (3.0,0) {400};
    \node at (2.2,0) {500};
    \node at (1.4,0) {600};
    \node[red] at (0,0) {700};

    % 山峰标记
    \filldraw[red] (0,0) circle (3pt);
    \node[above right] at (0,0) {▲ 山顶};

    % 河流（从高到低）
    \draw[blue, thick, ->] (0.5,0.3) .. controls (2,1) and (3,-1) .. (4.5,0.2);
    \node[blue] at (3,0.8) {河流};

    % 村庄标记
    \filldraw[brown] (-2,1) circle (2pt);
    \node[above] at (-2,1) {A村};
    \filldraw[brown] (1,-1.5) circle (2pt);
    \node[below] at (1,-1.5) {B村};

    % 指向标
    \draw[->, thick] (4,2.5) -- (4,3.2);
    \node at (4,3.5) {N};
\end{tikzpicture}
\captionof{figure}{某区域等高线地形图}
\end{center}

\end{document}
```

---

## 2. 地理过程/循环示意图

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{tikz}
\usetikzlibrary{arrows.meta, positioning}
\begin{document}

\begin{center}
\begin{tikzpicture}[
    node distance=2.5cm,
    box/.style={rectangle, draw, rounded corners, minimum width=2.5cm, minimum height=1cm, align=center, fill=blue!10},
    arrow/.style={-Stealth, thick}
]
    \node[box] (a) {海水蒸发};
    \node[box, right=of a] (b) {水汽输送};
    \node[box, below right=of b] (c) {大气降水};
    \node[box, below left=of c] (d) {地表径流\\地下径流};
    \node[box, left=of d] (e) {汇入海洋};

    \draw[arrow] (a) -- (b);
    \draw[arrow] (b) -- (c);
    \draw[arrow] (c) -- (d);
    \draw[arrow] (d) -- (e);
    \draw[arrow] (e) to[out=180, in=180] (a);
    \draw[arrow, dashed] (c) -- ++(0,-1) -| (d);
\end{tikzpicture}
\captionof{figure}{水循环示意图}
\end{center}

\end{document}
```

---

## 3. 统计图表（柱状图/折线图）

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}

% 柱状图：某地区产业结构变化
\begin{center}
\begin{tikzpicture}
\begin{axis}[
    ybar,
    width=10cm, height=6cm,
    xlabel={年份},
    ylabel={比重 (\%)},
    ymin=0, ymax=100,
    symbolic x coords={2018, 2019, 2020, 2021, 2022},
    xtick=data,
    legend style={at={(0.5,1.05)}, anchor=south, legend columns=-1},
    bar width=12pt,
    nodes near coords,
    nodes near coords align={vertical},
]
\addplot coordinates {(2018,52) (2019,50) (2020,48) (2021,45) (2022,42)};
\addplot coordinates {(2018,30) (2019,31) (2020,32) (2021,33) (2022,34)};
\addplot coordinates {(2018,18) (2019,19) (2020,20) (2021,22) (2022,24)};
\legend{第一产业, 第二产业, 第三产业}
\end{axis}
\end{tikzpicture}
\captionof{figure}{某地区产业结构变化}
\end{center}

% 折线图：人口增长趋势
\begin{center}
\begin{tikzpicture}
\begin{axis}[
    width=10cm, height=6cm,
    xlabel={年份},
    ylabel={人口（万人)},
    xmin=2015, xmax=2025,
    grid=major,
    legend pos=north west,
]
\addplot[smooth, mark=*, blue, thick] coordinates {
    (2016,1200) (2017,1230) (2018,1255) (2019,1280)
    (2020,1300) (2021,1315) (2022,1325) (2023,1330)
    (2024,1332) (2025,1330)
};
\legend{总人口}
\end{axis}
\end{tikzpicture}
\captionof{figure}{某地区人口变化趋势}
\end{center}

\end{document}
```

---

## 4. 气候图表（气温曲线+降水柱状图）

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}

\begin{center}
\begin{tikzpicture}
    % 降水柱状图（左轴）
    \begin{axis}[
        width=12cm, height=7cm,
        ybar,
        bar width=8pt,
        xlabel={月份},
        ylabel={降水量 (mm)},
        ymin=0, ymax=250,
        symbolic x coords={1,2,3,4,5,6,7,8,9,10,11,12},
        xtick=data,
        axis y line*=left,
        fill=cyan!50,
    ]
    \addplot coordinates {(1,15)(2,20)(3,35)(4,55)(80,150)(200,220)(180,100,60,30,20,15)};
    \end{axis}

    % 气温曲线（右轴）
    \begin{axis}[
        width=12cm, height=7cm,
        ylabel={气温 (℃)},
        ymin=-10, ymax=35,
        symbolic x coords={1,2,3,4,5,6,7,8,9,10,11,12},
        xtick=data,
        axis y line*=right,
        axis x line=none,
        red, thick,
    ]
    \addplot[smooth, mark=*, red, thick] coordinates {
        (1,-5)(2,-2)(3,5)(4,12)(5,18)(6,22)(7,25)(8,23)(3,18)(10,10)(11,3)(12,-3)
    };
    \end{axis}
\end{tikzpicture}
\captionof{figure}{某地气温曲线与降水柱状图}
\end{center}

\end{document}
```

---

## 5. 地质剖面图

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{tikz}
\begin{document}

\begin{center}
\begin{tikzpicture}[scale=0.8]
    % 地层分层
    \fill[yellow!30] (0,0) rectangle (8,0.8);
    \fill[orange!40] (0,0.8) rectangle (8,1.6);
    \fill[brown!40] (0,1.6) rectangle (8,2.4);
    \fill[gray!40] (0,2.4) rectangle (8,3.2);
    \fill[green!30] (0,3.2) rectangle (8,4.0);

    % 地层标签
    \node at (4,0.4) {表层土壤};
    \node at (4,1.2) {砂岩层};
    \node at (4,2.0) {页岩层};
    \node at (4,2.8) {石灰岩层};
    \node at (4,3.6) {花岗岩层};

    % 断层线
    \draw[thick, red, decorate, decoration={zigzag, segment length=4mm, amplitude=2mm}]
        (4,0) -- (4,4);
    \node[red] at (5.5,3.5) {断层};

    % 标注
    \draw[<->] (8.5,0) -- (8.5,4) node[midway, right] {地层年代};
    \draw[dashed] (0,0) -- (0,-0.5) node[below] {地表};
\end{tikzpicture}
\captionof{figure}{某地区地质剖面图}
\end{center}

\end{document}
```

---

## 6. 区域示意图

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{tikz}
\usetikzlibrary{arrows.meta, shapes.geometric}
\begin{document}

\begin{center}
\begin{tikzpicture}[scale=0.7]
    % 区域轮廓
    \fill[green!20, draw=green!50!black, thick] (0,0) .. controls (2,1) and (4,-1) .. (6,0)
        .. controls (7,1) and (7,3) .. (6,4) .. controls (4,5) and (2,5) .. (0,4)
        .. controls (-1,3) and (-1,1) .. (0,0);

    % 城市标记
    \filldraw[red] (2,2) circle (3pt);
    \node[above right] at (2,2) {甲城市};
    \filldraw[red] (4,3) circle (3pt);
    \node[above right] at (4,3) {乙城市};
    \filldraw[red] (3,1) circle (3pt);
    \node[below right] at (3,1) {丙城市};

    % 河流
    \draw[blue, thick] (0.5,2.5) .. controls (2,2) and (3,3.5) .. (5.5,2);
    \node[blue] at (1.5,3) {河流};

    % 山脉
    \filldraw[brown] (5,3.5) -- (5.3,4.2) -- (5.6,3.5) -- cycle;
    \filldraw[brown] (5.5,3.3) -- (5.8,4) -- (6.1,3.3) -- cycle;
    \node[brown] at (6.5,4) {山脉};

    % 交通线
    \draw[black, thick] (2,2) -- (3,1) -- (4,3);
    \node at (2.5,1.3) {铁路};

    % 图例
    \node[anchor=west] at (7,1) {\tikz \filldraw[red] (0,0) circle (2pt);} 城市;
    \node[anchor=west] at (7,0) {\tikz \draw[blue, thick] (0,0) -- (0.5,0);} 河流;
    \node[anchor=west] at (7,-1) {\tikz \draw[black, thick] (0,0) -- (0.5,0);} 铁路;
\end{tikzpicture}
\captionof{figure}{某区域地理事物分布示意图}
\end{center}

\end{document}
```

---

## 7. 地理关系/系统结构图

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{tikz}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric}
\begin{document}

\begin{center}
\begin{tikzpicture}[
    node distance=1.8cm,
    cause/.style={rectangle, draw=blue!60, fill=blue!10, rounded corners, minimum width=2.5cm, minimum height=0.8cm, align=center},
    effect/.style={rectangle, draw=red!60, fill=red!10, rounded corners, minimum width=2.5cm, minimum height=0.8cm, align=center},
    arrow/.style={-Stealth, thick}
]
    \node[cause] (c1) {全球变暖};
    \node[cause, below=of c1] (c2) {冰川融化};
    \node[cause, below=of c2] (c3) {降水减少};
    \node[effect, right=of c1, xshift=2cm] (e1) {海平面上升};
    \node[effect, right=of c2, xshift=2cm] (e2) {河流径流减少};
    \node[effect, right=of c3, xshift=2cm] (e3) {农业减产};

    \draw[arrow] (c1) -- (e1);
    \draw[arrow] (c1) -- (c2);
    \draw[arrow] (c2) -- (e2);
    \draw[arrow] (c2) -- (c3);
    \draw[arrow] (c3) -- (e3);
    \draw[arrow, dashed] (c1) to[bend left=30] (e2);
\end{tikzpicture}
\captionof{figure}{全球变暖对地理环境的影响}
\end{center}

\end{document}
```

---

## 8. 饼图（产业结构/人口构成）

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{pgf-pie}
\begin{document}

\begin{center}
\begin{tikzpicture}
\pie[
    text=legend,
    radius=3,
    color={blue!60, green!60, orange!60, red!60},
    sum=auto,
]{42/第一产业, 34/第三产业, 20/第二产业, 4/其他}
\end{tikzpicture}
\captionof{figure}{某地区产业结构}
\end{center}

\end{document}
```

> **注意**：`pgf-pie` 需额外安装。若不可用，可用 `pgfplots` 的 `\addplot` 替代。

---

## 重绘决策流程

在 Step 4 逐题转换时，按以下流程判断是否重绘：

```
遇到图片
    ↓
图片类型是统计图/示意图/气候图/剖面图/关系图？
    ├── 是 → ✅ 用 TikZ/pgfplots 重绘
    │         ├── 数据完整 → 完全重绘
    │         └── 底图复杂 → 混合方式（TikZ框架 + 图片底图）
    └── 否 → 是照片/卫星图/真实地图？
              ├── 是 → ❌ 直接插入原图
              └── 不确定 → 优先尝试重绘，失败则插入原图
```

## 重绘原则

1. **清晰优先**：重绘后的图表必须比原图更清晰
2. **信息完整**：不丢失原图中的任何标注、数据
3. **风格统一**：全卷的统计图表保持一致的配色和字体
4. **标注准确**：海拔、温度、百分比等数据与原图一致
5. **简洁美观**：去除原图中的噪点、水印等干扰元素
