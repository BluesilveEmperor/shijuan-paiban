# -*- coding: utf-8 -*-
"""Unit tests for the fixed clean() / fix_dollar_signs()."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from md2tex import clean, fix_dollar_signs

PASS = 0
FAIL = 0

def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f'  PASS {name}')
    else:
        FAIL += 1
        print(f'  FAIL {name}')
        print(f'    got : {got!r}')
        print(f'    want: {want!r}')

def check_even(name, s):
    global PASS, FAIL
    if s.count('$') % 2 == 0:
        PASS += 1
        print(f'  PASS {name} (even $)')
    else:
        FAIL += 1
        print(f'  FAIL {name} (odd $): {s!r}')

print('== clean() ==')

# 1. \right) D $\left(  — the just-added regex (bug fixed: $ re-emitted)
out = clean(r'C $\left( 1 , \frac { \sqrt { 6 } } { 2 } \right) D $\left( 1 , \frac { \sqrt { 1 0 } } { 2 } \right)$')
check('right-D-left', out,
      r'C $\left( 1 , \frac { \sqrt { 6}} { 2} \right)$ D $\left( 1 , \frac { \sqrt { 1 0}} { 2} \right)$')

# 2. $\right)$\cup merge no longer un-done by \right)-fix (line 113 bug)
out = clean(r'B. $\left(0,\frac{2}{3}\right)$\cup \left[\frac{8}{3},4\right]$$ C. $\left(0,\frac{1}{3}\right)$')
check('merge-cup', out,
      r'B. $\left(0,\frac{2}{3}\right)\cup \left[\frac{8}{3},4\right]$ C. $\left(0,\frac{1}{3}\right)$')

# 3. legit \right)^{n} must stay intact (previously corrupted)
out = clean(r'已知 $\left(x^{2}+\frac{1}{x^{3}}\right)^{n}$ 展开式')
check('right-protect', out,
      r'已知 $\left(x^{2}+\frac{1}{x^{3}}\right)^{n}$ 展开式')

# 4. legit closed span before option letter must NOT get extra $
out = clean(r'A $\left[ \frac { \sqrt { 6 } } { 2 } , + \infty \right]$ B $\left[ \frac { \sqrt { 1 0 } } { 2 } , + \infty \right]$')
check_even('closed-ab-options', out)
check('closed-ab-options-text', out,
      r'A $\left[ \frac { \sqrt { 6}} { 2} , + \infty \right]$ B $\left[ \frac { \sqrt { 1 0}} { 2} , + \infty \right]$')

# 5. \textcircled variants
out = clean(r'都有 $a _{i} \leq b _{k}$ $\textcircled{1}\forall i$ 与 $\textcircled$ { 2}')
check('textcircled-mixed', out,
      r'都有 $a _{i} \leq b _{k}$ $\cir{1}\forall i$ 与 \cir { 2}')

# 6. plain \textcircled{2} inside math
out = clean(r'由 $\textcircled{2}$ 可知')
check('textcircled-in-math', out, r'由 $\cir{2}$ 可知')

# 7. broken \ln split merge still works
out = clean(r'函数 $f(x) = \cos x \cdot \ln $\left(2^x + 2^{-x}\right)$ 在区间')
check('ln-merge', out,
      r'函数 $f(x) = \cos x \cdot \ln \left(2^x + 2^{-x}\right)$ 在区间')

# 8. CJK guard: option letter spans not merged
out = clean(r'已知数列 $\{a_{n}\}$ 是等差数列，若 $s$ 、 $t$ 、 $p\in \mathbf{N}^{*}$ ，则 “ $2a_{t} = a_{s} + a_{p}$ ”')
check('cjk-guard', out,
      r'已知数列 $\{a_{n}\}$ 是等差数列，若 $s$ 、 $t$ 、 $p\in \mathbf{N}^{*}$ ，则 “ $2a_{t} = a_{s} + a_{p}$ ”')

# 9. odd-$ final guard: stray trailing $ dropped
out = clean(r'求 $f(x)$ 的极值$')
check('odd-guard', out, r'求 $f(x)$ 的极值')

# 10. text-mode bare sin wrapped (the 5 TEXT cases)
out = clean(r'处的切线方程为 y x= − −( ln 2)( 1).')
check('text-sin-wrap', out, r'处的切线方程为 y x= − −( $ln 2$)( 1).')

# 11. \right) directly followed by CJK in TEXT mode (rare)
out = clean(r'且 \left(0,1\right)且 f(x)$')
check('text-right-cjk', out, r'且 $\left(0,1\right)$且 f(x)')

print('== fix_dollar_signs() ==')

# odd inline $ -> drop last $
check('fds-odd-mid', fix_dollar_signs(r'求 $f(x) 的值$ 且 $g(x) > 0$ x$'),
      r'求 $f(x) 的值$ 且 $g(x) > 0$ x')
# even -> untouched
check('fds-even', fix_dollar_signs(r'$a$ 和 $b$'), r'$a$ 和 $b$')
# single stray $
check('fds-single', fix_dollar_signs(r'已知实数 x$ 的取值'), r'已知实数 x 的取值')
# mathrm{A}. fix: empty-content form -> plain option letter, stray $ dropped
check('fds-mathrm', fix_dollar_signs(r'$\mathrm{B}.$y = x$'),
      r'B.y = x')

print()
print(f'TOTAL: {PASS} pass, {FAIL} fail')
sys.exit(1 if FAIL else 0)
