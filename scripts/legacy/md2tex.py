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
    # Fix: \right) D $\cmd...  ->  \right)$ D \cmd...  (lost closer before the
    # option letter). Parity-neutral: the stray opener before \cmd is dropped;
    # the span engine below re-wraps the bare command in text mode.
    s = re.sub(r'(\\right[\)\]])(?!\s*\$)(\s+)([A-D][\.、．]?)(\s*)\$(?=\\)',
               lambda m: m.group(1) + '$' + m.group(2) + m.group(3) + m.group(4), s)
    # Fix \textcircled (invalid in math mode) -> \cir, also broken \textcircled$ forms
    # (consume an optional orphan $ before \textcircled: $\textcircled$ {2} -> \cir {2})
    s = re.sub(r'\$?\\textcircled\s*\$', r'\\cir', s)
    s = s.replace('\\textcircled', '\\cir')
    # Inline-math span engine: tokenize on unescaped '$', drop pseudo-span
    # delimiters (MinerU delimiter misuse), rebuild with balance as a
    # construction invariant. Replaces the legacy merge loop + textmode
    # walker + $$-collapse + odd-count guard stack: the count-based post
    # fixes corrupted balanced walker output (the guard deleted legitimate
    # closers whenever engine-emitted delimiters flipped the parity).
    s = _fix_inline_math(s)
    # \complement_U -> \complement_{U}; braced forms normalized; a dangling
    # underscore is dropped. (The old rule stripped '_' outright, turning
    # '\complement_U' into the undefined control sequence '\complementU'.)
    s = re.sub(r'\\complement\s*_([A-Za-z0-9])(?![A-Za-z0-9])', r'\\complement_{\1}', s)
    s = re.sub(r'\\complement\s*_\{', r'\\complement_{', s)
    s = re.sub(r'\\complement\s*_(?![A-Za-z0-9{])', r'\\complement', s)
    # Drop stray unmatched closing braces (e.g. MinerU `$\{a_n\}$}`)
    s = _fix_stray_braces(s)
    return s


_RIGHT_RE = re.compile(r'\\right([\)\]])')
_LEFT_RE = re.compile(r'\\left(?![a-zA-Z])')
# Prose boundary: CJK ideographs / fullwidth forms / ellipsis stop a
# formula-continuation scan (was the legacy walker's _CJKSTOP).
_PROSE_RE = re.compile(r'[一-鿿　-〿＀-￯…]')

# --- Inline-math span engine ---------------------------------------------
# clean() tokenizes on unescaped '$', drops pseudo-span delimiters (MinerU
# delimiter misuse: empty / pure-CJK / separator / punctuation spans), and
# rebuilds the string with '$'-balance as a construction invariant.  Internal
# PUA markers stand in for '$' until the final replace, so emitted delimiter
# pairs stay unambiguous and adjacent-pair hazards ($$) can be normalized
# before they ever reach TeX.  Replaces the legacy five-layer stack (merge
# loop -> wrap_text_cmds -> textmode walker -> $$-collapse -> odd guard):
# the count-based post fixes corrupted balanced walker output (the guard
# deleted legitimate closers whenever engine-emitted delimiters flipped
# the parity).
_OPEN = '\ue000'
_CLOSE = '\ue001'

# Math commands that may continue a $...$ span across a lost delimiter
# (legacy merge-loop pat_cmd / pat_sup semantics).
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
       r'propto|notin|land|lor|lnot|oplus|ominus|otimes|oint|bigsqcup|bigcap|bigcup|'
       r'alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|'
       r'lambda|mu|nu|xi|varpi|pi|rho|varrho|sigma|varsigma|tau|upsilon|phi|varphi|'
       r'chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|'
       r'ell|hbar|imath|jmath)')
_SPANCONT_RE = re.compile(r'(?:[\^_]|\\' + _MC + r'(?![a-zA-Z]))')

# Pseudo-span content (MinerU delimiter misuse, not real math): the
# delimiters are dropped and the content returns to the text stream.
_CJKSPAN_RE = re.compile(r'^[一-鿿　-〿＀-￯]+$')
_SEP_RE = re.compile(r'^\s*[,，;；、]\s*$')
_PUNCT_RE = re.compile(r'^[^\w\\{}]*$')

# Bare math symbols in TEXT mode -> wrap in $...$.  Regex backtracking plus
# the shared trailing (?![a-zA-Z]) makes alternation order irrelevant:
# \in cannot misfire on \int, \cdot on \cdots.
_TEXTSYM_RE = re.compile(r'\\(?:therefore|because|triangle|angle|perp|parallel|'
                         r'cong|sim|simeq|approx|equiv|propto|infty|emptyset|'
                         r'varnothing|times|div|cdot|pm|mp|cup|cap|setminus|'
                         r'subset|subseteq|supset|supseteq|in|notin|ni|le|leq|'
                         r'ge|geq|ne|neq|ll|gg|ast|star|oplus|ominus|otimes|'
                         r'oslash|land|lor|wedge|vee|lnot|neg|forall|exists|'
                         r'partial|nabla|prime|circ|bullet|dots|cdots|ldots|'
                         r'vdots|ddots|rightarrow|to|leftarrow|Rightarrow|'
                         r'Leftarrow|Leftrightarrow|leftrightarrow|mapsto|'
                         r'longrightarrow|longleftarrow|rightleftharpoons|'
                         r'uparrow|downarrow|quad|qquad|'
                         r'sin|cos|tan|cot|sec|csc|arcsin|arccos|arctan|sinh|'
                         r'cosh|tanh|ln|log|lg|lim|max|min|exp|gcd|hom|ker|'
                         r'deg|dim|arg)(?![a-zA-Z])')

# Group-reading commands in TEXT mode: wrap \cmd{...}; without a group emit
# \cmd{\ } so the command still has a valid (empty) argument.
_ARGSYM_RE = re.compile(r'\\(?:overrightarrow|overleftarrow|vec|hat|check|tilde|'
                        r'bar|breve|acute|grave|dot|ddot|dddot|widehat|widetilde|'
                        r'overline|underline|overbrace|underbrace|mathbf|mathrm|'
                        r'mathbb|mathcal|mathfrak|mathit|mathsf|mathtt|bm)'
                        r'(?![a-zA-Z])')

# Text fragments that look like broken-off math: a bare unescaped _/^ with a
# valid argument is always a LaTeX error in text mode.  PULLIN moves such a
# fragment into the following span; SUBWRAP wraps the remaining ones.
_FRAG = r'[A-Za-z0-9_^{}()=+<>!|\\\- ]'
_SUBCORE = r'(?<!\\)[_^]\s*(?:\{[^{}]*\}|[A-Za-z0-9])'
_PULLIN_RE = re.compile(r'(' + _FRAG + '*' + _SUBCORE + _FRAG + r'*)\ue000')
_SUBWRAP_RE = re.compile(r'(' + _FRAG + '*' + _SUBCORE + _FRAG + r'*)')


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
    c = c.replace('&gt;', '>')
    c = c.replace('&lt;', '<')
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    c = re.sub(r'(?<!\\)&', r'\\&', c)
    c = re.sub(r'(?<!\\)#', r'\\#', c)
    return c


def _split_dollars(s):
    r"""Tokenize on unescaped '$'.  Escaped \$ pairs stay glued to text
    tokens (the legacy s.split('$') wrongly cut \$ in half).  Even indices
    are text, odd indices are the content of a $...$ span."""
    parts = []
    cur = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == '\\':
            cur.append(s[i:i + 2])
            i += 2
            continue
        if ch == '$':
            parts.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append(''.join(cur))
    return parts


def _unstar(tok):
    r"""Unescape \* (text discretionary, invalid in math mode) in a token
    that is emitted into math mode."""
    return re.sub(r'(?<!\\)\\\*', '*', tok)


def _is_pseudo_span(content):
    """MinerU delimiter misuse, not real math: empty / pure-CJK / pure
    separator / pure punctuation span content."""
    t = content.strip()
    if not t:
        return True
    if _CJKSPAN_RE.match(t) or _SEP_RE.match(content) or _PUNCT_RE.match(content):
        return True
    return False


def _emit_text(out, s):
    r"""Text-mode walker for one token (contains no unescaped '$').

    Text-mode-only structural fixes (legacy walker semantics):
      - bare \left...\right<delim> group in text -> wrap in $...$; when the
        formula continues (peek ^_=+-0123456789( or \) leave the span open
      - \right)/\right] whose closing $ was lost -> reopen ('scan')
      - bare \frac{A}{B} / \sqrt{A} / group-reading commands / math symbols
        in text mode -> wrap in $...$
      - bare function names 'sin x' / Delta / triangle words -> wrap
      - text-mode & -> \& ;  \* unescaped inside math / \ensuremath{...}

    Returns the mode at token end: 'text', or 'scan' when a
    formula-continuation region was left open.
    """
    i = 0
    n = len(s)
    cur = 'text'
    depth = 0
    ens_depths = []  # brace depths at which each open \ensuremath closes
    while i < n:
        ch = s[i]
        if cur == 'scan':
            # formula continuation: math until a prose boundary
            if _PROSE_RE.match(ch):
                out.append(_CLOSE)
                cur = 'text'
                continue
            if ch == '\\':
                if s[i:i + 2] == '\\*':
                    out.append('*')
                else:
                    out.append(s[i:i + 2])
                i += 2
                continue
            out.append(ch)
            i += 1
            continue
        # cur == 'text'
        if ch == '\\':
            # Track \ensuremath{...} groups: their content is already math
            # mode -- wrapping inside them would produce the broken
            # \ensuremath{$\sqrt{\ }$} form.
            m = _ENSUREMATH_OPEN.match(s, i)
            if m:
                ens_depths.append(depth)
                depth += 1
                out.append(m.group(0))
                i = m.end()
                continue
            if ens_depths:
                if s[i:i + 2] == '\\*':
                    out.append('*')
                else:
                    out.append(s[i:i + 2])
                i += 2
                continue
            # Bare math constructs in TEXT mode (outside \ensuremath)
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
                        out.append(_OPEN + s[i:end])
                        cur = 'scan'
                    else:
                        out.append(_OPEN + s[i:end] + _CLOSE)
                    i = end
                    continue
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
                            out.append(_OPEN + s[i:k2] + _CLOSE)
                            i = k2
                            continue
            m = _SQRT_RE.match(s, i)
            if m:
                a, j = _read_group(s, m.end() - 1)
                if a is not None:
                    out.append(_OPEN + s[i:j] + _CLOSE)
                    i = j
                    continue
            m = _ARGSYM_RE.match(s, i)
            if m:
                k = m.end()
                while k < n and s[k] in ' \t':
                    k += 1
                if k < n and s[k] == '{':
                    a, k2 = _read_group(s, k)
                    if a is not None:
                        out.append(_OPEN + s[i:k2] + _CLOSE)
                        i = k2
                        continue
                out.append(_OPEN + m.group(0) + '{\\ }' + _CLOSE)
                i = m.end()
                continue
            m = _TEXTSYM_RE.match(s, i)
            if m:
                out.append(_OPEN + m.group(0) + _CLOSE)
                i = m.end()
                continue
            m = _RIGHT_RE.match(s, i)
            if m:
                j = m.end()
                nxt = s[j] if j < n else ''
                if nxt and nxt not in ').,; \t' and not _PROSE_RE.match(nxt):
                    # lost closing $: reopen and scan the formula continuation
                    out.append(m.group(0) + _OPEN)
                    cur = 'scan'
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
        if not ens_depths:
            # Text-mode & (alignment tab in LaTeX) -> \&
            if ch == '&':
                out.append('\\&')
                i += 1
                continue
            m = _FUNC_RE.match(s, i)
            if m:
                out.append(_OPEN + m.group(0) + _CLOSE)
                i = m.end()
                continue
            m = _DELTA_RE.match(s, i)
            if m and (i == 0 or not (s[i - 1].isalpha() or s[i - 1] == '\\')):
                out.append(_OPEN + m.group(1) + _CLOSE)
                i = m.end()
                continue
        out.append(ch)
        i += 1
    return cur


def _emit_piece(out, tok, mode):
    """Emit one TEXT token under the current mode; returns the new mode."""
    if mode == 'span':
        if _SPANCONT_RE.match(tok):
            # whole-token continuation of the open span
            # (legacy merge-loop pat_cmd / pat_sup)
            out.append(_unstar(tok))
            return 'span'
        out.append(_CLOSE)
        mode = 'text'
    if mode == 'scan':
        # formula continuation opened by a text-mode fix: math until prose
        i = 0
        n = len(tok)
        while i < n:
            ch = tok[i]
            if _PROSE_RE.match(ch):
                out.append(_CLOSE)
                mode = 'text'
                break
            if ch == '\\':
                if tok[i:i + 2] == '\\*':
                    out.append('*')
                else:
                    out.append(tok[i:i + 2])
                i += 2
                continue
            out.append(ch)
            i += 1
        if mode == 'scan':
            return 'scan'
        tok = tok[i:]  # remainder processed as text
    return _emit_text(out, tok)


def _fix_inline_math(s):
    r"""Rebuild inline math with '$'-balance as a construction invariant."""
    # Display remnants inlined into the text: $$...$$ -> $...$
    s = re.sub(r'\$\$(.+?)\$\$', r'$\1$', s)
    parts = _split_dollars(s)
    if len(parts) % 2 == 0:
        # Odd '$' count in the raw input: drop a stray marker (user
        # heuristic; MinerU usually leaves a stray trailing marker).  Done
        # at tokenize time so engine-emitted delimiters can never flip the
        # parity.  Exception: when the final text fragment is a math
        # continuation (starts with ^/_/\cmd, legacy pat_cmd semantics),
        # the stray marker is the one BEFORE it -- merge the fragment into
        # the preceding span so the trailing prose returns to text
        # (deleting the last $ instead would glue formula + prose into one
        # absorbed token and pull CJK into math mode).
        if len(parts) >= 4 and _SPANCONT_RE.match(parts[-2]):
            parts = parts[:-3] + [parts[-3] + parts[-2]] + [parts[-1]]
        else:
            parts = parts[:-2] + [parts[-2] + parts[-1]]
    out = []
    mode = 'text'
    for idx, tok in enumerate(parts):
        if idx % 2 == 1:
            # span token
            if _is_pseudo_span(tok):
                if mode != 'text':
                    out.append(_CLOSE)
                    mode = 'text'
                mode = _emit_text(out, tok)
            else:
                if mode != 'text':
                    out.append(_CLOSE)
                out.append(_OPEN)
                out.append(_unstar(tok))
                mode = 'span'
        else:
            mode = _emit_piece(out, tok, mode)
    if mode != 'text':
        out.append(_CLOSE)
    t = ''.join(out)
    # PULLIN: a broken-off math fragment (bare unescaped _/^) right before a
    # span opener belongs inside that span.
    t = _PULLIN_RE.sub('\ue000\\1', t)
    # SUBWRAP: remaining bare _/^ fragments in TEXT regions get their own
    # span (bare _/^ in text mode is always a LaTeX error).
    segs = re.split('[\ue000\ue001]', t)
    fixed = []
    for k, seg in enumerate(segs):
        if k % 2 == 0:
            seg = _SUBWRAP_RE.sub(lambda m: _OPEN + m.group(1).strip() + _CLOSE, seg)
        if k > 0:
            fixed.append(_OPEN if k % 2 == 1 else _CLOSE)
        fixed.append(seg)
    t = ''.join(fixed)
    # Never emit TeX-ambiguous adjacent delimiters: drop empty fix-spans,
    # and keep at least one space between a closer and the next opener
    # (adjacent $$ flips TeX between display math and Bad math delimiter).
    t = re.sub(r'\ue000[ \t]*\ue001', '', t)
    t = re.sub(r'\ue001[ \t]*\ue000', '\ue001 \ue000', t)
    return t.replace(_OPEN, '$').replace(_CLOSE, '$')


def _fix_textmode(s):
    """Legacy alias: text-mode fixes are now part of the inline-math span
    engine (_fix_inline_math); kept because regression suites import this
    name.  Behaviour is a superset of the old walker (text & -> \\& etc.)."""
    return _fix_inline_math(s)


_ENSUREMATH_OPEN = re.compile(r'\\ensuremath\s*\{')
_MATHCMD = re.compile(r'\\(mathbf|mathrm|mathbb|mathcal|mathfrak)\s*\{([^{}]*)\}')


def wrap_text_cmds(s):
    r"""Wrap \mathbf{...} etc. in $...$ only when they appear in text mode.

    Uses a brace-depth stack to skip anything inside an open \ensuremath{...}:
    that content is ALREADY math mode, and double-wrapping produced the broken
    `\ensuremath{$\mathrm{II}$}` (which killed xelatex with `\@ensuredmath` EOF
    errors). \text{...} content stays wrappable (text mode inside), and nested
    or sequential \mathrm inside one \ensuremath are all skipped correctly.

    Legacy: no longer called by clean() -- the span engine's _ARGSYM_RE wraps
    \mathbf{...}-style commands in text mode now.  Kept because regression
    suites and debug scripts import it.
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
