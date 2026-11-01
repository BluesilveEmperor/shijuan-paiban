#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2ans.py — 答案 Markdown → 参考答案 LaTeX（XeLaTeX / ctexart）

用法：
    python md2ans.py <答案md> <输出tex> --img-base Images-<卷名>
        [--img-src <源图片目录[,目录2]>] [--exam-name <卷名>]

要点：
    * \\daan{}（红）/ \\jieti（【解析】）/ \\xijie（【详解】）/
      \\xiaoI,\\xiaoII,\\xiaoIII（小问详解）；
    * 选择题答案表用 tabular；填空题答案行；解答题逐题；
    * 合并 MinerU 误拆的短 $$...$$ 行内公式碎片回正文，长块转 \\[...\\]；
    * 彻底去水印；异常片段写 stderr 不崩溃。

依赖同目录 md2exam.py 的清洗 / 工具函数。
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2exam import (  # noqa: E402
    clean_math, clean_inline_math_line, strip_watermark_fragments,
    normalize_blanks, wrap_unicode_math, escape_text, is_watermark_line,
    strip_inline_watermark,
    collect_images, section_type, SEC_SINGLE, SEC_MULTI, SEC_FILL, SEC_SOLVE,
    RE_HEADING,
)

_WARN = {"n": 0}


def eprint(*a):
    print("[md2ans]", *a, file=sys.stderr)


def warn(msg):
    _WARN["n"] += 1
    eprint("WARN:", msg)


RE_ITEM_NUM = re.compile(r"^\s*(\d{1,2})\s*[.．、]\s*(.*)$")
RE_IMAGE = re.compile(r"^\s*!\[[^\]]*\]\(\s*([^)\s]+)\s*\)\s*$")
RE_TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
# 题型小节行：「一、选择题：…」，同时捕获编号标记（一、）与其余标题
RE_SEC_LINE = re.compile(r"^\s*#{0,6}\s*([一二三四五六七八九十]+\s*[、.．])\s*(.+)$")
RE_FILL_ANS = re.compile(r"(?:^|\s)(1[2-9])\s*[.．、]\s*")

PREAMBLE = r"""% ============================================
% 高考数学参考答案（由 md2ans.py 自动生成）
% 依据 templates/gaokao-answer-template.tex，XeLaTeX 编译
% ============================================
\documentclass[12pt,a4paper]{ctexart}

\usepackage[top=2cm,bottom=2cm,left=2.5cm,right=2.5cm]{geometry}
\usepackage{setspace}
\onehalfspacing

\usepackage{enumitem}
\usepackage{amsmath,amssymb}
\usepackage{bm}
\usepackage{graphicx}
\graphicspath{{__IMGBASE__/}}
\usepackage{xcolor}
\usepackage{array,booktabs,caption}

\usepackage{fancyhdr}
\usepackage{lastpage}
\setlength{\headheight}{13.6pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{\small __EXAMNAME__\,$\cdot$\,数学\quad 参考答案}
\fancyfoot[C]{数学试题第\thepage 页（共\pageref{LastPage}页）}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}

\usepackage[hidelinks]{hyperref}

\newcommand{\daan}[1]{{\color{red}\textbf{【答案】#1}}}
\newcommand{\jieti}{\par{\color{gray!60!black}\textbf{【解析】}}}
\newcommand{\xijie}{\par{\color{blue!60!black}\textbf{【详解】}}}
\newcommand{\xiaoI}{\par{\color{blue!60!black}\textbf{【小问 1 详解】}}}
\newcommand{\xiaoII}{\par{\color{blue!60!black}\textbf{【小问 2 详解】}}}
\newcommand{\xiaoIII}{\par{\color{blue!60!black}\textbf{【小问 3 详解】}}}
\newcommand{\eqimg}[2][0.5]{\includegraphics[width=#1\textwidth,keepaspectratio]{#2}}
\newcommand{\Parallel}{\raisebox{0.1ex}{\rotatebox[origin=c]{-20}{$\parallel$}}}
\newcommand{\mi}{\mathrm{i}}
\newcommand{\me}{\mathrm{e}}

\begin{document}
"""

# --------------------------------------------------------------------------- #
#  文本 / 公式处理
# --------------------------------------------------------------------------- #

# 仅识别全角小问标记 （1）/（2）/（3），避免误伤 f(1)、h'(1)、(0,3-a) 等半角括号
RE_SUBQ = re.compile(r"（\s*([123])\s*）")
_SUBQ_CMD = {"1": r"\xiaoI", "2": r"\xiaoII", "3": r"\xiaoIII"}


def replace_subquestions(t):
    """把行内小问标记 （1）/（2）/（3） 转成 \\xiaoI/II/III。"""
    return RE_SUBQ.sub(lambda m: _SUBQ_CMD[m.group(1)] + " ", t)


def render_text_line(t):
    """普通文本行 → LaTeX（去水印 + 清洗公式 + 小问标记 + 转义）。"""
    t = strip_watermark_fragments(t)
    t = clean_inline_math_line(t)
    t = normalize_blanks(t)
    t = wrap_unicode_math(t)
    t = replace_subquestions(t)
    return escape_text(t)


def render_formula(fx):
    """行间公式内容 → LaTeX 行。"""
    fx = normalize_blanks(clean_math(strip_watermark_fragments(fx)), in_math=True)
    return r"\[%s\]" % fx


# --------------------------------------------------------------------------- #
#  $$ 块折叠（合并 MinerU 误拆的行内公式碎片）
# --------------------------------------------------------------------------- #

def fold_dollars(lines):
    """把行列表折叠为 unit 列表：("text",原文) / ("math",公式)。

    多行形态（$$ 单独成行）与单行形态（$$x$$）统一标为 "math"，
    交由 fold_short_inlines 决定合并回正文还是保留为行间公式。
    """
    units = []
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "$$":
            buf = []
            i += 1
            while i < n and lines[i].strip() != "$$":
                buf.append(lines[i].strip())
                i += 1
            i += 1
            units.append(("math", " ".join(buf)))
            continue
        m = re.match(r"^\$\$(.+)\$\$$", s, flags=re.S)
        if m:
            units.append(("math", m.group(1)))
            i += 1
            continue
        units.append(("text", lines[i]))
        i += 1
    return units


def fold_short_inlines(units):
    """短数学碎片合并回紧邻的前一正文行；长块保留为行间公式。

    仅当上一 unit 恰为正文（text）时才合并，避免图片后的图内 OCR 碎片
    被错误拼接到更早的正文。
    """
    res = []
    for kind, val in units:
        if kind != "math":
            res.append([kind, val])
            continue
        inner = clean_math(val)
        short = (len(inner) <= 50 and "\\\\" not in inner
                 and "\\begin" not in inner and "&" not in inner)
        if short and res and res[-1][0] == "text":
            res[-1][1] = res[-1][1].rstrip() + " $" + inner + "$"
            continue
        res.append(["formula", inner])
    return [(k, v) for k, v in res]


def parse_html_table(text):
    """<table>...</table> → 二维列表。"""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in cells]
        if cells:
            rows.append(cells)
    return rows

# --------------------------------------------------------------------------- #
#  结构解析
# --------------------------------------------------------------------------- #

def is_section_line(text):
    """仅当整行形如「一、选择题：…」时才判为题型小节，返回 (type|None, 标题)。"""
    m = RE_SEC_LINE.match(text)
    if not m:
        return None, None
    title = (m.group(1) + m.group(2)).strip()
    return section_type(title), title


def count_questions(sec):
    """估算某小节题目数（用于推断解答题起始编号）。"""
    if sec.get("table"):
        for row in sec["table"]:
            if row and row[0].strip() in ("题号", "題號"):
                return len(row) - 1
        return max(len(r) for r in sec["table"]) - 1
    n = 0
    for blk in sec.get("ansline", []):
        n += len(RE_FILL_ANS.findall(blk))
    if n == 0:
        n = len([x for x in sec.get("items", []) if isinstance(x[0], int)])
    return n


def parse(lines):
    """行列表 → (h1_lines, sections)。

    section = {"type","title","table","items":[(num,units)],"pre_units","ansline"}
    """
    h1 = []
    sections = []
    cur = None
    cur_item = None

    def flush_item():
        nonlocal cur_item
        if cur is not None and cur_item is not None:
            cur["items"].append(cur_item)
        cur_item = None

    def ensure_solve_item():
        nonlocal cur_item
        if cur is None:
            return
        if cur_item is None:
            base = cur.get("_start", 1)
            flush_item()
            cur_item = [base + len(cur["items"]), []]

    def add_unit(u):
        nonlocal cur_item
        if cur is None:
            return
        if cur_item is None:
            if cur["type"] == SEC_SOLVE:
                ensure_solve_item()
            else:
                cur.setdefault("pre_units", []).append(u)
                return
        cur_item[1].append(u)

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        # HTML 答案表
        mt = RE_TABLE.search(raw)
        if mt:
            rows = parse_html_table(mt.group(0))
            if cur is not None and rows:
                cur["table"] = rows
            continue
        # 行间公式（已由 fold 还原为单行 $$...$$）
        mf = re.match(r"^\$\$(.*)\$\$$", s, flags=re.S)
        if mf and cur is not None:
            add_unit(("formula", mf.group(1)))
            continue
        mh = RE_HEADING.match(raw)
        body = mh.group(2).strip() if mh else s
        if mh and len(mh.group(1)) == 1 and cur is None:
            h1.append(body)
            continue
        st, title = is_section_line(body)
        if st:
            flush_item()
            if cur:
                sections.append(cur)
            cur = {"type": st, "title": title, "table": None, "items": []}
            if st == SEC_SOLVE:
                base = 1 + sum(count_questions(x) for x in sections
                               if x["type"] in (SEC_SINGLE, SEC_MULTI, SEC_FILL))
                cur["_start"] = base
            continue
        if cur is None:
            continue
        mg = RE_IMAGE.match(raw)
        if mg:
            add_unit(("image", os.path.basename(mg.group(1))))
            continue
        mi = RE_ITEM_NUM.match(body)
        if mi:
            # 填空答案行特判：同一行含多个题号
            if cur["type"] == SEC_FILL and len(RE_FILL_ANS.findall(body)) >= 2:
                cur.setdefault("ansline", []).append(body)
                cur_item = None
                continue
            flush_item()
            cur_item = [int(mi.group(1)), []]
            rest = mi.group(2).strip()
            if rest:
                cur_item[1].append(("text", rest))
            continue
        add_unit(("text", raw))
    flush_item()
    if cur:
        sections.append(cur)
    return h1, sections

# --------------------------------------------------------------------------- #
#  渲染
# --------------------------------------------------------------------------- #

def render_answer_table(rows):
    """选择题 / 多选答案表 → 竖线 tabular。"""
    if not rows:
        return []
    ncol = max(len(r) for r in rows)
    spec = "|c|" + "c" * (ncol - 1) + "|"
    out = [r"\begin{center}", r"\begin{tabular}{%s}" % spec, r"\hline"]
    for r in rows:
        r = list(r) + [""] * (ncol - len(r))
        out.append(" & ".join(r) + r" \\")
        out.append(r"\hline")
    out += [r"\end{tabular}", r"\end{center}"]
    return out


def render_fill_ansline(blk):
    """填空答案行「12. x 13. y 14. z」→ 单行答案。"""
    parts = re.split(r"(?:^|\s)(1[2-9])\s*[.．、]\s*", blk.strip())
    segs = []
    for k in range(1, len(parts) - 1, 2):
        num = parts[k]
        txt = clean_inline_math_line(parts[k + 1].strip())
        txt = wrap_unicode_math(normalize_blanks(txt))
        segs.append(r"\textbf{%s.}\ %s" % (num, escape_text(txt)))
    if not segs:
        return []
    return [r"\noindent " + r"\quad ".join(segs)]


def render_units(units, indent=""):
    """units：("text",s) / ("formula",s) / ("image",fn) → LaTeX 行。"""
    out = []
    for u in units:
        kind = u[0]
        if kind == "text":
            t = render_text_line(u[1])
            if t.strip():
                out.append(indent + t)
        elif kind == "formula":
            out.append(indent + render_formula(u[1]))
        elif kind == "image":
            out.append(indent + r"\begin{center}")
            out.append(indent + r"\includegraphics[width=0.35\textwidth]{%s}" % u[1])
            out.append(indent + r"\end{center}")
    return out


def render_section(sec):
    out = []
    head = sec["title"].split("：", 1)
    out.append(r"\section*{%s}" % escape_text(head[0].strip()))
    if len(head) > 1 and head[1].strip():
        out.append(escape_text(head[1].strip()))
    out.append("")
    if sec.get("table"):
        out += render_answer_table(sec["table"])
        out.append("")
    for blk in sec.get("ansline", []):
        out += render_fill_ansline(blk)
        out.append("")
    out += render_units(sec.get("pre_units", []))
    items = sec.get("items", [])
    if items:
        nums = [n for n, _ in items if isinstance(n, int)]
        start = nums[0] if nums else 1
        out.append(r"\begin{enumerate}[start=%d, itemsep=1em]" % start)
        for _num, units in items:
            out.append(r"    \item ")
            out.append("    " + r"\jieti")
            out += render_units(units, indent="    ")
        out.append(r"\end{enumerate}")
    return out


def build_tex(h1, sections, img_base, exam_name):
    tex = [PREAMBLE.replace("__IMGBASE__", img_base).replace("__EXAMNAME__", exam_name)]
    tex.append(r"\begin{center}")
    if h1:
        tex.append(r"    {\LARGE\textbf{%s}}\\[0.5em]" % escape_text(h1[0]))
        for extra in h1[1:]:
            tex.append(r"    {\large\textbf{%s}}\\[0.3em]" % escape_text(extra))
    tex.append(r"    \vspace{0.3em}")
    tex.append(r"    \hrule")
    tex.append(r"\end{center}")
    tex.append("")
    for sec in sections:
        tex += render_section(sec)
        tex.append("")
    tex.append(r"\end{document}")
    tex.append("")
    return "\n".join(tex)


# --------------------------------------------------------------------------- #
#  无题型小节时的回退合成（如 2605/2610：答案表 + 12~19 逐题，无「一、…」小节）
# --------------------------------------------------------------------------- #

_CJK_NUMS = "一二三四五六七八九十"


def _extract_choice_pairs(text):
    """从文本提取选择题答案对 [(num, letters)]。

    优先解析 <table>（「题号」行 + 紧随的「答案」行）；否则解析内联
    「1. D 2. C …」形式。返回 (pairs, table_html_or_None)。
    """
    mt = RE_TABLE.search(text)
    if mt:
        rows = parse_html_table(mt.group(0))
        pairs = []
        for i, row in enumerate(rows):
            if not row or row[0].strip() not in ("题号", "題號"):
                continue
            if i + 1 >= len(rows):
                continue
            ans = rows[i + 1]
            for k in range(1, len(row)):
                num = row[k].strip()
                letters = ans[k].strip() if k < len(ans) else ""
                if num.isdigit() and letters and all(c in "ABCD" for c in letters):
                    pairs.append((int(num), letters))
        return pairs, mt.group(0)
    # 内联「N. X N. X …」：整行须全部为选择题答案对，且题号在 1~11
    pairs = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or "$" in s:
            continue
        found = re.findall(r"(\d{1,2})\s*[.．、]\s*([A-D]{1,4})(?=\s|$)", s)
        if not found:
            continue
        markers = re.findall(r"(?:^|\s)(\d{1,2})\s*[.．、]", s)
        if len(found) != len(markers):
            continue
        if not all(1 <= int(n) <= 11 and all(c in "ABCD" for c in a)
                   for n, a in found):
            continue
        pairs.extend((int(n), a) for n, a in found)
    return pairs, None


def _mk_answer_table(pairs):
    """由 [(num, letters)] 生成 MinerU 风格 <table> 文本。"""
    hs = "".join("<td>%d</td>" % n for n, _ in pairs)
    vs = "".join("<td>%s</td>" % a for _, a in pairs)
    return ("<table><tr><td>题号</td>%s</tr>"
            "<tr><td>答案</td>%s</tr></table>" % (hs, vs))


def _synthesize_no_section(lines):
    """无题型小节时，按题号顺序合成「选择 / 填空 / 解答」小节。

    返回 (new_lines, title_candidate)：
      * 选择题答案（<table> 或内联 1~11）→ 单选 / 多选 两个小节；
      * 12~14 → 填空题小节；15 及以后 → 解答题小节。
    """
    text = "\n".join(lines)
    pairs, _ = _extract_choice_pairs(text)

    # 顶层标题候选（如 2605 的 "## 数学模拟练习答案"）
    title = None
    for ln in lines:
        m = RE_HEADING.match(ln)
        if m and len(m.group(1)) <= 2 and "答案" in m.group(2):
            title = m.group(2).strip()
            break

    seq = [0]

    def _next():
        seq[0] += 1
        return (_CJK_NUMS[seq[0] - 1] if seq[0] <= len(_CJK_NUMS)
                else str(seq[0]))

    out = []
    singles = [p for p in pairs if len(p[1]) == 1]
    multis = [p for p in pairs if len(p[1]) >= 2]
    if singles:
        out += ["## %s、选择题" % _next(), _mk_answer_table(singles)]
    if multis:
        out += ["## %s、多项选择题" % _next(), _mk_answer_table(multis)]

    # 其余正文（剔除标题行、已抽取的表格行、已抽取的内联选择答案行）
    body = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if RE_HEADING.match(ln):
            continue
        if RE_TABLE.search(ln):
            continue
        found = re.findall(r"(\d{1,2})\s*[.．、]\s*([A-D]{1,4})(?=\s|$)", s)
        markers = re.findall(r"(?:^|\s)(\d{1,2})\s*[.．、]", s)
        if (found and len(found) == len(markers) and "$" not in s
                and all(1 <= int(n) <= 11 for n, _ in found)):
            continue
        body.append(ln)

    fill_head = solve_head = False
    for ln in body:
        m = re.match(r"^\s*(\d{1,2})\s*[.．、]", ln)
        if m:
            n = int(m.group(1))
            if n >= 15 and not solve_head:
                out.append("## %s、解答题" % _next())
                solve_head = True
            elif 12 <= n <= 14 and not fill_head and not solve_head:
                out.append("## %s、填空题" % _next())
                fill_head = True
        out.append(ln)
    return out, title


# --------------------------------------------------------------------------- #
#  主流程
# --------------------------------------------------------------------------- #

def convert(md_path, out_tex, img_base, img_srcs=None, exam_name=None):
    with open(md_path, encoding="utf-8") as f:
        raw = f.read().replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", ln) for ln in raw.split("\n")]
    # 先就地切除行内水印 token（公众号/浙考神墙/QQ 号），再丢弃整行水印
    lines = [strip_inline_watermark(ln) for ln in lines]
    lines = [ln for ln in lines if not is_watermark_line(ln)]
    units = fold_short_inlines(fold_dollars(lines))
    lines2 = []
    for kind, val in units:
        if kind == "text":
            lines2.append(val)
        else:  # formula：还原为单行 $$...$$ 交 parse 识别
            lines2.append("$$%s$$" % val)
    h1, sections = parse(lines2)
    if not sections:
        # 回退：源 MD 无「一、…」题型小节（如 2605/2610），按题号顺序合成小节
        fb_lines, fb_title = _synthesize_no_section(lines2)
        if fb_lines:
            _h1b, sections = parse(fb_lines)
            if not h1 and fb_title:
                h1 = [fb_title]
    if not sections:
        warn("未识别到任何题型小节，输出空答案卷")
    if exam_name is None:
        exam_name = h1[0] if h1 else "数学"
    text = build_tex(h1, sections, img_base, exam_name)
    out_dir = os.path.dirname(os.path.abspath(out_tex))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(text)
    if img_srcs:
        try:
            collect_images(text, out_dir, img_base, img_srcs)
        except Exception as ex:  # 容错：归集失败不影响 tex 产出
            warn("图片归集失败：%s" % ex)
    eprint("已生成：%s" % out_tex)
    eprint("统计：小节 %d；警告数 %d" % (len(sections), _WARN["n"]))


def main():
    ap = argparse.ArgumentParser(description="答案 Markdown → LaTeX")
    ap.add_argument("md", help="输入答案 Markdown")
    ap.add_argument("out", help="输出 tex 路径")
    ap.add_argument("--img-base", default="images", help="图片目录名（相对 tex）")
    ap.add_argument("--img-src", default=None, help="源图片目录（逗号分隔）")
    ap.add_argument("--exam-name", default=None, help="卷名（标题 / 页眉用）")
    args = ap.parse_args()
    if not os.path.exists(args.md):
        eprint("错误：输入文件不存在：%s" % args.md)
        sys.exit(2)
    srcs = [s.strip() for s in args.img_src.split(",") if s.strip()] if args.img_src else None
    convert(args.md, args.out, args.img_base, srcs, args.exam_name)


if __name__ == "__main__":
    main()