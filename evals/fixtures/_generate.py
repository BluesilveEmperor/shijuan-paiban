#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_generate.py - 生成评估样本（fixture）的 .tex 与占位图片

fixture 不手写导言区，而是从 templates/ 里的真实模板切出 preamble，
再拼上各场景的正文。这样 fixture 就是「技能实际会产出的东西」，
模板一改，重新运行本脚本即可让样本同步。

用法:
  python evals/fixtures/_generate.py

产出:
  evals/fixtures/<case>/<case>.tex
  evals/fixtures/<case>/images/*.png   （需要插图的用例）
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"


def preamble_of(template_name):
    """取出 \\begin{document} 之前的全部内容。"""
    text = (TEMPLATES / template_name).read_text(encoding="utf-8")
    idx = text.find("\\begin{document}")
    if idx < 0:
        raise SystemExit(f"[FATAL] {template_name} 缺少 \\begin{{document}}")
    return text[:idx].rstrip() + "\n"


def make_images(target_dir, count=6):
    """生成简单的几何占位图，避免 fixture 依赖外部素材。"""
    from PIL import Image, ImageDraw

    target_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for i in range(1, count + 1):
        img = Image.new("RGB", (240, 240), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([20, 20, 220, 220], outline="black", width=3)
        if i % 3 == 1:
            d.line([20, 220, 120, 40, 220, 220], fill="black", width=3)
        elif i % 3 == 2:
            d.ellipse([60, 60, 180, 180], outline="black", width=3)
        else:
            d.line([20, 120, 220, 120], fill="black", width=3)
            d.line([120, 20, 120, 220], fill="black", width=3)
        path = target_dir / f"fig{i}.png"
        img.save(path, dpi=(150, 150))
        made.append(path)
    return made


# ────────────────────────── 各场景正文 ──────────────────────────

BODY_STANDARD = r"""\begin{document}

\begin{center}
    \LARGE{\textbf{2026 年测试卷（标准结构）}}
\end{center}

\vspace{0.5em}

\noindent\textbf{一、选择题：本题共2小题，每小题5分，共10分。}

\begin{enumerate}[itemsep=0.3em]
    \item 已知集合 $A=\{x \mid x^2-3x+2=0\}$，$B=\{0,1,2\}$，则 $A \cup B =$
    \begin{tasks}(4)
        \task $\{0\}$
        \task $\{0,1,2\}$
        \task $\{1,2\}$
        \task $\{0,1\}$
    \end{tasks}

    \item 设 $z = 3 + 2\mi$，则 $|z| =$
    \begin{tasks}(4)
        \task $\sqrt{5}$
        \task $\sqrt{13}$
        \task $5$
        \task $13$
    \end{tasks}
\end{enumerate}

\noindent\textbf{二、选择题：本题共1小题，每小题6分，共6分。}

\begin{enumerate}[start=3, itemsep=0.5em]
    \item 下列函数中，在 $\mathbb{R}$ 上单调递增的是
    \begin{tasks}(2)
        \task $y = \me^{x}$
        \task $y = \ln x$
        \task $y = -x^{2}$
        \task $y = \sin x$
    \end{tasks}
\end{enumerate}

\noindent\textbf{三、填空题：本题共1小题，每小题5分，共5分。}

\begin{enumerate}[start=4, itemsep=0.8em]
    \item 若直线 $y=2x+5$ 是曲线 $y=\me^{x}+x+a$ 的一条切线，则 $a=$ \blank.
\end{enumerate}

\noindent\textbf{四、解答题：本题共2小题，共24分。}

\begin{examenum}[start=5, itemsep=2.0cm]
    \item （12分）已知数列 $\{a_n\}$ 中，$a_1=3$，$a_{n+1}=2a_n+1$.
    \begin{examenum}
        \item 证明：数列 $\{a_n+1\}$ 是等比数列；
        \item 求 $\{a_n\}$ 的前 $n$ 项和 $S_n$.
    \end{examenum}
    \answern

    \item （12分）在 $\triangle ABC$ 中，角 $A,B,C$ 的对边分别为 $a,b,c$，且 $2a\cos B = 2c - b$.
    \begin{examenum}
        \item 求角 $A$ 的大小；
        \item 若 $a=3$，求 $\triangle ABC$ 面积的最大值.
    \end{examenum}
\end{examenum}

\end{document}
"""

BODY_ANSWER = r"""\begin{document}

\begin{center}
    {\Large\textbf{2026 年测试卷}}
    \vspace{0.5em}

    {\large\textbf{参考答案}}
    \vspace{0.5em}
    \hrule
\end{center}

\section*{一、选择题}
本题共 2 小题，每小题 5 分，共 10 分。

\begin{enumerate}
    \item 已知集合 $A=\{x \mid x^2-3x+2=0\}$，$B=\{0,1,2\}$，则 $A \cup B =$
    \begin{flushleft}
        A.\ $\{0\}$\quad B.\ $\{0,1,2\}$\quad C.\ $\{1,2\}$\quad D.\ $\{0,1\}$
    \end{flushleft}
    \daan{B}
    \jieti 由 $x^{2}-3x+2=0$ 得 $x=1$ 或 $x=2$，故 $A=\{1,2\}$，从而 $A\cup B=\{0,1,2\}$.
    \xijie 逐个代入验证即可，注意集合元素的互异性.

    \item 设 $z = 3 + 2\mi$，则 $|z| =$
    \begin{flushleft}
        A.\ $\sqrt{5}$\quad B.\ $\sqrt{13}$\quad C.\ $5$\quad D.\ $13$
    \end{flushleft}
    \daan{B}
    \jieti $|z|=\sqrt{3^{2}+2^{2}}=\sqrt{13}$.
    \xijie 复数的模等于实部与虚部平方和的算术平方根.
\end{enumerate}

\section*{三、填空题}
本题共 1 小题，每小题 5 分，共 5 分。

\begin{enumerate}[resume]
    \item 若直线 $y=2x+5$ 是曲线 $y=\me^{x}+x+a$ 的一条切线，则 $a=$ \blank.
    \daan{4}
    \jieti 设切点横坐标为 $x_0$，由 $y'=\me^{x}+1=2$ 得 $x_0=0$.
    \xijie 切点为 $(0,1+a)$，代入直线方程得 $1+a=5$，故 $a=4$.
\end{enumerate}

\section*{四、解答题}
本题共 1 小题，共 12 分。

\begin{enumerate}[resume]
    \item （12分）已知数列 $\{a_n\}$ 中，$a_1=3$，$a_{n+1}=2a_n+1$.
    \begin{enumerate}
        \item 证明：数列 $\{a_n+1\}$ 是等比数列；
        \item 求 $\{a_n\}$ 的前 $n$ 项和 $S_n$.
    \end{enumerate}
    \daan{(1) 见解析\quad (2) $S_n=2^{n+2}-n-4$}
    \jieti 由 $a_{n+1}+1=2(a_n+1)$ 知 $\{a_n+1\}$ 是公比为 $2$ 的等比数列.
    \xiaoI 首项 $a_1+1=4$，故 $a_n+1=2^{n+1}$，即 $a_n=2^{n+1}-1$.
    \xiaoII $S_n=\sum_{k=1}^{n}(2^{k+1}-1)=2^{n+2}-n-4$.
\end{enumerate}

\end{document}
"""

BODY_GEOMETRY = r"""\graphicspath{{images/}}
\begin{document}

\begin{center}
    \LARGE{\textbf{2026 年测试卷（几何配图）}}
\end{center}

\vspace{0.5em}

\noindent\textbf{一、选择题：本题共1小题，每小题5分，共5分。}

\begin{enumerate}[itemsep=0.3em]
    \item 某几何体的三视图如图所示，则该几何体的体积为
    \begin{tasks}(4)
        \task $4$
        \task $6$
        \task $8$
        \task $12$
    \end{tasks}
\end{enumerate}

\noindent\textbf{四、解答题：本题共2小题，共24分。}

\begin{wrapfigure}{r}{0.30\textwidth}
\centering
\includegraphics[width=\linewidth]{fig1.png}
\caption*{第2题图}
\end{wrapfigure}
\begin{examenum}[start=2, itemsep=1.5cm]
    \item （12分）如图，在四棱锥 $Q-ABCD$ 中，底面 $ABCD$ 是正方形，$QA \perp$ 平面 $ABCD$.
    \begin{examenum}
        \item 证明：$BQ \perp AD$；
        \item 若 $QB=\sqrt{6}$，求平面 $QAD$ 与平面 $QBC$ 夹角的余弦值.
    \end{examenum}
    \answern

    \item （12分）三个几何体的三视图分别如图①②③所示，求它们的表面积之和.
\end{examenum}

\begin{figure}[H]
\centering
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{fig2.png}
\caption*{①}
\end{minipage}
\hfill
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{fig3.png}
\caption*{②}
\end{minipage}
\hfill
\begin{minipage}[t]{0.28\textwidth}
\centering
\includegraphics[width=\linewidth,height=2.5cm,keepaspectratio]{fig4.png}
\caption*{③}
\end{minipage}
\end{figure}

\end{document}
"""

BODY_TABLE = r"""\begin{document}

\begin{center}
    \LARGE{\textbf{2026 年测试卷（统计表格）}}
\end{center}

\vspace{0.5em}

\noindent\textbf{一、选择题：本题共1小题，每小题5分，共5分。}

\begin{enumerate}[itemsep=0.3em]
    \item 某校对学生的视力情况做调查，得到如下列联表，则

    \begin{center}
    \small
    \begin{tabular}{cccc}
    \toprule
    班级 & 有效 & 无效 & 合计 \\
    \midrule
    甲 & 40 & 10 & 50 \\
    乙 & 30 & 20 & 50 \\
    \midrule
    合计 & 70 & 30 & 100 \\
    \bottomrule
    \end{tabular}
    \captionof{table}{视力调查列联表}
    \end{center}

    \begin{tasks}(2)
        \task 有 $99\%$ 的把握认为有关
        \task 有 $95\%$ 的把握认为有关
        \task 没有 $95\%$ 的把握认为有关
        \task 数据不足，无法判断
    \end{tasks}
\end{enumerate}

\noindent\textbf{四、解答题：本题共1小题，共12分。}

\begin{examenum}[start=2, itemsep=1.5cm]
    \item （12分）根据上表数据，计算 $\chi^{2}$ 的观测值并说明理由.
\end{examenum}

\end{document}
"""

BODY_LONGOPT = r"""\graphicspath{{images/}}
\begin{document}

\begin{center}
    \LARGE{\textbf{2026 年测试卷（长选项与图片选项）}}
\end{center}

\vspace{0.5em}

\noindent\textbf{二、选择题：本题共2小题，每小题6分，共12分。}

\begin{enumerate}[itemsep=0.5em]
    \item 关于双曲函数，下列结论正确的是
    \begin{tasks}(2)
        \task 双曲正弦函数 $\sinh x$ 是增函数
        \task $\tanh(x+y) = \dfrac{\tanh x + \tanh y}{1 + \tanh x \tanh y}$
        \task $\cosh^{2} x - \sinh^{2} x = 1$
        \task $\sinh 2x = 2\sinh x \cosh x$
    \end{tasks}

    \item 下列图形中，既是轴对称图形又是中心对称图形的是
    \begin{tasks}(4)
        \task \includegraphics[width=0.12\textwidth]{fig5.png}
        \task \includegraphics[width=0.12\textwidth]{fig6.png}
        \task \includegraphics[width=0.12\textwidth]{fig1.png}
        \task \includegraphics[width=0.12\textwidth]{fig2.png}
    \end{tasks}
\end{enumerate}

\end{document}
"""

CASES = [
    {
        "id": "standard",
        "template": "gaokao-template.tex",
        "body": BODY_STANDARD,
        "images": 0,
    },
    {
        "id": "answer",
        "template": "gaokao-answer-template.tex",
        "body": BODY_ANSWER,
        "images": 0,
    },
    {
        "id": "geometry",
        "template": "gaokao-template.tex",
        "body": BODY_GEOMETRY,
        "images": 6,
    },
    {
        "id": "table",
        "template": "gaokao-template.tex",
        "body": BODY_TABLE,
        "images": 0,
    },
    {
        "id": "longopt",
        "template": "gaokao-template.tex",
        "body": BODY_LONGOPT,
        "images": 6,
    },
]


def main():
    for case in CASES:
        out_dir = FIXTURES / case["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        tex = preamble_of(case["template"]) + "\n" + case["body"]
        # 去掉模板里残留的示例注释行，避免误导
        tex = re.sub(r"^%.*\n", lambda m: m.group(0) if "=====" in m.group(0) or "──" in m.group(0) else "", tex, flags=re.M)
        (out_dir / f"{case['id']}.tex").write_text(tex, encoding="utf-8")
        if case["images"]:
            make_images(out_dir / "images", case["images"])
        print(f"[OK] {case['id']}.tex" + (f"  (+{case['images']} 张图)" if case["images"] else ""))


if __name__ == "__main__":
    main()
