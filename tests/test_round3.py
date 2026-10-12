# -*- coding: utf-8 -*-
r"""Round-3 regression tests: the 5 fixes for the 6 low-error files.

1. _ok circled guard (Wenzhou: `$ ; \cir{2} $\forall` merge ate the forall `$`)
2. wrap_text_cmds skips \ensuremath{...} content (Henan: \ensuremath{$\mathrm{II}$})
3. TEX_HEADER no longer redefines \lim (Fuzhong-5: Limit controls error)
4. bare % escaped in clean()/clean_display()/table cells (Fuzhong-3: 25% comment)
5. text-mode & escaped; math-mode & preserved (array separators)
6. fix_dollar_signs mathrm option rule is now balanced (Lanzhou: `A.x \in A$`)
"""
import sys, os
sys.path.insert(0, r'D:\Desktop\shijuan-paiban\scripts')
os.environ['PYTHONIOENCODING'] = 'utf-8'
from md2tex import (clean, clean_display, wrap_text_cmds, fix_dollar_signs,
                    _fix_textmode, _html_table_to_latex, _escape_cell, TEX_HEADER)

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

# --- 1. circled guard: spans separated by ①-⑩ / \cir{n} must NOT merge ---
out = clean(r'满足 ① $x>0$ ② $x<1$')
check_true('circ-guard-raw', out.count('$') == 4, f'out={out!r}')

out = clean(r'则 $a$ ; \cir{2} $b$ 成立')
check_true('circ-guard-cir-cmd', out.count('$') == 4, f'out={out!r}')

# control: legit adjacent merge still happens when between-content is plain
out = clean(r'函数 $f(x) = \cos x \cdot \ln $\left(2^x + 2^{-x}\right)$ 在区间')
check_true('merge-still-works', r'\ln \left(2^x + 2^{-x}\right)$' in out.replace('  ', ' '),
           f'out={out!r}')

# --- 2. wrap_text_cmds: \ensuremath content not double-wrapped ---
out = wrap_text_cmds(r'是 \ensuremath{\mathrm{II}} 型')
check('ens-single', out, r'是 \ensuremath{\mathrm{II}} 型')

out = wrap_text_cmds(r'是 \ensuremath{\mathrm{I}\mathrm{II}} 型')
check('ens-sequential', out, r'是 \ensuremath{\mathrm{I}\mathrm{II}} 型')

out = wrap_text_cmds(r'甲 \ensuremath{\mathrm{II}} 乙 \ensuremath{\mathrm{III}} 丙')
check('ens-multiple', out, r'甲 \ensuremath{\mathrm{II}} 乙 \ensuremath{\mathrm{III}} 丙')

# control: bare text-mode \mathrm still wrapped
out = wrap_text_cmds(r'型号 \mathrm{II} 系列')
check('bare-mathrm-wrapped', out, r'型号 $\mathrm{II}$ 系列')

# control: math-mode \mathrm untouched
out = wrap_text_cmds(r'设 $x \in \mathrm{A}$ 集')
check('math-mathrm-untouched', out, r'设 $x \in \mathrm{A}$ 集')

# --- 3. TEX_HEADER must not redefine \lim ---
check_true('lim-not-redefined', r'\renewcommand{\lim}' not in TEX_HEADER)

# --- 4. bare % escaped ---
out = clean(r'利润增加了25%，则 $x$ 为')
check_true('pct-clean', r'25\%' in out, f'out={out!r}')

out = clean(r'已有 \% 转义不重复处理')
check_true('pct-no-double', r'\%' in out and r'\\%' not in out, f'out={out!r}')

check('pct-display', clean_display('覆盖率 25%'), r'覆盖率 25\%')

check('pct-cell', _escape_cell('增加25%的利润'), r'增加25\%的利润')

tab = _html_table_to_latex('<table><tr><td>年份</td><td>利润</td></tr>'
                           '<tr><td>2024</td><td>增加25%的利润</td></tr></table>')
check_true('pct-table', tab is not None and r'增加25\%的利润' in tab, f'tab={tab!r}')

# --- 5. text-mode & escaped; math-mode & preserved ---
check('amp-text', _fix_textmode(r'A & B'), r'A \& B')

m = r'$\left(\begin{array}{cc}a & b\\c & d\end{array}\right)$'
check('amp-math-preserved', _fix_textmode(m), m)

check('amp-cell-entity', _escape_cell('A &amp; B'), r'A \& B')
check('amp-cell-raw', _escape_cell('P(AB) & 0.5'), r'P(AB) \& 0.5')

# --- 6. fix_dollar_signs mathrm option rule is balanced ---
check('fds-mathrm-balanced', fix_dollar_signs(r'$\mathrm{A}.x \in A$ 是'),
      r'A. $x \in A$ 是')

# Lanzhou shape: option spans back to back, must stay $-balanced
out = fix_dollar_signs(r'$\mathrm{A}.x \in A$ 是 $x \in B$ 的充分条件')
check_true('fds-mathrm-lanzhou', out.count('$') % 2 == 0 and r'A. $x \in A$' in out,
           f'out={out!r}')

# empty-content form falls back to plain letter (odd $ then dropped)
check('fds-mathrm-empty', fix_dollar_signs(r'$\mathrm{B}.$y = x$'), r'B.y = x')

# --- 7. sqrt escaped-space protection (附中二月考: \ensuremath{\sqrt{\}} EOF) ---
# text-mode √2 -> \ensuremath{\sqrt{2}} (digit absorbed, braces balanced)
out = clean(r'侧棱长为√2，P为动点')
check('sqrt-digit-text', out, r'侧棱长为\ensuremath{\sqrt{2}}，P为动点')

# √ without following digit keeps the escaped-space form intact
out = clean(r'根号√后无数字')
check('sqrt-bare-kept', out, r'根号\ensuremath{\sqrt{\ }}后无数字')

# math-mode display: √3 -> \sqrt{3}
check('sqrt-digit-display', clean_display('面积为√3'), r'面积为\sqrt{3}')

# `}` whitespace strip must not eat escaped spaces.  The bare _{2}/^{3}
# fragments are additionally wrapped by the engine's SUBWRAP (text-mode
# _ is a LaTeX error), so the expected output carries $ delimiters and
# the stripped inter-fragment spaces.
out = clean(r'x_{ 2 } 与 y^{ 3 } 归一化')
check('brace-norm-still-works', out, r'$x_{2}$与$y^{3}$归一化')

# end-to-end: the exact 附中二 source line must yield balanced braces
out = clean(r'水平放置的正三棱台 =4，侧棱长为√2，P为棱 上的动点.')
check_true('fuzhong2-line-balanced',
           out.count('{') == out.count('}') and r'\ensuremath{\sqrt{2}}' in out,
           f'out={out!r}')

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL ROUND-3 TESTS PASSED')
