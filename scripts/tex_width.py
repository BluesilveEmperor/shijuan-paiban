#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tex_width.py — LaTeX 内容宽度估算（TASKS-COL-001 的量化依据）

用途
----
判断一个选项（题干 + 公式）放进 ``tasks(N)`` 的第 N 列会不会溢出版心。

为什么不能用「字符个数」
------------------------
旧实现把 ``$...$`` 里的公式按「字符数 / 2」折算成宽度，这对
``$\\{0\\}$``、``$\\sqrt{3}$`` 这类短公式够用，但对**不可断行的长分式**
会严重低估：

    $\\dfrac{\\tanh x+\\tanh y}{1+\\tanh x\\tanh y}$   实测 86.53pt（newtxmath 12pt）

字符折算只给出约 15 个单位（≈90pt 的一半），而 tasks(2) 每列实际只有
**200.4pt**，实测该选项整体 286.3pt → 溢出 51.46pt。

核心模型
--------
1. **宽度按不可断行片段求和**：文字可换行，但公式块（分式、根式、上下标
   组合）不可断行，分式宽度是 ``max(分子, 分母) + padding``，不是两者之和。
2. 整行宽度 = 所有片段宽度之和（近似，忽略断行带来的松弛）。
3. 字号线性缩放：所有标定值是 12pt，其他字号乘 ``pt/12``。

标定数据（XeLaTeX + ctexart + newtxmath + amsmath，12pt）
--------------------------------------------------------
    中文字符            12.00 pt/字
    拉丁正文            ≈ 4.83 pt/字符
    数学斜体 x           5.91 pt
    数学数字 1           5.87 pt
    \\sqrt{x+1}         33.19 pt
    |z|                12.04 pt
    (x+y)              34.81 pt
    \\dfrac{a_{n+1}}{n}  24.18 pt
    \\dfrac{\\tanh x+\\tanh y}{1+\\tanh x\\tanh y}   86.53 pt
    （　　）全角括号      41.20 pt

版心预算（A4，margin=2.5cm，tasks label-width 1.8em / item-indent 2.4em /
column-sep 2em）
------------------------------------------------------------------------
    版心宽            453.54 pt
    tasks(4) 每列        88.2 pt
    tasks(2) 每列       200.4 pt
    tasks(1) 每列       424.7 pt
"""

from __future__ import annotations

import re

# ── 标定常量（12pt 基准）──────────────────────────────────────────────────
PT_PER_CJK = 12.0          # 一个汉字
PT_PER_LATIN = 4.83        # 一个拉丁正文字符
PT_PER_MATH_CHAR = 5.9     # 一个数学斜体/数字字符
PT_MATH_OP = 3.0           # 一元运算符（-）的额外开销
PT_FRAC_PAD = 2.4          # 分式线上下 padding（实测 fracfull - max(分子,分母)）
PT_SQRT_HEAD = 13.0        # 根号头部宽度
PT_PAREN = 4.0             # 一对半角括号
PT_ABS = 3.36             # 竖线（实测 $|z|$ = 12.04 = 2*3.36 + z 5.32）
PT_SUP = 2.5               # 上下标整体额外宽度
PT_CJK_PUNCT = 12.0        # 全角标点（，（）：等

# 二元运算符（自带两侧间距，实测 +/= 为 9.14pt）
BIN_OP_WIDTH = 9.14
# 一元/标点类（实测 - 为 3.91pt、, 为 3.26pt、\cdot 为 3.24pt）
UN_OP_WIDTH = 3.9
PUNCT_WIDTH = 3.3
# 算符名后的隐式间距（实测 \tanh x - \tanh = 7.91pt，其中 x 本身 5.9pt → 间距约 2pt）
PT_OP_SPACE = 2.0
# 上下标内容的缩放（script style ≈ 0.7 倍正文）
SCRIPT_SCALE = 0.70
# 全角括号实测（　）= 29.20pt，空格 12.00pt → 每个括号 8.60pt
PT_CJK_BRACKET = 8.60

# 常用算符名的**固定**渲染宽度（newtxmath 12pt 实测）。
# 关键：算符名不是「按字符数估」——\tanh(4字母) 23.56pt，\sin(3字母) 14.48pt，
# 单字符比例完全不同。按名字查表最准，未知算符名退化为逐字母估。
OP_WIDTH = {
    "sin": 14.48, "cos": 14.26, "tan": 14.30, "cot": 14.30,
    "sec": 13.40, "csc": 14.60, "arcsin": 31.0, "arccos": 31.0,
    "arctan": 31.0, "sinh": 21.01, "cosh": 22.32, "tanh": 23.56,
    "ln": 9.85, "lg": 9.85, "log": 15.0, "exp": 17.0,
    "min": 17.0, "max": 17.0, "lim": 14.0, "sup": 17.0, "inf": 13.0,
    "det": 15.0, "dim": 15.0, "gcd": 19.0, "deg": 15.0,
    "sin": 14.48, "arg": 15.0, "ker": 16.0,
}
# \mathrm{i} 这类「装饰型」命令：内容按普通字符宽算，无额外开销
_DECOR_CMDS = {"mathrm", "mathbf", "mathbb", "mathcal", "mathfrak", "boldsymbol",
               "mathsf", "mathtt", "textit", "textbf", "operatorname", "text"}

BASE_FONT_PT = 12.0

# 版心几何（A4 + margin 2.5cm + tasks 参数，见 md2exam preamble）
TEXT_WIDTH_PT = 453.54
TASKS_INDENT_PT = 2.4 * 12.0   # item-indent 2.4em
TASKS_COLSEP_PT = 2.0 * 12.0   # column-sep 2em

# 超过此宽度即认为会溢出（留 4pt 安全余量）
SAFETY_PT = 4.0

# 模型全局安全系数。标定后整体误差约 -5%~-13%（模型偏保守，低估实际宽度），
# 取 1.15 保证估算值不小于实际值，宁可少用一列也不允许溢出。
WIDTH_SAFETY = 1.15


def column_budget_pt(cols: int, text_width_pt: float = TEXT_WIDTH_PT) -> float:
    """返回 tasks(cols) 中单列的可用宽度（pt）。"""
    if cols <= 0:
        return text_width_pt
    avail = text_width_pt - TASKS_INDENT_PT - (cols - 1) * TASKS_COLSEP_PT
    return avail / cols


# ── 公式片段解析 ─────────────────────────────────────────────────────────
_RE_FRAC = re.compile(r"\\[dt]?frac\s*\{")
_RE_SQRT = re.compile(r"\\sqrt\s*(\[[^\]]*\])?\s*\{")
_RE_CMD_ARG = re.compile(r"\\[A-Za-z]+\*?\s*\{([^{}]*)\}")
_RE_MATHOP = re.compile(r"[+\-=<>≤≥≠×÷·±]")


def _match_brace(s: str, start: int) -> tuple[str, int]:
    """从 s[start] 处的 '{' 开始，返回其配对内容与结束后的下标。

    start 必须指向 '{'。找不到配对时返回剩余全部内容。
    """
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
        i += 1
    return s[start + 1:], len(s)


def math_width_pt(s: str, font_pt: float = BASE_FONT_PT) -> float:
    """估算一段**数学模式**内容（不含 $ 定界符）的渲染宽度（pt）。

    按不可断行片段求和：分式取 max(分子,分母)，根式取 头部+内容。
    """
    scale = font_pt / BASE_FONT_PT
    total = 0.0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            m = _RE_FRAC.match(s, i)
            if m:
                # \dfrac{分子}{分母}
                brace = s.index("{", i)
                num, j = _match_brace(s, brace)
                if j < n and s[j] == "{":
                    den, k = _match_brace(s, j)
                else:
                    den, k = "", j
                total += max(math_width_pt(num, font_pt),
                             math_width_pt(den, font_pt)) + PT_FRAC_PAD
                i = k
                continue
            m = _RE_SQRT.match(s, i)
            if m:
                brace = s.index("{", i)
                inner, j = _match_brace(s, brace)
                total += PT_SQRT_HEAD + math_width_pt(inner, font_pt)
                i = j
                continue
            m = _RE_CMD_ARG.match(s, i)
            if m:
                name = s[i + 1:s.index("{", i)]
                if name in _DECOR_CMDS:
                    total += math_width_pt(m.group(1), font_pt)
                else:
                    total += OP_WIDTH.get(name, len(name) * PT_PER_LATIN)
                    total += math_width_pt(m.group(1), font_pt)
                i = m.end()
                continue
            # 其余命令（\sin \cos \tanh \mathrm \left 等）：按标识符长度估
            j = i + 1
            while j < n and s[j].isalpha():
                j += 1
            name = s[i + 1:j]
            if name:
                # \left \right \big 等定界命令本身不产生宽度
                if name in ("left", "right", "big", "Big", "bigg", "Bigg",
                            "bigl", "bigr", "Bigl", "Bigr", "displaystyle",
                            "textstyle", "scriptstyle", "limits", "nolimits"):
                    i = j
                    continue
                # 常见算符名有固定宽度（\tanh = 23.56pt），其余按标识符估
                total += OP_WIDTH.get(name, len(name) * PT_PER_LATIN)
                # 算符后有隐式间距（实测 \tanh x 比 \tanh 单独宽 7.9pt，
                # 其中 \tanh 后的间距约 2pt，x 前约 5.9pt）
                if i < n and s[i] == " ":
                    total += PT_OP_SPACE
                i = j
                continue
            i += 2
            continue
        if c == "{":
            inner, j = _match_brace(s, i)
            total += math_width_pt(inner, font_pt)
            i = j
            continue
        if c == "}":
            i += 1
            continue
        if c == "^" or c == "_":
            total += PT_SUP
            i += 1
            # 跳过紧跟的单个 token；上下标内容按 script 缩放渲染
            # （实测 a_{n+1} = 21.06pt，其中 a 5.9 + "n+1" 按 0.7 缩放 ≈ 14.7）
            if i < n and s[i] == "{":
                inner, j = _match_brace(s, i)
                total += math_width_pt(inner, font_pt) * SCRIPT_SCALE
                i = j
            else:
                total += PT_PER_MATH_CHAR * SCRIPT_SCALE
                i += 1
            continue
        if c in "+=<>≤≥≠×÷":
            total += BIN_OP_WIDTH
            i += 1
            continue
        if c == "-":
            total += UN_OP_WIDTH
            i += 1
            continue
        if c in ",;:":
            total += PUNCT_WIDTH
            i += 1
            continue
        if c == "·":
            total += PUNCT_WIDTH
            i += 1
            continue
        if c == "(" or c == ")":
            total += PT_PAREN
            i += 1
            continue
        if c == "[" or c == "]":
            total += PT_PAREN
            i += 1
            continue
        if c == "|":
            total += PT_ABS
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        total += PT_PER_MATH_CHAR
        i += 1
    return total * scale


_RE_INLINE_MATH = re.compile(r"\$([^$]*)\$", re.S)


def text_width_pt(s: str, font_pt: float = BASE_FONT_PT) -> float:
    """估算一段**混排文本**（含 $...$ 行内公式）的渲染宽度（pt）。"""
    scale = font_pt / BASE_FONT_PT
    total = 0.0
    pos = 0
    for m in _RE_INLINE_MATH.finditer(s):
        total += _plain_width_pt(s[pos:m.start()], font_pt)
        total += math_width_pt(m.group(1), font_pt)
        pos = m.end()
    total += _plain_width_pt(s[pos:], font_pt)
    return total * scale


def _plain_width_pt(s: str, font_pt: float = BASE_FONT_PT) -> float:
    """估算纯文本（无公式）宽度。"""
    scale = font_pt / BASE_FONT_PT
    total = 0.0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
            name = s[i + 1:j]
            if name:
                if j < len(s) and s[j] == "{":
                    inner, k = _match_brace(s, j)
                    total += text_width_pt(inner, font_pt)
                    i = k
                    continue
                total += len(name) * PT_PER_LATIN
                i = j
                continue
            i += 2
            continue
        if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f" or "\uff00" <= c <= "\uffef":
            if c in "（）【】":
                total += PT_CJK_BRACKET
            elif c in "，。：；":
                total += PT_CJK_PUNCT
            elif c == "\u3000":
                total += PT_PER_CJK      # 全角空格
            else:
                total += PT_PER_CJK
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        total += PT_PER_LATIN
        i += 1
    return total * scale


def option_width_pt(option: str, font_pt: float = BASE_FONT_PT) -> float:
    """估算一个选项（含公式）的渲染宽度（pt）。

    含全局安全系数 WIDTH_SAFETY：估算偏保守（宁可略大于实际），
    保证「放得下」的判断可靠。
    """
    return text_width_pt(option, font_pt) * WIDTH_SAFETY


def fits_columns(options, cols: int, font_pt: float = BASE_FONT_PT,
                 text_width_pt_: float = TEXT_WIDTH_PT) -> bool:
    """所有选项能否放进 tasks(cols) 的单列宽度内。"""
    budget = column_budget_pt(cols, text_width_pt_) - SAFETY_PT
    return all(option_width_pt(o, font_pt) <= budget for o in options)


def choose_tasks_cols(options, font_pt: float = BASE_FONT_PT,
                      text_width_pt_: float = TEXT_WIDTH_PT,
                      want_cols: int | None = None,
                      has_image: bool | None = None) -> int:
    """TASKS-COL-001 的量化实现。

    与 layout.yaml 的规则对应：
      * 含图片且平均长度 < 80 字符 → 4 列；≥ 80 → 2 列
      * 可见长度 > 25 字符 → 2 列；否则 4 列

    但**最终以「实测宽度是否放得下」为准**：只要某列放不下，
    就退到能放下的列数（最多退到 1 列）。

    参数
    ----
    want_cols
        调用方已按 layout.yaml 口径算出的意图列数。传入则直接用作起点；
        为 None 时由本函数按 layout.yaml 口径自行推算。
    has_image
        选项是否含图片。IR 路线里图片在独立的 ``image`` 字段而非文本中，
        调用方需显式告知；为 None 时按文本里是否出现 \\includegraphics 推断。

    退列下限
    --------
    图片选项的下限是 2 列——TASKS-COL-002 禁止图片选项用 tasks(1) 竖排。
    纯文字选项可以退到 1 列（TASKS-COL-003）。
    """
    if not options:
        return 4

    if has_image is None:
        has_image = any(r"\includegraphics" in o for o in options)

    if want_cols is None:
        if has_image:
            avg = sum(len(o) for o in options) / float(len(options))
            want = 4 if avg < 80 else 2
        else:
            want = 4 if _visible_len_max(options) <= 25 else 2
    else:
        want = want_cols

    # 宽度兜底：在 [floor, want] 区间内选**能放下的最大列数**。
    # 注意不能只试 want/2/1 —— want=4 时 want 列放不下应退到 3 或 2，
    # 只按固定序列 (want, 2, 1) 试会漏掉中间档位。
    floor = 2 if has_image else 1
    for cols in range(want, floor - 1, -1):
        if fits_columns(options, cols, font_pt, text_width_pt_):
            return cols
    # 全部放不下 → 取下限（图片保持 2 列，纯文字 1 列）
    return floor


def _visible_len_max(options) -> float:
    """按 TASKS-COL-001「可见长度」判定用的估算值（字符数口径）。

    保留原口径用于**选择意图**（4 列还是 2 列好看），
    真正的**能否放下**由 fits_columns 用宽度判定。
    """
    vals = []
    for o in options:
        s = _RE_INLINE_MATH.sub("X", o)
        s = re.sub(r"\\[A-Za-z]+\*?", "", s)
        s = s.replace("{", "").replace("}", "").replace("\\", "")
        vals.append(len(s))
    return max(vals) if vals else 0.0
