# -*- coding: utf-8 -*-
"""finalize_paper 一键收尾回归测试（需要 xelatex，缺失时整文件 skip）。

覆盖（ARTIFACT-001 / ARTIFACT-002 / ARTIFACT-004）：
1. 一键收尾生成完整标准产物集（学生版 / 教师版 / 教师版-考试 /
   答题卡-A4 / 答题卡-A3 的 tex+pdf + build.py）
2. 幂等：重复运行退出码仍为 0，产物不丢
3. 答案文档（文件名含「答案」）只出三件：tex/pdf + build.py，
   不生成教师版 / 学生版 / 答题卡
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

import gen_answer_sheet as G  # noqa: E402  复用其 xelatex 探测逻辑

ROOT = Path(__file__).resolve().parent.parent
FINALIZE = ROOT / 'scripts' / 'finalize_paper.py'

if not G.find_xelatex():
    print('SKIP: 未找到 xelatex，test_finalize 需要真实编译环境')
    sys.exit(0)

fails = []


def check_true(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def run_finalize(target):
    r = subprocess.run([sys.executable, str(FINALIZE), str(target)],
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


# ---------------------------------------------------------------- 样本试卷
# 精简版高考模板：只保留 gen_teacher / gen_answer_sheet / build.py 都需要的
# 宏包与环境（examenum / \blank / \answern），编译快且不依赖图片目录。
PAPER = r"""\documentclass[12pt, a4paper]{ctexart}
\usepackage{amsmath, amssymb}
\usepackage[shortlabels]{enumitem}
\newlist{examenum}{enumerate}{3}
\setlist[examenum,1]{label=\arabic*., leftmargin=2em, itemsep=0.3em}
\newcommand{\blank}{\underline{\hspace{2cm}}}
\newcommand{\answern}{\par\vspace{3em}}
\begin{document}
\begin{center}
    {\LARGE\textbf{2026 年测试模拟卷}}\\[0.4em]
\end{center}

\noindent\textbf{一、选择题：本题共2小题，每小题5分，共10分。}
\begin{enumerate}[itemsep=0.3em]
    \item 第一题
    \item 第二题
\end{enumerate}

\noindent\textbf{二、选择题：本题共1小题，每小题6分，共6分。在每小题给出的选项中，有多项符合题目要求。}
\begin{enumerate}[start=3, itemsep=0.5em]
    \item 第三题
\end{enumerate}

\noindent\textbf{三、填空题：本题共2小题，每小题5分，共10分。}
\begin{enumerate}[start=4, itemsep=0.8em]
    \item 第四题 \blank.
    \item 第五题 \blank.
\end{enumerate}

\noindent\textbf{四、解答题：本题共2小题，共30分。解答应写出文字说明、证明过程或演算步骤。}
\begin{examenum}[start=6, itemsep=2.5cm]
    \item （13分）第六题
    \item （17分）第七题
\end{examenum}
\end{document}
"""

# ---------------------------------------------------------------- 1+2 试题卷
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    src = d / '2026测试模拟卷.tex'
    src.write_text(PAPER, encoding='utf-8')
    stem = src.stem

    rc, out = run_finalize(src)
    check_true('finalize-rc0', rc == 0, f'rc={rc}\n{out[-1500:]}')

    artifacts = [
        f'{stem}.pdf',
        f'{stem}-学生版.tex', f'{stem}-学生版.pdf',
        f'{stem}-教师版.tex', f'{stem}-教师版.pdf',
        f'{stem}-教师版-考试.tex', f'{stem}-教师版-考试.pdf',
        f'{stem}-答题卡-A4.tex', f'{stem}-答题卡-A4.pdf',
        f'{stem}-答题卡-A3.tex', f'{stem}-答题卡-A3.pdf',
        'build.py',
    ]
    for name in artifacts:
        check_true(f'artifact-{name}', (d / name).exists(), '缺失')

    # 幂等：产物已齐全时重跑，退出码仍为 0
    rc, out = run_finalize(src)
    check_true('finalize-idempotent', rc == 0, f'rc={rc}\n{out[-1500:]}')
    for name in artifacts:
        check_true(f'idempotent-{name}', (d / name).exists(), '重跑后缺失')

# ---------------------------------------------------------------- 3 答案文档
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    ans = d / '2026测试模拟卷-答案.tex'
    ans.write_text(PAPER, encoding='utf-8')
    stem = ans.stem

    rc, out = run_finalize(ans)
    check_true('answer-rc0', rc == 0, f'rc={rc}\n{out[-1500:]}')
    check_true('answer-pdf', (d / f'{stem}.pdf').exists())
    check_true('answer-build-py', (d / 'build.py').exists())
    check_true('answer-no-teacher',
               not (d / f'{stem}-教师版.tex').exists(), '答案文档不应生成教师版')
    check_true('answer-no-student',
               not (d / f'{stem}-学生版.tex').exists(), '答案文档不应生成学生版')
    check_true('answer-no-sheet',
               not (d / f'{stem}-答题卡-A4.tex').exists(), '答案文档不应生成答题卡')

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL FINALIZE TESTS PASSED')
