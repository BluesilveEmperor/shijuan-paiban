# -*- coding: utf-8 -*-
"""答题卡生成回归测试（不需要 LaTeX，纯解析 / 规划逻辑）。

覆盖：
1. 小节标题的四种写法（\\noindent\\textbf / \\section* / 单选题 / 多项符合）
2. 顶层 \\item 计数：嵌套 examenum 不得计入
3. 分值的四种写法（本题满分 13 分 / 本小题满分13分 / （13分） / (13 分)）
4. 卷头标题清洗（不误伤"调研测试卷"）
5. 分页规划：无空版面、每面 ≤ block、19 题得 4 版面
6. 渲染产物：rules / choices / blanks 正确落进 \\gkSetup
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

import tempfile
from pathlib import Path
import gen_answer_sheet as G

fails = []

def check(name, actual, expected):
    if actual == expected:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}\n  actual:   {actual!r}\n  expected: {expected!r}')

def check_true(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


# ---------------------------------------------------------------- 样本试卷
PAPER = r"""\documentclass{ctexart}
\begin{document}
\begin{center}
    {\LARGE\textbf{湖州市 2025 学年第一学期期末调研测试卷}}\\[0.4em]
\end{center}

\noindent\textbf{一、选择题：本题共8小题，每小题5分，共40分。}
\begin{enumerate}[itemsep=0.3em]
    \item 第一题
    \begin{tasks}(4)
        \task A \task B \task C \task D
    \end{tasks}
    \item 第二题
    \item 第三题
    \item 第四题
    \item 第五题
    \item 第六题
    \item 第七题
    \item 第八题
\end{enumerate}

\noindent\textbf{二、选择题：本题共3小题，每小题6分，共18分。在每小题给出的选项中，有多项符合题目要求。}
\begin{enumerate}[start=9, itemsep=0.5em]
    \item 第九题
    \item 第十题
    \item 第十一题
\end{enumerate}

\noindent\textbf{三、填空题：本题共3小题，每小题5分，共15分。}
\begin{enumerate}[start=12, itemsep=0.8em]
    \item 十二题 \blank.
    \item 十三题 \blank.
    \item 十四题 \blank.
\end{enumerate}

\noindent\textbf{四、解答题：本题共5小题，共77分。}
\begin{examenum}[start=15]
    \item （本题满分 13 分）
    题目正文
    \begin{examenum}
        \item 第一问
        \item 第二问
        \begin{examenum}
            \item 子问
        \end{examenum}
    \end{examenum}
    \item （本小题满分15分）
    题目正文
    \item （15分）
    \item (17 分)
    \item （本题满分17分）
\end{examenum}
\end{document}
"""

SINGLE_ONLY = r"""\documentclass{ctexart}
\begin{document}
\begin{center}
    {\LARGE\textbf{2025 学年第一学期期末学业水平测试 高三数学试题卷}}\\[0.4em]
\end{center}
\noindent\textbf{一、单选题：本题共8小题，每小题5分，共40分．}
\begin{enumerate}
    \item 甲
    \item 乙
    \item 丙
    \item 丁
    \item 戊
    \item 己
    \item 庚
    \item 辛
\end{enumerate}
\section*{二、多项选择题}
\begin{enumerate}[start=9]
    \item 壬
\end{enumerate}
\noindent\textbf{三、填空题：本题共3小题}
\begin{enumerate}[start=12]
    \item 丙
\end{enumerate}
\noindent\textbf{四、解答题：本题共5小题}
\begin{examenum}[start=15]
    \item (13 分) 甲
    \item (15 分) 乙
    \item (15 分) 丙
    \item (17 分) 丁
    \item (17 分) 戊
\end{examenum}
\end{document}
"""


def parse(text: str) -> G.ExamSpec:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'x.tex'
        p.write_text(text, encoding='utf-8')
        return G.parse_exam_tex(p)


# ---------------------------------------------------------------- 1 & 2 & 3
spec = parse(PAPER)
check('single-count', spec.single, 8)
check('multi-count', spec.multi, 3)          # "多项符合" 需判为多选
check('blank-count', spec.blanks, 3)
check('solve-count', len(spec.solve_scores), 5)
check('solve-scores', spec.solve_scores, [13, 15, 15, 17, 17])   # 4 种写法
check('solve-start', spec.solve_start, 15)
check('choices', spec.choices, 11)
check('nested-not-counted', len(spec.solve_scores), 5)  # 嵌套子问不额外计数

# ---------------------------------------------------------------- 4
check('title-keep-测试卷', spec.title, '湖州市 2025 学年第一学期期末调研测试卷')

spec2 = parse(SINGLE_ONLY)
check('single-alt-title', spec2.single, 8)   # "单选题" 不含"选择"
check('multi-alt-title', spec2.multi, 1)
check('title-strip-学科尾缀', spec2.title, '2025 学年第一学期期末学业水平测试')
check('scores-halfwidth', spec2.solve_scores, [13, 15, 15, 17, 17])

# ---------------------------------------------------------------- 4b 卷头变体
# 真题卷（22-26）里出现的三种非常规卷头，逐条回归
HEAD_CASES = [
    # 2022 型：密级在前、标题用 \textbf{\LARGE{...}} 嵌套
    ('2022型', r"""\begin{document}
{\large\textbf{绝密☆启用前\quad 试卷类型：A}}
\vspace{1em}
\textbf{\LARGE{2022年普通高等学校招生全国统一考试}}\\[0.5em]
\textbf{\LARGE{数\hspace{1em}学}}
\noindent\textbf{本试卷共4页，22小题，满分150分．}
""", '2022年普通高等学校招生全国统一考试'),
    # 2023 型：\LARGE{\textbf{...\\...}}，标题内含换行
    ('2023型', r"""\begin{document}
\begin{center}
    \LARGE{\textbf{2023年普通高等学校招生全国统一考试\\新课标I卷数学}}
\end{center}
""", '2023年普通高等学校招生全国统一考试\u3000新课标I卷数学'),
    # 2025 型：完全不用 \textbf，用自定义 \subtitle / \subjecttitle
    ('2025型', r"""\begin{document}
\noindent\textbf{绝密{\bigstarraised}启用前}
\subtitle{2025年普通高等学校招生全国统一考试}
\subjecttitle{数\hspace{0.8em}学}
""", '2025年普通高等学校招生全国统一考试'),
    # 小节标题很长，不能被误当成卷头
    ('小节不抢标题', r"""\begin{document}
\begin{center}
    {\LARGE\textbf{2024年全国统一高考数学试卷\\新高考I卷}}\\[0.4em]
\end{center}
\noindent\textbf{一、选择题：本题共8小题，每小题5分，共40分。在每小题给出的四个选项中，
只有一项是符合题目要求的．}
""", '2024年全国统一高考数学试卷\u3000新高考I卷'),
]

for name, text, expect in HEAD_CASES:
    sp = parse(text)
    check(f'title-{name}', sp.title, expect)

# ---------------------------------------------------------------- 4c 非试题输入必须拒绝
import subprocess
GEN = Path(__file__).resolve().parent.parent / 'scripts' / 'gen_answer_sheet.py'

def run_gen(*a):
    r = subprocess.run([sys.executable, str(GEN), *a],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')

with tempfile.TemporaryDirectory() as td:
    ans = Path(td) / '某卷-答案.tex'
    ans.write_text(PAPER, encoding='utf-8')
    rc, out = run_gen(str(ans), '--print-spec')
    check('reject-答案文件', rc, 4)

    # 已有手工答题卡 → 不覆盖
    exam = Path(td) / '某卷.tex'
    exam.write_text(PAPER, encoding='utf-8')
    hand = Path(td) / '某卷-答题卡.tex'
    hand.write_text('% 手工版答题卡\n\\documentclass{ctexart}\n', encoding='utf-8')
    rc, out = run_gen(str(exam), '--no-compile')
    check('skip-手工版', rc, 5)
    check('skip-原文件未动', hand.read_text(encoding='utf-8'),
          '% 手工版答题卡\n\\documentclass{ctexart}\n')

    # --force 才允许覆盖
    rc, out = run_gen(str(exam), '--no-compile', '--force')
    check('force-覆盖', rc, 0)
    check_true('force-已改写', G.GEN_MARK in hand.read_text(encoding='utf-8'))

    # 再跑一次：这次是自己生成的，可以正常覆盖
    rc, out = run_gen(str(exam), '--no-compile')
    check('regen-自己生成的可覆盖', rc, 0)

# ---------------------------------------------------------------- 5
for name, ch, bl, sc, expect in [
    ('新高考19题', 11, 3, [13, 15, 15, 17, 17], 4),
    ('小测2解答', 8, 2, [10, 10], 2),
    ('单解答', 8, 2, [10], 1),
]:
    s = G.ExamSpec(source=Path('x.tex'), title='t', subject='数学')
    s.single, s.blanks, s.solve_start, s.solve_scores = ch, bl, ch + bl + 1, sc
    pages, block = G.choose_layout_params(s, 2)
    panels = G.simulate_panels(pages, s.solves, block, ch, 4, bl)
    check(f'pages-{name}', pages, expect)
    check_true(f'no-empty-{name}', all(e >= st for st, e in panels), f'{panels}')
    check_true(f'block-{name}', all(e - st + 1 <= block for st, e in panels), f'{panels}')

# 空版面必须被规避：7 题 12 分、12 选择 4 填空，不能出现空白答题框
s = G.ExamSpec(source=Path('x.tex'), title='t', subject='数学')
s.single, s.blanks, s.solve_start = 12, 4, 17
s.solve_scores = [10, 12, 12, 12, 12, 10, 10]
pages, block = G.choose_layout_params(s, 2)
panels = G.simulate_panels(pages, s.solves, block, 12, 4, 4)
check_true('no-empty-23题', all(e >= st for st, e in panels), f'pages={pages} {panels}')

# ---------------------------------------------------------------- 6
tex = G.render_tex(spec, layout='a4', pages=4, block=2, percol=4,
                   title=spec.title, subject='数学')
check_true('render-rules', 'rules   = {15/13,16/15,17/15,18/17,19/17}' in tex)
check_true('render-choices', 'choices = 11, percol = 4, blanks = 3' in tex)
check_true('render-layout', 'layout  = a4' in tex and 'a4paper' in tex)
check_true('render-usepackage', r'\usepackage{answersheet}' in tex)

tex3 = G.render_tex(spec, layout='a3', pages=2, block=2, percol=4,
                    title=spec.title, subject='数学')
check_true('render-a3', 'layout  = a3' in tex3 and 'a3paper' in tex3
           and 'paperwidth=420mm' in tex3)

# 转义
check_true('render-escape', r'\&' in G.render_tex(
    G.ExamSpec(source=Path('x.tex'), title='A&B', subject='数学',
               solve_start=1, solve_scores=[10]),
    layout='a4', pages=1, block=2, percol=4, title='A&B', subject='数学'))

# ---------------------------------------------------------------- 7 附图 / 三线表
TIKZ = r"""\begin{tikzpicture}[scale=0.6]\draw (0,0)--(2,0)--(1,1.5)--cycle;\end{tikzpicture}"""
TAB = r"""\begin{tabular}{|c|cc|}\hline 组别 & 良好 & 合计 \\ \hline 病例组 & 40 & 100 \\ \hline\end{tabular}"""

# 单张 tikz → 角图
aux = G.extract_aux("题目正文 " + TIKZ)
check('aux-single-tikz', [(m) for m, _, _ in aux], ['fig'])

# center 里并排两图（minipage）→ 通栏
two = (r"\begin{center}\begin{minipage}{0.32\textwidth}\centering " + TIKZ
       + r"\end{minipage}\hfill\begin{minipage}{0.32\textwidth}\centering "
       + TIKZ + r"\end{minipage}\end{center}")
aux = G.extract_aux(two)
check('aux-two-figs', [m for m, _, _ in aux], ['block'])

# 表格 → 通栏
aux = G.extract_aux("附：" + TAB)
check('aux-table', [m for m, _, _ in aux], ['block'])

# 同题多块要全部保留（渲染时合并，不能互相覆盖）
aux = G.extract_aux("甲 " + TAB + " 乙 " + TIKZ)
check('aux-multi', len(aux), 2)

# \caption / \label 必须剥掉（浮动环境外会报错）
aux = G.extract_aux(r"\begin{center}" + TAB + r"\caption{某某}\label{tab:1}\end{center}")
check_true('aux-strip-caption', "caption" not in aux[0][1] and "label" not in aux[0][1])

# 表格行数越多估得越高
h_small = G.extract_aux(r"\begin{tabular}{c}" + r"a \\ " + r"\end{tabular}")[0][2]
h_big = G.extract_aux(r"\begin{tabular}{c}" + r"a \\ " * 6 + r"\end{tabular}")[0][2]
check_true('aux-height-rows', h_big > h_small, f"{h_small} vs {h_big}")

# ---------------------------------------------------------------- 8 依赖宏包
PKGS, LIBS = G.extract_deps(r"""
\usepackage{amsmath,amssymb}
\usepackage{diagbox}
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{fancyhdr}
\usepackage{tikz}
\usetikzlibrary{calc,patterns}
""")
check_true('deps-keep-diagbox', "diagbox" in PKGS, f"{PKGS}")
check_true('deps-drop-geometry', "geometry" not in PKGS and "fancyhdr" not in PKGS, f"{PKGS}")
check_true('deps-tikzlib', LIBS == ["calc", "patterns"], f"{LIBS}")

# ---------------------------------------------------------------- 9 版面自适应
def mk(scores, figs):
    sp = G.ExamSpec(source=Path('x.tex'), title='t', subject='数学')
    sp.single, sp.blanks, sp.solve_start = 11, 3, 15
    sp.solve_scores = scores
    sp.aux = {q: [("block", "", h)] for q, h in figs.items()}
    return sp

# 图不高 → 维持 4 版面
pages, block, notes = G.fit_layout_for_aux(mk([13, 15, 15, 17, 17], {16: 3.0}), 2)
check('fit-normal-pages', pages, 4)
check('fit-normal-block', block, 2)

# 图过高（13.5cm 塞不进 12.9cm 的框）→ 自动每题独占一面
pages, block, notes = G.fit_layout_for_aux(mk([13, 15, 15, 17, 17], {17: 13.5}), 2)
check('fit-tall-block', block, 1)
check_true('fit-tall-notes', any("独占一面" in n for n in notes), f"{notes}")
boxes = G.estimate_box_heights(mk([13, 15, 15, 17, 17], {}), pages, block)
check_true('fit-tall-fits', 13.5 / boxes[17] <= G.FIT_RATIO,
           f"13.5/{boxes[17]:.1f}")

# ---------------------------------------------------------------- 10 渲染附图
sp = parse(PAPER)
sp.aux = {16: [("block", TAB, 3.0)], 18: [("fig", TIKZ, 4.5), ("block", TAB, 3.0)]}
tex = G.render_tex(sp, layout='a4', pages=4, block=2, percol=4,
                   title=sp.title, subject='数学')
check_true('render-gkblock', "\\gkBlock{16}{" in tex)
check_true('render-gkfig', "\\gkFig{18}{" in tex)
check_true('render-aux-before-gkmake',
           tex.index("\\gkFig{18}") < tex.index("\\gkMake"))
# 同题两个 block 必须合并成一次调用（重复调用会互相覆盖）
check('render-merge-blocks', tex.count("\\gkBlock{18}{"), 1)
check_true('render-aux-note', "附图/表：2 题" in tex)

# --no-figs 时不带任何附图
sp2 = parse(PAPER)
sp2.aux = {}
tex2 = G.render_tex(sp2, layout='a4', pages=4, block=2, percol=4,
                    title=sp2.title, subject='数学')
check_true('render-no-aux', "\\gkBlock" not in tex2 and "\\gkFig" not in tex2)

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL ANSWER-SHEET TESTS PASSED')
