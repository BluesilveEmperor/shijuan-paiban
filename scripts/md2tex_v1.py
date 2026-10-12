#!/usr/bin/env python3
"""Convert MinerU markdown to gaokao LaTeX exam paper.
Strategy: preserve original text, only fix structure and minimal formula issues."""
import os, re, sys, argparse
from pathlib import Path

TEX_HEADER = r"""\documentclass[12pt, a4paper, oneside]{ctexart}
\usepackage{amsmath, amsthm, amssymb}
\usepackage[bookmarks=true, colorlinks, citecolor=blue, linkcolor=black]{hyperref}
\usepackage{newtxmath}
\usepackage[a4paper, margin=2.5cm, footskip=1cm]{geometry}
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{数学试题第\thepage 页（共\pageref{LastPage}页）}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\usepackage{graphicx}
\usepackage{diagbox}
\usepackage{makecell}
\usepackage{caption}
\usepackage{float}
\usepackage{tikz}
\usepackage{pifont}
\usepackage{tasks}
\settasks{label=\Alph*.,label-width=1.8em,item-indent=2.4em,label-offset=0.5em,column-sep=2em,before-skip=0pt,after-skip=0pt}
\usepackage[shortlabels]{enumitem}
\newlist{examenum}{enumerate}{3}
\setlist[examenum,1]{label=\arabic*.,leftmargin=2em,itemsep=0.3em,parsep=0em}
\setlist[examenum,2]{label=(\arabic*),leftmargin=1.5em,itemsep=0.1em,parsep=0em}
\setlist[examenum,3]{label=(\roman*),leftmargin=1.5em,itemsep=0.1em,parsep=0em}
\newcommand{\Parallel}{\raisebox{0.1ex}{\rotatebox[origin=c]{-20}{$\parallel$}}}
\newcommand{\bigstarraised}{\raisebox{0.2ex}{$\bigstar$}}
\newcommand{\blank}{\underline{\hspace{2cm}}}
\newcommand{\mi}{\mathrm{i}}
\newcommand{\me}{\mathrm{e}}
\newcommand{\cir}[1]{\mbox{\ding{\numexpr171+#1\relax}}}
\newcommand{\cirdig}[1]{\mbox{\ding{\numexpr171+#1\relax}}}
\newcommand{\unitII}{\ensuremath{\mathrm{II}}}
"""

def clean(s):
    """Formula cleaning for MinerU OCR output."""
    # MinerU answer MDs use \( ... \) inline math delimiters alongside $...$;
    # normalize to $ so the rest of the pipeline sees one delimiter form.
    s = s.replace('\\(', '$').replace('\\)', '$')
    # MinerU sometimes escapes the math delimiter itself: \$\left... -> $\left...
    s = re.sub(r'\\\$(\s*\\(?:left|begin))', r'$\1', s)
    # Strip private-use-area garbage chars from broken PDF font encodings
    s = re.sub(r'[\ue000-\uf8ff]', '', s)
    # Non-standard slanted negations -> standard forms (amssymb has no \neqslant)
    s = s.replace('\\neqslant', '\\neq')
    # MinerU typo: \dotimes -> \dots; collapse \dots runs
    s = s.replace('\\dotimes', '\\dots')
    s = re.sub(r'(?:\\dots\s*){2,}', r'\\dots ', s)
    # Unicode math symbols -> ensuremath (safe inside or outside math mode)
    for i, ch in enumerate('①②③④⑤⑥⑦⑧⑨⑩', 1):
        s = s.replace(ch, f'\\cir{{{i}}}')
    for ch, repl in [('△', '\\ensuremath{\\triangle}'), ('▲', '\\ensuremath{\\blacktriangle}'),
                     ('★', '\\ensuremath{\\bigstar}'), ('Ⅰ', '\\ensuremath{\\mathrm{I}}'),
                     ('Ⅱ', '\\ensuremath{\\mathrm{II}}'), ('π', '\\ensuremath{\\pi}'),
                     ('∞', '\\ensuremath{\\infty}'), ('≤', '\\ensuremath{\\le}'),
                     ('≥', '\\ensuremath{\\ge}'), ('≠', '\\ensuremath{\\ne}'),
                     ('∈', '\\ensuremath{\\in}'), ('⊥', '\\ensuremath{\\perp}'),
                     ('∥', '\\ensuremath{\\parallel}'), ('±', '\\ensuremath{\\pm}'),
                     ('×', '\\ensuremath{\\times}'), ('÷', '\\ensuremath{\\div}'),
                     ('°', '\\ensuremath{^{\\circ}}'), ('√', '\\ensuremath{\\sqrt{\\ }}'),
                     ('∴', '\\ensuremath{\\therefore}'), ('∵', '\\ensuremath{\\because}')]:
        s = s.replace(ch, repl)
    # √2 -> \sqrt{2}: absorb digits following a bare radical (else we emit an
    # empty \sqrt{\ } and a stranded 2)
    s = re.sub(r'\\ensuremath\{\\sqrt\{\\ \}\}(\d)', r'\\ensuremath{\\sqrt{\1}}', s)
    # Flatten nested \cir / strip size commands inside \cir
    # (e.g. \textcircled{\scriptsize ①} -> \cir{\cir{\scriptsize 1}})
    s = re.sub(r'\\cir\s*\{\s*\\(?:scriptsize|small|footnotesize|tiny)\s*', r'\\cir{', s)
    s = re.sub(r'\\cir\s*\{\s*\\cir\s*\{\s*(\d+)\s*\}\s*\}', r'\\cir{\1}', s)
    # Escape bare % (LaTeX comment char) -- MinerU emits raw percentages
    s = re.sub(r'(?<!\\)%', r'\\%', s)
    # Whitespace / brace normalization (keep `\ ` escaped spaces intact --
    # stripping them turned \sqrt{\ } into the brace-unbalanced \sqrt{\})
    s = re.sub(r'_\s*\{\s*', '_{', s)
    s = re.sub(r'\^\s*\{\s*', '^{', s)
    s = re.sub(r'(?<!\\)\s*\}', '}', s)
    s = re.sub(r'\\\\(sin|cos|tan|log|ln|lim|max|min|sup|inf|det|exp|gcd|lg|cot|sec|csc|arcsin|arccos|arctan|sinh|cosh|tanh|sqrt|frac|dfrac|binom|sum|int|prod)\b', r'\\\1', s)
    s = s.replace('\\in fty', '\\infty')
    s = re.sub(r'_{3,}', lambda m: '\\blank', s)
    s = re.sub(r'\\left\\lbracket', r'\\left[', s)
    s = re.sub(r'\\right\\rbracket', r'\\right]', s)
    s = re.sub(r'\\left\(([^)]*?)\\right\]', lambda m: f'\\left({m.group(1)}\\right)', s)
    s = re.sub(r'(?<!\\)#', r'\\#', s)
    # Strip any residual HTML tags (tables are pre-converted; this is defense)
    s = re.sub(r'</?(?:table|thead|tbody|tr|td|th)[^>]*>', ' ', s)
    # Fix: \right) D $\left(...  ->  \right)$ D $\left(...  (lost closer before option letter)
    # Guards: only after \right)] (not plain parens), not already closed by $,
    # replacement must re-emit the $ that opens the next option's math.
    s = re.sub(r'(\\right[\)\]])(?!\s*\$)(\s+)([A-D][\.、．]?)(\s*)\$(?=\\)',
               lambda m: m.group(1) + '$' + m.group(2) + m.group(3) + m.group(4) + '$', s)
    # Fix \textcircled (invalid in math mode) -> \cir, also broken \textcircled$ forms
    # (consume an optional orphan $ before \textcircled: $\textcircled$ {2} -> \cir {2})
    s = re.sub(r'\$?\\textcircled\s*\$', r'\\cir', s)
    s = s.replace('\\textcircled', '\\cir')
    # Merge MinerU-split math segments, iteratively:
    #   $A$\cmd B$ -> $A\cmd B$   /   $A$^{n}$ -> $A^{n}$   /   $$ -> $
    _MC = (r'(?:left|right|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr|'
           r'mathbf|mathrm|mathbb|mathcal|mathfrak|mathit|displaystyle|textstyle|'
           r'frac|dfrac|tfrac|sqrt|overset|underset|stackrel|binom|'
           r'lvert|rvert|Vert|vert|lfloor|rfloor|lceil|rceil|langle|rangle|'
           r'overline|underline|hat|vec|dot|ddot|tilde|widetilde|widehat|overbrace|underbrace|'
           r'begin|end|limits|nolimits|operatorname|text|mathop|'
           r'leftarrow|rightarrow|Rightarrow|Leftarrow|Leftrightarrow|mapsto|'
           r'leq|geq|neq|approx|equiv|subset|subseteq|supset|supseteq|'
           r'cup|cap|setminus|times|cdot|pm|mp|forall|exists|infty|emptyset|varnothing|'
           r'lim|sum|prod|int|iint|partial|nabla|cdots|vdots|ddots|dots|ldots|quad|qquad|'
           r'sin|cos|tan|cot|sec|csc|arcsin|arccos|arctan|sinh|cosh|tanh|ln|log|lg|'
           r'exp|min|max|arg|deg|dim|gcd|hom|ker|triangle|angle|perp|parallel|cong|sim|'
           r'propto|notin|land|lor|lnot|oplus|ominus|otimes|oint|bigsqcup|bigcap|bigcup)')
    pat_cmd = re.compile(r'\$([^$]*[^\s$][^$]*)\$\\' + _MC + r'(?![a-zA-Z])')
    pat_sup = re.compile(r'\$([^$]*[^\s$][^$]*)\$([\\^_])')
    _CJK = re.compile(r'[一-鿿　-〿＀-￯]')
    _OPT = re.compile(r'^\s*[A-Za-z][\.、．]?\s*$')
    # Option-boundary guards: never merge two legit spans when the text between
    # them is an option marker (A. / B、), pure option letters, a lone separator,
    # or contains a circled-number marker (①/② act as enumeration separators;
    # by merge time they are already \cir{n}).
    _OPTG = re.compile(r'[A-D][\.、．]')
    _OPTLET = re.compile(r'^\s*[A-D](?:\s+[A-D])*\s*$')
    _SEP = re.compile(r'^\s*[,，;；、]\s*$')
    # Pure-punctuation span interior (ASCII "." "," ")" quotes ...): MinerU
    # emits these as split artifacts like "$ .$\therefore"; merging them
    # forward eats the next span's opening $ and exposes the command to text
    # mode (_fix_textmode then wraps \therefore mid-formula, shattering it).
    _PUNCT = re.compile(r'^[^\w\\{}]*$')
    _CIRC = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]|\\cir(?![a-zA-Z])')

    def _ok(content):
        if _CJK.search(content) or _OPT.match(content) or _CIRC.search(content):
            return False
        if _OPTG.search(content) or _OPTLET.match(content) or _SEP.match(content) or _PUNCT.match(content):
            return False
        return True

    for _ in range(10):
        s2 = pat_cmd.sub(lambda m: m.group(0) if not _ok(m.group(1))
                         else '$' + m.group(1) + m.group(0).rsplit('$', 1)[-1], s)
        s2 = pat_sup.sub(lambda m: m.group(0) if not _ok(m.group(1))
                         else '$' + m.group(1) + m.group(0).rsplit('$', 1)[-1], s2)
        s2 = s2.replace('$$', '$')
        if s2 == s:
            break
        s = s2
    # Wrap \mathbf/\mathrm/\mathbb/\mathcal occurring in TEXT mode with $...$
    s = wrap_text_cmds(s)
    # Text-mode-only structural fixes ($-context aware)
    s = _fix_textmode(s)
    s = re.sub(r'\\complement\s*_', r'\\complement', s)
    # Drop stray unmatched closing braces (e.g. MinerU `$\{a_n\}$}`)
    s = _fix_stray_braces(s)
    # Balance: collapse any residual $$
    s = s.replace('$$', '$')
    # Final guard: odd inline $ count -> drop the last $ (stray trailing marker)
    if s.count('$') % 2 == 1:
        i = s.rfind('$')
        s = s[:i] + s[i + 1:]
    return s


_RIGHT_RE = re.compile(r'\\right([\)\]])')
_LEFT_RE = re.compile(r'\\left(?![a-zA-Z])')
_TRIANGLE_RE = re.compile(r'\\triangle(?![a-zA-Z])')
_CJKSTOP = re.compile(r'[一-鿿　-〿＀-￯…]')


def _match_left_group(s, j):
    """End index of the \\right<delim> matching a text-mode \\left opened at j.

    Returns -1 when no balanced \\right follows (leave the \\left untouched).
    """
    bal = 1
    n = len(s)
    while j < n:
        if s.startswith('\\left', j) and not s[j + 5:j + 6].isalpha():
            bal += 1
            j += 5
            continue
        if s.startswith('\\right', j) and not s[j + 6:j + 7].isalpha():
            bal -= 1
            j += 6
            while j < n and s[j] in ' \t':
                j += 1
            if j < n:
                if s[j] == '\\':
                    j += 2
                elif not s[j].isalpha():
                    j += 1
            if bal == 0:
                return j
            continue
        j += 1
    return -1
_FRAC_RE = re.compile(r'\\[dt]?frac\s*\{')
_SQRT_RE = re.compile(r'\\sqrt\s*(?:\[[^\]]*\])?\s*\{')
_THUS_RE = re.compile(r'\\(?:therefore|because)(?![a-zA-Z])')
_FUNC_RE = re.compile(r'(sin|cos|tan|log|ln|lim|max|min|sup|exp|gcd|lg|cot|sec|csc'
                      r'|arcsin|arccos|arctan|sinh|cosh|tanh)\s+(\w)')
_DELTA_RE = re.compile(r'(Delta|triangle)\b')


def _read_group(s, i):
    r"""Read a balanced {...} group starting at s[i] == '{'.

    Returns (content, index_after_closing_brace), or (None, i) if unbalanced.
    Escaped \{ / \} are literal characters and skipped.
    """
    depth = 0
    j = i
    n = len(s)
    while j < n:
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None, i


def _fix_stray_braces(s):
    """Drop unmatched closing braces (MinerU artifacts like `$\\{a_n\\}$}`).

    Walks the string tracking group depth; `\\{`/`\\}` are literal chars and
    skipped. A `}` that would close below depth 0 is dropped.
    """
    out = []
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == '\\':
            out.append(s[i:i + 2])
            i += 2
            continue
        if ch == '{':
            depth += 1
            out.append(ch)
        elif ch == '}':
            if depth > 0:
                depth -= 1
                out.append(ch)
            # else: stray closer -> drop
        else:
            out.append(ch)
        i += 1
    return ''.join(out)


def clean_display(s):
    """Light cleanup for display-math block content (already in math mode)."""
    s = re.sub(r'[\ue000-\uf8ff]', '', s)
    s = re.sub(r'(?<!\\)%', r'\\%', s)
    s = s.replace('\\neqslant', '\\neq')
    s = s.replace('\\dotimes', '\\dots')
    s = re.sub(r'(?:\\dots\s*){2,}', r'\\dots ', s)
    for i, ch in enumerate('①②③④⑤⑥⑦⑧⑨⑩', 1):
        s = s.replace(ch, f'\\cir{{{i}}}')
    for ch, repl in [('△', '\\triangle'), ('▲', '\\blacktriangle'), ('★', '\\bigstar'),
                     ('Ⅰ', '\\mathrm{I}'), ('Ⅱ', '\\mathrm{II}'), ('π', '\\pi'),
                     ('∞', '\\infty'), ('≤', '\\le'), ('≥', '\\ge'), ('≠', '\\ne'),
                     ('∈', '\\in'), ('⊥', '\\perp'), ('∥', '\\parallel'), ('±', '\\pm'),
                      ('×', '\\times'), ('÷', '\\div'), ('°', '^{\\circ}'), ('√', '\\sqrt{\\ }'),
                     ('∴', '\\therefore'), ('∵', '\\because')]:
        s = s.replace(ch, repl)
    s = re.sub(r'\\sqrt\{\\ \}(\d)', r'\\sqrt{\1}', s)
    s = re.sub(r'\\cir\s*\{\s*\\(?:scriptsize|small|footnotesize|tiny)\s*', r'\\cir{', s)
    s = re.sub(r'\\cir\s*\{\s*\\cir\s*\{\s*(\d+)\s*\}\s*\}', r'\\cir{\1}', s)
    s = re.sub(r'\$?\\textcircled\s*\$', r'\\cir', s)
    s = s.replace('\\textcircled', '\\cir')
    s = re.sub(r'</?(?:table|thead|tbody|tr|td|th)[^>]*>', ' ', s)
    s = _fix_stray_braces(s)
    return s.strip()


def _html_table_to_latex(s):
    """Convert a single-line MinerU `<table>` to a LaTeX tabular block."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S)
    if not rows:
        return None
    grid = []
    maxc = 0
    for r in rows:
        cells = [c.strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)]
        cells = [_escape_cell(c) for c in cells]
        grid.append(cells)
        maxc = max(maxc, len(cells))
    if maxc == 0:
        return None
    for r in grid:
        while len(r) < maxc:
            r.append('')
    out = ['\\begin{center}', '\\begin{tabular}{|' + 'c|' * maxc + '}', '\\hline']
    for r in grid:
        out.append(' & '.join(r) + ' \\\\ \\hline')
    out.append('\\end{tabular}')
    out.append('\\end{center}')
    return '\n'.join(out)


def _escape_cell(c):
    """Escape LaTeX-special chars in a table cell (cell may keep $...$ math)."""
    c = c.replace('&amp;', r'\&')
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    c = re.sub(r'(?<!\\)&', r'\\&', c)
    c = re.sub(r'(?<!\\)#', r'\\#', c)
    return c


def _fix_textmode(s):
    """Post-fixes that must only fire in TEXT mode (outside $...$ spans).

    Flat regexes here previously corrupted legit math like \\right)^{n} or
    \\right)\\cup inside $...$; this walker tracks $-pairing so the fixes
    only apply outside math:
      - \\right)/\\right] whose closing $ was lost (followed by a
        non-terminator char) -> append $
      - bare function names 'sin x' -> $sin x$
      - bare Delta/triangle -> $...$
    """
    out = []
    i = 0
    n = len(s)
    in_math = False
    cont_open = False  # in_math region opened by the bare-\left continuation fix
    depth = 0
    ens_depths = []  # brace depths at which each open \ensuremath closes
    while i < n:
        ch = s[i]
        if ch == '$':
            in_math = not in_math
            cont_open = False
            out.append(ch)
            i += 1
            continue
        if in_math and cont_open and _CJKSTOP.match(ch):
            # formula continuation ran into prose: close the span we opened
            out.append('$')
            in_math = False
            cont_open = False
        if ch == '\\':
            # Track \ensuremath{...} groups: their content is already math
            # mode -- wrapping \sqrt/\therefore inside them would produce
            # the broken \ensuremath{$\sqrt{\ }$} form.
            m = _ENSUREMATH_OPEN.match(s, i)
            if m:
                ens_depths.append(depth)
                depth += 1
                out.append(m.group(0))
                i = m.end()
                continue
            if (in_math or ens_depths) and s[i:i + 2] == '\\*':
                # \* (text discretionary) is invalid in math mode: unescape
                out.append('*')
                i += 2
                continue
            if not in_math and not ens_depths:
                # Bare \left...\right<delim> in text (lost opening $): wrap the
                # whole balanced group in $...$
                m = _LEFT_RE.match(s, i)
                if m:
                    end = _match_left_group(s, m.end())
                    if end > 0:
                        k = end
                        while k < n and s[k] in ' \t':
                            k += 1
                        nxt = s[k] if k < n else ''
                        if nxt and (nxt in '^_=+-0123456789(' or nxt == '\\'):
                            # formula continues past the group: leave the span open
                            out.append('$' + s[i:end])
                            in_math = True
                            cont_open = True
                        else:
                            out.append('$' + s[i:end] + '$')
                        i = end
                        continue
                # Bare math commands in TEXT mode (fill-answer lists etc.):
                # \frac{A}{B} / \sqrt{A} / \therefore / \because -> $...$
                m = _FRAC_RE.match(s, i)
                if m:
                    a, j = _read_group(s, m.end() - 1)
                    if a is not None:
                        k = j
                        while k < n and s[k] in ' \t':
                            k += 1
                        if k < n and s[k] == '{':
                            b, k2 = _read_group(s, k)
                            if b is not None:
                                out.append('$' + s[i:k2] + '$')
                                i = k2
                                continue
                m = _SQRT_RE.match(s, i)
                if m:
                    a, j = _read_group(s, m.end() - 1)
                    if a is not None:
                        out.append('$' + s[i:j] + '$')
                        i = j
                        continue
                m = _THUS_RE.match(s, i)
                if m:
                    out.append('$' + m.group(0) + '$')
                    i = m.end()
                    continue
                m = _TRIANGLE_RE.match(s, i)
                if m:
                    out.append('$' + m.group(0) + '$')
                    i = m.end()
                    continue
                m = _RIGHT_RE.match(s, i)
                if m:
                    j = m.end()
                    nxt = s[j] if j < n else ''
                    if nxt and nxt not in ').,; \t':
                        out.append(m.group(0) + '$')
                        in_math = True
                    else:
                        out.append(m.group(0))
                    i = j
                    continue
            out.append(s[i:i + 2])
            i += 2
            continue
        if ch == '{':
            depth += 1
            out.append(ch)
            i += 1
            continue
        if ch == '}':
            if ens_depths and ens_depths[-1] == depth - 1:
                ens_depths.pop()
            if depth > 0:
                depth -= 1
            out.append(ch)
            i += 1
            continue
        if not in_math and not ens_depths:
            # Text-mode & (alignment tab in LaTeX) -> \&
            if ch == '&':
                out.append('\\&')
                i += 1
                continue
            m = _FUNC_RE.match(s, i)
            if m:
                out.append('$' + m.group(0) + '$')
                i = m.end()
                continue
            m = _DELTA_RE.match(s, i)
            if m and (i == 0 or not (s[i - 1].isalpha() or s[i - 1] == '\\')):
                out.append('$' + m.group(1) + '$')
                i = m.end()
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


_ENSUREMATH_OPEN = re.compile(r'\\ensuremath\s*\{')
_MATHCMD = re.compile(r'\\(mathbf|mathrm|mathbb|mathcal|mathfrak)\s*\{([^{}]*)\}')


def wrap_text_cmds(s):
    r"""Wrap \mathbf{...} etc. in $...$ only when they appear in text mode.

    Uses a brace-depth stack to skip anything inside an open \ensuremath{...}:
    that content is ALREADY math mode, and double-wrapping produced the broken
    `\ensuremath{$\mathrm{II}$}` (which killed xelatex with `\@ensuredmath` EOF
    errors). \text{...} content stays wrappable (text mode inside), and nested
    or sequential \mathrm inside one \ensuremath are all skipped correctly.
    """
    result = []
    i = 0
    n = len(s)
    in_math = False
    depth = 0
    ens_depths = []  # brace depths at which each open \ensuremath closes
    while i < n:
        ch = s[i]
        if ch == '$':
            j = s.find('$', i + 1)
            if j == -1:
                result.append(s[i:])
                break
            result.append(s[i:j + 1])
            in_math = not in_math
            i = j + 1
            continue
        if ch == '\\':
            m = _ENSUREMATH_OPEN.match(s, i)
            if m:
                ens_depths.append(depth)
                depth += 1
                result.append(m.group(0))
                i = m.end()
                continue
            if not in_math:
                m = _MATHCMD.match(s, i)
                if m and not ens_depths:
                    result.append(f'${m.group(0).replace(" ", "")}$')
                    i = m.end()
                    continue
            result.append(s[i:i + 2])
            i += 2
            continue
        if ch == '{':
            depth += 1
            result.append(ch)
            i += 1
            continue
        if ch == '}':
            if ens_depths and ens_depths[-1] == depth - 1:
                ens_depths.pop()
            if depth > 0:
                depth -= 1
            result.append(ch)
            i += 1
            continue
        result.append(ch)
        i += 1
    return ''.join(result)


def fix_dollar_signs(text):
    """Fix unbalanced $ signs in MinerU output."""
    # Normalize \( ... \) delimiters first so $-pair counting is meaningful
    text = text.replace('\\(', '$').replace('\\)', '$')
    # Common fix: $\mathrm{A}.text$ -> A. $text$  (option letter wrongly inside
    # the math span; move the letter out and RE-OPEN the span so $-pairs stay
    # balanced -- the old prefix-only rule stripped the opener and left the
    # closer, producing `A.x \in A$` fragments)
    text = re.sub(r'\$\\mathrm\{([A-D])\}\.([^$]*?)\$',
                  lambda m: f'{m.group(1)}. ${m.group(2)}$' if m.group(2) else f'{m.group(1)}.',
                  text)
    # Fallback when there is no closing $ on the line
    text = re.sub(r'\$\\mathrm\{([A-D])\}\.', r'\1.', text)

    dollar_count = text.count('$')
    if dollar_count % 2 == 1:
        # Odd inline $ count: delete the LAST $ (MinerU usually leaves a
        # stray trailing marker; only line-start/end were handled before)
        i = text.rfind('$')
        if i != -1:
            text = text[:i] + text[i + 1:]

    return text


def convert(md_path, tex_path, img_base):
    md = Path(md_path).read_text(encoding='utf-8')
    lines = md.split('\n')

    title = ''
    sections = []
    current_section = None
    current_question = None
    current_sub = None
    pending_images = []
    in_display = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Embedded answer section inside an exam MD -> stop parsing the rest
        if (re.match(r'^#{1,3}\s', stripped) and
                re.search(r'参考答案|答案与解析|试题答案', stripped)):
            break
        if re.match(r'^[（(]?参考答案[）)]?$', stripped):
            break

        # Title
        if stripped.startswith('#') and not title:
            t = stripped.lstrip('#').strip()
            if '一、' not in t and '二、' not in t and '一．' not in t and '二．' not in t and '注意事项' not in t:
                title = re.sub(r'\s*命题.*$', '', t)
                continue

        # Section headers
        section_match = re.match(r'#{0,3}\s*([一二三四五][、．.]\s*.+)', stripped)
        if not section_match and re.match(r'[一二三四][、．.]', stripped[:10]):
            section_match = re.match(r'([一二三四五][、．.]\s*.+)', stripped)
        if section_match:
            st = section_match.group(1).strip()
            if '一、' in st or '一．' in st or '单选' in st:
                current_section = ('single', st)
            elif '二、' in st or '二．' in st or '多选' in st:
                current_section = ('multi', st)
            elif '三、' in st or '三．' in st or '填空' in st:
                current_section = ('fill', st)
            elif '四、' in st or '四．' in st or '解答' in st:
                current_section = ('solve', st)
            else:
                current_section = ('other', st)
            sections.append([current_section[0], current_section[1], []])
            current_question = None
            current_sub = None
            continue

        # Display math blocks: $$ ... $$ (content becomes \[...\] blocks,
        # NOT glued into the inline question text)
        if stripped == '$$':
            in_display = not in_display
            continue
        if in_display:
            if current_question:
                tgt = current_sub if current_sub else current_question
                tgt['display'].append(stripped)
            continue

        img_match = re.match(r'!\[\]\((?:images/)?([^\)]+\.(?:jpg|png|jpeg))\)', stripped, re.IGNORECASE)
        if img_match:
            if current_question:
                # Image after a question belongs to THAT question (PDF order)
                current_question['images'].append(img_match.group(1))
            else:
                pending_images.append(img_match.group(1))
            continue

        # Figure captions like 第11题图 -> drop (pure caption, no content)
        if re.match(r'^[（(]?第\s*\d+\s*题图[）)]?$', stripped):
            continue

        # MinerU HTML tables -> LaTeX tabular attached to the (sub)question
        if '<table' in stripped:
            tab = _html_table_to_latex(stripped)
            if tab and current_question:
                tgt = current_sub if current_sub else current_question
                tgt['tables'].append(tab)
            continue

        # Question numbers (possibly with ## prefix)
        q_match = re.match(r'(?:#{1,3}\s*)?(\d+)[．.、]\s*', stripped)
        if q_match and current_section:
            q_num = int(q_match.group(1))
            q_text = stripped[q_match.end():].strip()
            q_images = pending_images[:]
            pending_images = []
            current_question = {'num': q_num, 'text': q_text, 'images': q_images,
                                'tables': [], 'display': [], 'sub': []}
            current_sub = None
            if sections:
                sections[-1][2].append(current_question)
            continue

        sub_match = re.match(r'[（(](\d+)[)）]\s*', stripped)
        if sub_match and current_question:
            current_sub = {'text': stripped[sub_match.end():].strip(),
                           'tables': [], 'display': []}
            current_question['sub'].append(current_sub)
            continue

        if current_question:
            current_question['text'] += ' ' + stripped

    # Post-process: fix unbalanced $ in question text
    for sec_type, sec_title, questions in sections:
        for q in questions:
            q['text'] = fix_dollar_signs(q['text'])
            q['display'] = [fix_dollar_signs(d) for d in q['display']]
            for sub in q['sub']:
                sub['text'] = fix_dollar_signs(sub['text'])
                sub['display'] = [fix_dollar_signs(d) for d in sub['display']]

    # Generate LaTeX
    latex = TEX_HEADER
    latex += f'\\graphicspath{{{{{img_base}/}}}}\n\n'
    latex += '\\begin{document}\n\n'

    if title:
        latex += '\\begin{center}\n'
        latex += f'    \\LARGE{{\\textbf{{{title}}}}}\n'
        latex += '\\end{center}\n\n\\vspace{0.5em}\n\n'

    latex += '\\noindent\\textbf{注意事项}：\n\n'
    latex += '1．答卷前，考生务必将自己的姓名、准考证号填写在答题卡上。\n\n'
    latex += '2．回答选择题时，选出每小题答案后，用铅笔把答题卡上对应题目的答案标号涂黑。\n'
    latex += '如需改动，用橡皮擦干净后，再选涂其它答案标号。回答非选择题时，将答案写在答题卡上，\n'
    latex += '写在本试卷上无效。\n\n'
    latex += '3．考试结束后，将本试卷和答题卡一并交回。\n\n\\vspace{1em}\n\n'

    def _emit_q_blocks(latex, q, indent):
        for d in q.get('display', []):
            latex += f'{indent}\\[{clean_display(d)}\\]\n'
        for tab in q.get('tables', []):
            for ln in tab.split('\n'):
                latex += f'{indent}{ln}\n'
            latex += '\n'
        for img in q.get('images', []):
            latex += f'{indent}\\begin{{center}}\n'
            latex += f'{indent}\\includegraphics[width=0.30\\textwidth]{{{img}}}\n'
            latex += f'{indent}\\end{{center}}\n\n'
        return latex

    single_count = 0
    multi_count = 0
    fill_count = 0

    for sec_type, sec_title, questions in sections:
        print(f"  Section {sec_type}: {len(questions)} questions")
        if sec_type == 'single':
            single_count = len(questions)
            latex += f'\\noindent{{\\textbf{{{sec_title}}}}}\n\n'
            latex += '\\begin{enumerate}[itemsep=0.3em]\n'
            for q in questions:
                text = clean(q['text'])
                latex += f'    \\item {text}\n'
                latex = _emit_q_blocks(latex, q, '    ')
            latex += '\\end{enumerate}\n\n'

        elif sec_type == 'multi':
            multi_count = len(questions)
            latex += f'\\noindent{{\\textbf{{{sec_title}}}}}\n\n'
            latex += f'\\begin{{enumerate}}[start={single_count+1}, itemsep=0.5em]\n'
            for q in questions:
                text = clean(q['text'])
                latex += f'    \\item {text}\n'
                latex = _emit_q_blocks(latex, q, '    ')
            latex += '\\end{enumerate}\n\n'

        elif sec_type == 'fill':
            fill_count = len(questions)
            latex += f'\\noindent{{\\textbf{{{sec_title}}}}}\n\n'
            latex += f'\\begin{{enumerate}}[start={single_count+multi_count+1}, itemsep=0.8em]\n'
            for q in questions:
                text = clean(q['text'])
                text = re.sub(r'_{3,}', '\\blank', text)
                latex += f'    \\item {text}\n'
                latex = _emit_q_blocks(latex, q, '    ')
            latex += '\\end{enumerate}\n\n'

        elif sec_type == 'solve':
            solve_start = single_count + multi_count + fill_count + 1
            latex += f'\\noindent{{\\textbf{{{sec_title}}}}}\n\n'
            latex += f'\\begin{{examenum}}[start={solve_start}, itemsep=2.5cm]\n'
            for q in questions:
                text = clean(q['text'])
                latex += f'    \\item {text}\n'
                for d in q.get('display', []):
                    latex += f'    \\[{clean_display(d)}\\]\n'
                if q['sub']:
                    latex += '    \\begin{examenum}\n'
                    for sub in q['sub']:
                        latex += f'        \\item {clean(sub["text"])}\n'
                        for d in sub.get('display', []):
                            latex += f'        \\[{clean_display(d)}\\]\n'
                        for tab in sub.get('tables', []):
                            for ln in tab.split('\n'):
                                latex += f'        {ln}\n'
                            latex += '\n'
                    latex += '    \\end{examenum}\n'
                for tab in q.get('tables', []):
                    for ln in tab.split('\n'):
                        latex += f'    {ln}\n'
                    latex += '\n'
                for img in q.get('images', []):
                    latex += '    \\begin{center}\n'
                    latex += f'    \\includegraphics[width=0.30\\textwidth]{{{img}}}\n'
                    latex += '    \\end{center}\n\n'
                latex += '\\vspace{0.5em}\n\n'
            latex += '\\end{examenum}\n\n'

    latex += '\\end{document}\n'
    Path(tex_path).write_text(latex, encoding='utf-8')
    return len(sections)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('md', help='Input markdown file')
    parser.add_argument('tex', help='Output tex file')
    parser.add_argument('--img-base', required=True, help='Image directory basename')
    args = parser.parse_args()
    convert(args.md, args.tex, args.img_base)
