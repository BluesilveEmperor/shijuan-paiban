#!/usr/bin/env python3
"""One-shot MD corruption fixes for the 5 remaining error files.

Each fix is verified (match count) and the original MD is backed up to
<name>.md.bak before editing. Idempotent: re-running reports 0 matches.
"""
import re
import shutil
import sys
from pathlib import Path

MD_DIR = Path(r"D:\Music\试题加题库\高三数学\.math-output" if sys.platform == 'win32'
              else "/mnt/d/Music/试题加题库/高三数学/.math-output")

results = []


def fix(name, fn):
    p = MD_DIR / f"{name}.md"
    if not p.exists():
        results.append((name, "NO FILE"))
        return
    s = p.read_text(encoding='utf-8')
    n = fn(p, s)
    if n > 0:
        bak = p.with_suffix('.md.bak')
        if not bak.exists():
            shutil.copy2(p, bak)
    results.append((name, f"{n} fixes"))


def replace_exact(old, new):
    def _f(p, s):
        n = s.count(old)
        if n:
            p.write_text(s.replace(old, new), encoding='utf-8')
        return n
    return _f


def yali3_h_t(p, s):
    """Delete MinerU-hallucinated h_t / h_t^* chains (月考三)."""
    pat1 = re.compile(r'\s*,?\s*h\\_t\s*=\s*h\\_t\^\\\*(?:\s*=\s*h\\_t\^\\\*)*')
    pat2 = re.compile(r'\s*,?\s*h\\_t\^\\\*(?:\s*=\s*h\\_t\^\\\*)*')
    pat3 = re.compile(r'\s*=\s*(?=\\\s*\))')  # trailing '=' left before \)
    n = len(pat1.findall(s)) + len(pat2.findall(s))
    s2 = pat1.sub('', s)
    s2 = pat2.sub('', s2)
    n3 = len(pat3.findall(s2))
    s2 = pat3.sub('', s2)
    if n + n3:
        p.write_text(s2, encoding='utf-8')
    return n + n3


def yali5_region(p, s):
    """雅礼五次月考: rebuild the (3) case-analysis spans with clean $ pairing."""
    end_anchor = r'\frac{(n+2)(n-1)}{2}.'
    j = s.find(end_anchor)
    if j < 0:
        return 0
    i = s.rfind('(3)以', 0, j)
    if i < 0:
        return 0
    new = (r'(3)以 $ a\_{i} $ 为首项的递增子列的最大长度不大于以 $ a\_{i} $ 为首项的子列的最大长度, '
           r'即 $ x\_{i}\leqslant n-i+1 $, 以 $ a\_{i} $ 为首项的递减子列的最大长度不大于以 $ a\_{i} $ 为首项的子列的最大长度, '
           r'即 $ y\_{i}\leqslant n-i+1 $, 而 $0\leqslant x\_i\leqslant n, 0\leqslant y\_i\leqslant n$, '
           r'所以 $|x\_i-y\_i|\leqslant \max\{x\_i,y\_i\}$, '
           r'所以 $\sum\_{i=1}^{n}|x\_i-y\_i|\leqslant\sum\_{i=1}^{n}\max\{x\_i,y\_i\}'
           r'\leqslant\sum\_{i=1}^{n}(n-i+1)+0=\frac{(n+2)(n-1)}{2}$.')
    p.write_text(s[:i] + new + s[j + len(end_anchor):], encoding='utf-8')
    return 1


def hnsfz5_distro(p, s):
    """附中五次月考: wrap the binomial/geometric distribution lines in math."""
    reps = [
        ('(2)X的分布列为P(X=k)=Cₙᵏpᵏ(1-p)ⁿ⁻ᵏ, k=0,1,2,…,n.',
         r'(2)X的分布列为 $P(X=k)=C_{n}^{k}p^{k}(1-p)^{n-k},\ k=0,1,2,\ldots,n.$'),
        ('Y的分布列为P(X=k)=(1-p)^(k-1)p,k=1,2,…,其中k为正整数',
         r'Y的分布列为 $P(Y=k)=(1-p)^{k-1}p,\ k=1,2,\ldots$ ，其中k为正整数'),
        ('记Sₙ=1+2(1-p)¹+3(1-p)²+⋯+(n-1)(1-p)ⁿ⁻²+n(1-p)ⁿ⁻¹,①',
         r'记 $S_{n}=1+2(1-p)+3(1-p)^{2}+\cdots+(n-1)(1-p)^{n-2}+n(1-p)^{n-1}$,①'),
        ('∴(1-p)Sₙ=1-p+2(1-p)²+3(1-p)³+⋯+(n-1)(1-p)ⁿ⁻¹+n(1-p)ⁿ,②',
         r'∴ $(1-p)S_{n}=1-p+2(1-p)^{2}+3(1-p)^{3}+\cdots+(n-1)(1-p)^{n-1}+n(1-p)^{n}$,②'),
        ('①-②,pSₙ=1+(1-p)+X(1-p)²+⋯+(1-p)ⁿ⁻¹-n(1-p)ⁿ= ',
         r'①-②, $pS_{n}=1+(1-p)+(1-p)^{2}+\cdots+(1-p)^{n-1}-n(1-p)^{n}=$ '),
    ]
    n = 0
    for old, new in reps:
        if old in s:
            s = s.replace(old, new)
            n += 1
    if n:
        p.write_text(s, encoding='utf-8')
    return n


def hnsfz2_normal_vectors(p, s):
    """附中月考二: rebuild the normal-vector systems; cos computation lives
    in the extracted image right after the corrupted run."""
    start = s.find('所以\\$\\left|\\begin{array}{ll}\\sqrt { 2 }x')
    end = s.find('![](images/5ede2d7')
    if start < 0 or end < 0 or end <= start:
        return 0
    new = (r'所以 $\left\{\begin{array}{l} \sqrt{2}x-\sqrt{2}z=0, \\ -\sqrt{2}x+\sqrt{2}y=0, \end{array}\right.$ '
           r'$\left\{\begin{array}{l} \sqrt{2}r-\sqrt{2}(\lambda+1)t=0, \\ \sqrt{2}s-\sqrt{2}t=0, \end{array}\right.$ '
           r'取 $\mathbf{m}=(1,1,1)$，$\mathbf{n}=(\lambda+1,\lambda,\lambda)$，计算式：')
    p.write_text(s[:start] + new + s[end:], encoding='utf-8')
    return 1


def yancheng_cases(p, s):
    """盐城: rebuild the ①②③ case analysis of the 融积数列 problem.

    Math verified: ① {a3=a1a2, a4=a1a2} -> d=0, a1 in {0,1};
    ② {a3=a1a2, a4=a1a3} -> d(1-a1)=0 -> d=0, a1 in {0,1};
    ③ {a3=a1a2, a4=a2a3} -> a1=2/3, d=-1/6  (or d=0 constants),
    consistent with the readable conclusion a_n = -n/6 + 5/6.
    """
    i3 = s.find('③若')
    if i3 < 0:
        return 0
    i1 = s.find('①若')
    icon = s.find('由①②③得')
    if i1 < 0 or icon < 0 or not (i1 < i3 < icon):
        return 0
    c1 = (r'①若 $\left\{\begin{array}{l} a_{3}=a_{1}a_{2}, \\ a_{4}=a_{1}a_{2}, \end{array}\right.$ '
          r'解得 $\left\{\begin{array}{l} a_{1}=0, \\ d=0, \end{array}\right.$ '
          r'或 $\left\{\begin{array}{l} a_{1}=1, \\ d=0, \end{array}\right.$' + '\n\n')
    c2 = (r'②若 $\left\{\begin{array}{l} a_{3}=a_{1}a_{2}, \\ a_{4}=a_{1}a_{3}, \end{array}\right.$ '
          r'解得 $\left\{\begin{array}{l} a_{1}=0, \\ d=0, \end{array}\right.$ '
          r'或 $\left\{\begin{array}{l} a_{1}=1, \\ d=0, \end{array}\right.$' + '\n\n')
    c3 = (r'③若 $\left\{\begin{array}{l} a_{3}=a_{1}a_{2}, \\ a_{4}=a_{2}a_{3}, \end{array}\right.$ '
          r'解得 $\left\{\begin{array}{l} a_{1}=\frac{2}{3}, \\ d=-\frac{1}{6}, \end{array}\right.$ '
          r'或 $\left\{\begin{array}{l} a_{1}=0, \\ d=0, \end{array}\right.$ '
          r'或 $\left\{\begin{array}{l} a_{1}=1, \\ d=0, \end{array}\right.$；' + '\n\n')
    p.write_text(s[:i1] + c1 + c2 + c3 + s[icon:], encoding='utf-8')
    return 3


fix('雅礼中学2025届高三月考试卷三数学参考答案', yali3_h_t)
fix('雅礼中学2025届高三第五次月考数学试题答案', yali5_region)
fix('湖南师大附中2025届高三第五次月考数学试题答案', hnsfz5_distro)
fix('湖南师范大学附属中学2025届高三上学期月考（二）数学答案', hnsfz2_normal_vectors)
fix('盐城市、南京市2024－2025学年度第一学期期末调研考试数学答案', yancheng_cases)

print('\n'.join(f'{r}: {n}' for r, n in results))
