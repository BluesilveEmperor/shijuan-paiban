# -*- coding: utf-8 -*-
"""宽度估算模型回归测试（TASKS-COL-003 / tex_width.py）

为什么需要这个文件
----------------
原实现按「字符数」摊算公式宽度，对**不可断行的长分式**严重低估：

    $\\dfrac{\\tanh x+\\tanh y}{1+\\tanh x\\tanh y}$   实际渲染宽 86.53pt

放进 tasks(2)（每列仅 200.4pt）时整个选项 286.3pt → 溢出 51.46pt。
本文件用**实测值**（XeLaTeX + ctexart + newtxmath，12pt）锁定模型精度，
防止再次退化成字符数估算。

覆盖：
1. 原子宽度标定（分式 / 根式 / 括号 / 算符名 / 中文 / 拉丁）
2. 整体选项宽度估算的误差上限
3. 列宽预算计算
4. 退列行为（文字可退到 1 列，图片下限 2 列）
"""
import sys
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

import tex_width as tw  # noqa: E402

fails = []


def check(name, actual, expected):
    if actual == expected:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}\n  actual:   {actual!r}\n  expected: {expected!r}')


def check_close(name, actual, expected, tol_pct=20.0):
    """宽度估算允许有误差，但误差必须在容忍范围内。"""
    if expected == 0:
        ok = abs(actual) < 1e-6
    else:
        err = abs(actual - expected) / expected * 100
        ok = err <= tol_pct
    if ok:
        print(f'PASS  {name}  ({actual:.1f} vs 实测 {expected:.1f})')
    else:
        err = abs(actual - expected) / expected * 100 if expected else 999
        fails.append(name)
        print(f'FAIL  {name}\n  actual:   {actual:.1f}\n  expected: {expected:.1f}'
              f'\n  误差 {err:.1f}% 超过 {tol_pct}%')


# ── 1. 原子宽度标定 ───────────────────────────────────────────────────
# 全部为 XeLaTeX + ctexart + newtxmath + amsmath，12pt 实测值
check_close('atom-cjk-5char', tw.text_width_pt('对任意实数'), 60.00)
check_close('atom-latin-hello', tw.text_width_pt('hello'), 24.16)
check_close('atom-math-x', tw.text_width_pt('$x$'), 5.91)
check_close('atom-math-digit', tw.text_width_pt('$1$'), 5.87)
check_close('atom-op-tanh', tw.text_width_pt('$\\tanh$'), 23.56)
check_close('atom-op-sin', tw.text_width_pt('$\\sin$'), 14.48)
check_close('atom-op-ln', tw.text_width_pt('$\\ln$'), 9.85)
check_close('atom-binop-plus', tw.text_width_pt('$+$'), 9.14)
check_close('atom-abs', tw.text_width_pt('$|z|$'), 12.04)
check_close('atom-paren', tw.text_width_pt('$(x+y)$'), 34.81)
check_close('atom-sqrt', tw.text_width_pt('$\\sqrt{x+1}$'), 33.19)
check_close('atom-cjk-punct', tw.text_width_pt('（　　）'), 41.20)

# 分式：宽度 = max(分子, 分母) + padding，不是两者之和
check_close('atom-frac-simple', tw.text_width_pt('$\\dfrac{a}{b}$'), 8.57)
check_close('atom-frac-nested', tw.text_width_pt('$\\dfrac{a_{n+1}}{n}$'), 24.18)
check_close('atom-frac-long',
            tw.text_width_pt('$\\dfrac{\\tanh x+\\tanh y}{1+\\tanh x\\tanh y}$'),
            86.53)

# ── 2. 整体选项宽度（真实多选题选项）────────────────────────────────
optA = '双曲正弦函数 $\\sinh x$ 在实数集上单调递增'
optB = ('对任意实数 $x,y$，都有 '
        '$\\tanh(x+y)=\\dfrac{\\tanh x+\\tanh y}{1+\\tanh x\\tanh y}$')
optC = '对任意实数 $x$，恒有 $\\cosh^{2}x-\\sinh^{2}x=1$'
optD = '对任意实数 $x$，恒有 $\\sinh 2x=2\\sinh x\\cosh x$'

# 实测（\sbox 量宽）
check_close('opt-A', tw.option_width_pt(optA), 217.45)
check_close('opt-B', tw.option_width_pt(optB), 286.29)
check_close('opt-C', tw.option_width_pt(optC), 216.91)
check_close('opt-D', tw.option_width_pt(optD), 232.25)

# 关键回归：估算值必须 **不小于** 实际值（宁可少用一列，也不允许溢出）
# 这是「放得下」判断可靠的前提
for nm, o, actual in [('A', optA, 217.45), ('B', optB, 286.29),
                      ('C', optC, 216.91), ('D', optD, 232.25)]:
    est = tw.option_width_pt(o)
    if est >= actual:
        print(f'PASS  opt-{nm}-not-underestimated ({est:.1f} >= {actual:.1f})')
    else:
        fails.append(f'opt-{nm}-not-underestimated')
        print(f'FAIL  opt-{nm}-not-underestimated\n'
              f'  估算 {est:.1f} < 实测 {actual:.1f} → 会误判为放得下')

# ── 3. 列宽预算 ──────────────────────────────────────────────────────
check_close('budget-cols4', tw.column_budget_pt(4), 88.2)
check_close('budget-cols2', tw.column_budget_pt(2), 200.4)
check_close('budget-cols1', tw.column_budget_pt(1), 424.7)

# ── 4. 退列行为 ──────────────────────────────────────────────────────
opts9 = [optA, optB, optC, optD]
check('fits-cols4', tw.fits_columns(opts9, 4), False)
check('fits-cols2', tw.fits_columns(opts9, 2), False)
check('fits-cols1', tw.fits_columns(opts9, 1), True)
# 文字选项：可退到 1 列
check('choose-text-fallback-1', tw.choose_tasks_cols(opts9), 1)

# 图片选项：下限 2 列（TASKS-COL-002 禁止图片用 tasks(1)）
img_opts = [r'\includegraphics[width=0.12\textwidth]{a.png}'] * 4
check('choose-image-floor-2', tw.choose_tasks_cols(img_opts), 2)

# 中等长度文字：实测 optC=216.9pt / optD=232.2pt，均超过 tasks(2) 每列
# 200.4pt → 2 列放不下，退到 1 列
med = ['对任意实数 $x$，恒有 $\\cosh^{2}x-\\sinh^{2}x=1$',
       '对任意实数 $x$，恒有 $\\sinh 2x=2\\sinh x\\cosh x$']
check('choose-medium-fallback-1', tw.choose_tasks_cols(med), 1)

# 真正能进 2 列的中等长度：把选项缩短到 200pt 以内
med_ok = ['恒有 $\\cosh^{2}x-\\sinh^{2}x=1$',
          '恒有 $\\sinh 2x=2\\sinh x\\cosh x$']
check('choose-medium-2', tw.choose_tasks_cols(med_ok), 2)

# 短选项：4 列
short = ['$\\{0\\}$', '$\\{0,1,2\\}$', '$\\{1,2\\}$', '$\\{0,1\\}$']
check('choose-short-4', tw.choose_tasks_cols(short), 4)

# 空输入
check('choose-empty-4', tw.choose_tasks_cols([]), 4)

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL PASS')
