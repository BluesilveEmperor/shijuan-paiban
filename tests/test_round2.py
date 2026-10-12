# -*- coding: utf-8 -*-
"""Tests for the new round of md2tex fixes (merge guards, stray braces, tables, parsing)."""
import os
import re
import sys


def to_native(p):
    """Map D:\\a\\b to /mnt/d/a/b when not running on Windows."""
    if os.name == 'nt' or not p.startswith('D:\\'):
        return p
    return '/mnt/d/' + p[3:].replace('\\', '/')


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import md2tex

fails = 0

def check(name, cond):
    global fails
    print(f'  {"PASS" if cond else "FAIL"} {name}')
    if not cond:
        fails += 1

print('== merge guards (clean) ==')
# Q6 华中师大: option-letter content must NOT merge
s = md2tex.clean(r'若对任意的 $x$ 都有 $g(x)=0$ ，则 $a$ 的值为（） A. -1 B. - $\sqrt{3}$ C. - $\sqrt{2}$ D. - $\frac{\sqrt{6}-\sqrt{2}}{2}$ 第6题图')
check('opt-dash-content no-merge', '$\\sqrt{2}$' in s and '$\\sqrt{3}$' in s)

# Q13 华中师大: separator-only content must NOT merge
s = md2tex.clean(r'在 $\Delta ABC$ 中, $AB = 3$ , $\overrightarrow{AD} = 2\overrightarrow{DB}$ , $\angle ACD = \frac{\pi}{3}$ , 则 $BC$ 的最大值为 ___.')
check('sep-content no-merge', '$\\overrightarrow{AD}' in s and '$\\angle ACD' in s)

# Q1 学军: pure option letters/empty options must NOT merge via pat_sup
s = md2tex.clean(r'已知集合 $A$ ,则 ( ) A. $\{-1,0,1\}$ B. C. D. $\phi$')
check('optlet-sup no-merge', '$\\phi$' in s)

# legit MinerU split still merges
s = md2tex.clean(r'已知 $\frac{1}{2}$\pi$ 成立')
check('legit-split merge', s == r'已知 $\frac{1}{2}\pi$ 成立' or '$\\frac{1}{2}\\pi$' in s)

print('== stray braces ==')
s = md2tex.clean(r'已知 $\{ a_{n} \}$} 的单极数列为1')
check('stray-close dropped', '}$}' not in s and '$\\{ a_{n} \\}$' in s)
s = md2tex._fix_stray_braces(r'$\left(x\right)$}')
check('stray-after-span', s == r'$\left(x\right)$')
s = md2tex._fix_stray_braces(r'\textbf{a} {b} \{c\}')
check('balanced-kept', s == r'\textbf{a} {b} \{c\}')

print('== cir flatten ==')
s = md2tex.clean(r'满足 $\cir{\cir{\scriptsize 1}}$ 或 ①')
check('nested-cir flat', '\\cir{1}' in s and '\\cir{\\cir' not in s)

print('== html table ==')
tab = md2tex._html_table_to_latex('<table><tr><td></td><td>出现</td><td>未出现</td><td>总计</td></tr>'
                                  '<tr><td>男</td><td>11</td><td></td><td>200</td></tr></table>')
check('table-rows', tab is not None and 'tabular' in tab and re.search(r'11 &\s*& 200', tab) is not None)
check('table-hline', '\\hline' in tab)

print('== display clean ==')
s = md2tex.clean_display(r'\frac {\sqrt {6}}{3}')
check('display-basic', s == r'\frac {\sqrt {6}}{3}')
s = md2tex.clean_display(r'\left( a+b \right) \cup D')
check('display-right-no-dollar', '$' not in s)

print('== convert() end-to-end (华中师大 MD) ==')
import tempfile, os
tmp = tempfile.mkdtemp()
tex = os.path.join(tmp, 't.tex')
md2tex.convert(to_native(r'D:\Music\试题加题库\高三数学\.math-output\湖北省武汉市华中师范大学第一附属中学2024-2025学年高三上学期十一月月度检测数学试卷.md'), tex, 'Images-x')
out = open(tex, encoding='utf-8').read()
check('no-html-table', '<table' not in out and '<td' not in out)
check('display-block-emitted', '\\[\\frac {\\sqrt {6}}{3}\\]' in out or '\\[\\frac{\\sqrt {6}}{3}\\]' in out)
# Q6 figure should attach to Q6's item (image 8f7b... after 函数 item, before 数列 item)
i_f = out.find('函数 $f(x) = A \\sin')
i_img = out.find('8f7b5644054f6efc31fedaf7a0aaf6938f529d971c79f4aa3f5c898b0bd1dc3b.jpg')
i_next = out.find('已知数列')
check('img-attribution', -1 < i_f < i_img < i_next)
# caption dropped
check('caption-dropped', '第6题图' not in out and '第11题图' not in out)

print('== convert() end-to-end (学军 MD, answer truncation) ==')
tex2 = os.path.join(tmp, 't2.tex')
md2tex.convert(to_native(r'D:\Music\试题加题库\高三数学\.math-output\浙江省杭州学军中学2024-2025学年高三上学期期末测试数学试卷.md'), tex2, 'Images-y')
out2 = open(tex2, encoding='utf-8').read()
check('answer-truncated', '参考答案' not in out2 and '⋯' not in out2 and '满分' not in out2)
check('phi-kept', '$\\phi$' in out2)

print('== convert() end-to-end (江岸 MD, table->tabular) ==')
tex3 = os.path.join(tmp, 't3.tex')
md2tex.convert(to_native(r'D:\Music\试题加题库\高三数学\.math-output\湖北省武汉市江岸区元月调考2025届高三数学试题.md'), tex3, 'Images-z')
out3 = open(tex3, encoding='utf-8').read()
check('table-converted', 'begin{tabular}' in out3 and '<table' not in out3)
check('table-content', '出现诊断问题人数' in out3)

print()
print(f'TOTAL: {fails} fail')
sys.exit(1 if fails else 0)
