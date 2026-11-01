# -*- coding: utf-8 -*-
"""教师版生成回归测试。

重点锁住两个历史问题：
1. v3 内联脚本用 content.find("[start=15, itemsep=2.5cm]") 定位解答题块，
   itemsep 一改就返回 -1 并静默写出错误文件 —— 现在必须不依赖 itemsep 取值
2. 渲染器已按 meta.answer_space 插入过答题空间，gen_teacher 不得重复插入
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from gen_teacher import (  # noqa: E402
    build_teacher, build_student_space, locate_long_answer,
)

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


def make_tex(itemsep="2.5cm", with_space=False):
    space = "\n    \\answern" if with_space else ""
    return f"""\\documentclass{{ctexart}}
\\newcommand{{\\answern}}{{x}}
\\begin{{document}}
\\begin{{examenum}}[start=5, itemsep={itemsep}]
    \\item 第一题
    \\begin{{examenum}}
        \\item 子问
    \\end{{examenum}}{space}

    \\item 第二题
    \\begin{{examenum}}
        \\item 子问
    \\end{{examenum}}{space}

    \\item 第三题
\\end{{examenum}}
\\end{{document}}
"""


# ── 1. 定位不依赖 itemsep ──
for sep in ("2.5cm", "1.5cm", "0.5em", None):
    tex = make_tex(sep) if sep else make_tex().replace(", itemsep=2.5cm", "")
    start, end, start_num, opts = locate_long_answer(tex)
    check_true(f'locate-itemsep-{sep}', start is not None and start_num == 5,
               f'start={start} num={start_num}')
    if start is not None:
        check_true(f'locate-block-{sep}', '第一题' in tex[start:end] and '第三题' in tex[start:end])

# ── 2. 三种模式 ──
tex = make_tex("2.0cm")

out, err = build_teacher(tex, "normal")
check('normal-no-error', err, None)
check_true('normal-itemsep', r'itemsep=1.5em' in out, 'itemsep 未替换')
check('normal-gap-count', out.count(r'\vspace{6em}'), 2)   # 3 题 → 2 处间隙
check('normal-no-newpage', out.count(r'\newpage'), 0)

out, err = build_teacher(tex, "compact")
check_true('compact-itemsep', r'itemsep=0.5em' in out)
check('compact-gap-count', out.count(r'\vspace{2em}'), 2)

out, err = build_teacher(tex, "exam")
check_true('exam-itemsep-removed', 'itemsep' not in out.split(r'\begin{examenum}')[1].split(']')[0])
check('exam-newpage-count', out.count(r'\newpage'), 2)

# ── 3. 找不到解答题块要报错，不能静默 ──
out, err = build_teacher("\\begin{document}\n无解答题\n\\end{document}", "normal")
check_true('no-block-errors', out is None and err is not None, f'out={out} err={err}')

def count_calls(content, cmd=r'\answern'):
    """只统计实际调用，排除导言区 \newcommand{\answern}{...} 定义行。"""
    return sum(1 for ln in content.split('\n')
               if cmd in ln and '\\newcommand' not in ln)


# ── 4. 答题空间不重复插入 ──
tex_with = make_tex("2.0cm", with_space=True)
out, note = build_student_space(tex_with, "normal")
check('no-double-space', count_calls(out), 2)
check_true('double-space-note', '沿用' in (note or ''), f'note={note}')

# 无答题空间时应正常插入 2 处
tex_plain = make_tex("2.0cm", with_space=False)
out2, note2 = build_student_space(tex_plain, "normal")
check('space-inserted', count_calls(out2), 2)

# ── 5. 最后一个 item 之后不插 ──
check_true('space-not-after-last',
           out2.rstrip().endswith(r'\end{document}') and
           out2.rindex(r'\answern') < out2.rindex(r'\item 第三题'),
           '答题空间出现在末题之后')

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL TEACHER TESTS PASSED')
