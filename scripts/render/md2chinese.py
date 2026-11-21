#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2chinese.py — MinerU OCR Markdown → 语文块流 IR

输入：``math_pdf_extract.py`` / ``pdf_extract.py`` 从语文试卷 PDF 提取的 Markdown
输出：``render_chinese.py`` 可消费的 chinese.json

解析策略（针对 2511 杭州一模 OCR 样本标定）：

    # 标题                         → meta.title
    ## 一、阅读（72 分）            → sechead
    ## (一) 阅读 I（本题共 5 小题）  → subsechead
    ## 材料一：                     → material.label
    材料正文 + (节选自…)            → material.text / material.source
    阅读下面的文字，完成 1~5 题。    → lead
    1. 题干（3 分）                 → question
    A. … / B. … / C. … / D. …      → question.options（一行多项也支持）
    【注】…                        → note
    答案卷：1.C 2.D …               → ans；示例（1）… → subans；（4 分…） → scorenote

无法识别的内容一律原样进 `para` 块，保证不丢内容。

清洗与容错（2026-11 无锡卷复盘补充）：

    <sup>①</sup> / <br>      去 HTML 标签保留内容，<br> 当换行
    Ⅰ Ⅳ Ⅻ                    罗马数字转 ASCII（缺字形）
    23（60分）                无点号题号也能识别（作文题）
    …EF 11. 下列…             断句选项串与下一题号挤行 → 拆开
    短选项（≤8 字）            打 choices_layout=inline（原卷一行四列）
    题干后紧跟材料/断句        自动删 space（否则题干与内容被留白隔开）
    卷首「语 文 / 2026.11」     去重

用法::

    python scripts/render/md2chinese.py 试题.md -o chinese.json --kind shiti
    python scripts/render/md2chinese.py 答案.md -o daan.json --kind daan
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# ── 清洗 ──────────────────────────────────────────────────────

WATERMARK_RE = re.compile(r"微信公众号\s*朝文道\s*CwD", re.I)
HALLUCINATION_RE = re.compile(
    r"^\s*(The image contains|According to Rule|\[Empty String\]|"
    r"I'm sorry|As an AI|Note: the image)", re.I)

# MinerU 偶尔把富文本标签原样吐出来（<sup>①</sup> / <br> / <span>）
HTML_BR_RE = re.compile(r"<br\s*/?>", re.I)
HTML_TAG_RE = re.compile(
    r"</?(?:sup|sub|span|div|p|b|i|u|em|strong|font|s|strike|table|thead|"
    r"tbody|tr|td|th|ul|ol|li)\b[^>]*>", re.I)

# 罗马数字 Ⅰ-Ⅻ / ⅰ-ⅻ：西文字体与部分楷体缺字形，日志报
# "Missing character: There is no Ⅰ"，统一转 ASCII（Ⅰ→I、Ⅳ→IV）。
_ROMAN = "I II III IV V VI VII VIII IX X XI XII".split()
ROMAN_MAP = {}
for _i, _r in enumerate(_ROMAN):
    ROMAN_MAP[0x2160 + _i] = _r
    ROMAN_MAP[0x2170 + _i] = _r.lower()


def clean_markdown(text: str, fig_width: str = "0.5", keep_roman=False) -> str:
    lines = []
    for ln in text.splitlines():
        if HALLUCINATION_RE.match(ln):
            continue
        # MinerU VLM 偶尔把自己的识别规则说明当成正文输出
        # （如 "The Ground Truth image displays… According to Rule 2…"），
        # 直接进试卷正文，必须整行丢弃。
        if VLM_META_RE.search(ln):
            continue
        ln = WATERMARK_RE.sub("", ln)
        # HTML 残留：<br> 当换行，其余标签去掉保留内容（<sup>①</sup> → ①）
        ln = HTML_BR_RE.sub("\n", ln)
        ln = HTML_TAG_RE.sub("", ln)
        # MinerU 的转义：\_ -> _, \~ -> ~, \{ -> {, \% 保留
        ln = ln.replace("\\_", "_").replace("\\~", "~")
        ln = ln.replace("\\{", "{").replace("\\}", "}")
        # 罗马数字 → ASCII（缺字形，见 ROMAN_MAP）；--keep-roman 可保留原字
        if not keep_roman:
            ln = ln.translate(ROMAN_MAP)
        # 脚注 $^{①}$ -> ①（随后统一转 \xq）
        ln = re.sub(r"\$\^\{([^}]*)\}\$", r"\1", ln)
        # 圈号 ①-⑳：西文字体缺字形，改走模板的 \xq{}（textcircled 绘制）
        def _circled(m):
            return r"\xq{%d}" % (ord(m.group(0)) - 0x2460 + 1)
        ln = re.sub(r"[\u2460-\u2473]", _circled, ln)
        # OCR 偶把 ① 拆成「1⃝」（U+20DD 组合圆圈）；带括号数字 ⑴-⒇ → （1）
        ln = re.sub(r"(\d)?\u20dd",
                    lambda m: (r"\xq{%s}" % m.group(1)) if m.group(1) else "", ln)
        ln = re.sub(r"[\u2474-\u2487]",
                    lambda m: f"（{ord(m.group(0)) - 0x2473}）", ln)
        # OCR 图片 → LaTeX（图片文件随 OCR 输出一起拷到工作目录）
        # 宽度默认 0.5\linewidth：语文配图（地图/示意图）过宽会被整体推到下一页，
        # 与题干分页隔开；放不下时按 0.52 → 0.44 继续缩（--fig-width 可改）。
        ln = re.sub(r"!\[[^\]]*\]\(([^)]+)\)",
                    r"\\includegraphics[width=" + fig_width + r"\\linewidth]{\1}", ln)
        # <br> 已转成 \n：按真实行拆开，避免整段塞进一个 para 块
        lines.extend(part.rstrip() for part in ln.split("\n"))
    return "\n".join(lines)


def tex_escape(s: str) -> str:
    """转义 LaTeX 特殊字符，但保护 $…$ / \\(…\\) 数学段与已有转义。"""
    if not s:
        return ""
    holders = []

    def hold(m):
        holders.append(m.group(0))
        return f"\x00{len(holders) - 1}\x00"

    s = re.sub(r"\$[^$]+\$", hold, s)
    s = re.sub(r"\\\([^)]*\\\)", hold, s)
    # 已有转义先占位，避免二次转义
    s = re.sub(r"\\[%#&_$]", hold, s)
    # OCR 常把分隔符「/」识成反斜杠（「当之无愧\名副其实」）→ 还原为斜杠，
    # 否则 LaTeX 会当成未定义命令。必须在生成新的 \_ \% 之前做，否则会误伤。
    s = re.sub(r"\\(?=[\u4e00-\u9fa5])", "／", s)
    s = re.sub(r"\\(?![a-zA-Z\\\{}\[\]])", "／", s)
    s = s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
    s = s.replace("_", r"\_")
    for i, v in enumerate(holders):
        s = s.replace(f"\x00{i}\x00", v)
    return s


# ── 行模式 ────────────────────────────────────────────────────

RE_HEAD = re.compile(r"^#{1,3}\s*(.+?)\s*$")
RE_SEC = re.compile(r"^([一二三四五六七八九十]+、.+)$")
RE_SUBSEC = re.compile(r"^[（(]?[一二三四五六七八九十][）)]\s*.+$")
RE_MATERIAL = re.compile(r"^材料([一二三四五六七八九十]+)[：:]\s*(.*)$")
RE_SOURCE = re.compile(r"^[（(](节选自|摘编自|摘译自|选自|摘自).+[）)]\s*$")
RE_LEAD = re.compile(r"^阅读(下面|下列)的文字?[,，]?\s*完成\s*[\d~～\-—]+\s*题")
RE_QNUM = re.compile(r"^(\d{1,2})\s*[.．、]\s*(.*)$")
# 「23（60分）」这类没有点号、直接跟分值括号的作文题题号（原 RE_QNUM 匹配不到，
# 会导致答案/试题缺号）。要求分值括号紧跟题号，避免误伤「第 3（1）题」之类。
RE_QNUM_SCORE = re.compile(r"^(\d{1,2})\s*[（(]\s*(\d{1,3})\s*分\s*[）)]\s*(.*)$")
RE_OPT_LINE = re.compile(r"^([A-D])\s*[.．、]\s*(.*)$")
RE_INLINE_OPTS = re.compile(r"([A-D])\s*[.．、]\s*")
RE_SUBQ = re.compile(r"^[（(](\d{1,2})[）)]\s*(.{2,})$")
RE_NOTE = re.compile(r"^[【\[]注[】\]]")
# 卷首「注意事项 / 考生须知」区：里面的 1./2./3. 不是题目
RE_NOTICE_HEAD = re.compile(r"^(注意事项|考生须知|考生注意)")
# 注意事项条目的内容特征（卷首那些 1./2./3. 不是题目）
RE_NOTICE_ITEM = re.compile(
    r"^(答题前|考生务必|考生请|考生须|请将|请把|在答题卡|答题卡上|回答选择题|"
    r"选择题用|考试结束|考试时间|本卷满分|本试卷满分|本卷共|答卷|"
    r"考生作答|作答时请|考试时)")
# MinerU VLM 的规则说明文字（不是试题内容）
VLM_META_RE = re.compile(
    r"(Ground Truth|According to Rule|OCR result|the provided OCR|"
    r"Stylistic/Background Lines|not permitted under the|"
    r"must be ignored by the OCR|inconsistent with the Ground Truth)", re.I)
RE_SCORE = re.compile(r"^[（(]\s*\d{1,2}\s*分")
RE_CHOICE_LIST = re.compile(r"选择题\s*[：:]")

CN_NUM = "一二三四五六七八九十"


def split_inline_options(line: str):
    """一行里多个选项：A. xxx B. xxx C. xxx D. xxx → ['xxx', ...]。"""
    parts = RE_INLINE_OPTS.split(line)
    opts = []
    for i in range(1, len(parts) - 1, 2):
        label, body = parts[i], parts[i + 1].strip()
        if not opts and label != "A":
            break
        opts.append(body)
        if label == "D":
            break
    return opts if len(opts) == 4 else None


def is_option_line(line: str) -> bool:
    return bool(RE_OPT_LINE.match(line)) or split_inline_options(line) is not None


def take_options(lines, i):
    """从 i 开始收集 A/B/C/D 四项，允许中间夹空行。

    返回 (options 或 None, 新的游标)。**收集失败时必须退回原游标**，
    否则选项行会被主循环跳过、既不进 choices 也不进 para，直接丢失。
    """
    start = i
    found = {}
    while i < len(lines) and len(found) < 4:
        s = lines[i].strip()
        if not s:                      # 选项之间常夹空行，不能提前退出
            i += 1
            continue
        if RE_QNUM.match(s):           # 下一题开始
            break
        mh = RE_HEAD.match(s)
        if mh and (RE_SEC.match(mh.group(1).strip())
                   or RE_SUBSEC.match(mh.group(1).strip())):
            break
        inline = split_inline_options(s)
        if inline:
            for label, body in zip("ABCD", inline):
                found[label] = body
            i += 1
            break
        m = RE_OPT_LINE.match(s)
        if m and m.group(1) in "ABCD":
            found[m.group(1)] = m.group(2).strip()
            i += 1
            continue
        break

    if len(found) == 4:
        return [found[k] for k in "ABCD"], i
    return None, start


def split_inline_questions(line: str):
    """把一行里的多个题号拆成多行。

    OCR 常把「1.xxx      2.yyy      3.zzz」挤在一行（多空格分隔），
    题号正则只认行首，不拆就会整行漏掉。

    另一种更隐蔽的挤行：断句题选项串（…EF）后面紧跟下一题号
    「…后必为边患F已而果然 EF 11. 下列对…」，字母串与题号之间只有一个空格，
    按「≥2 空格」切不开，这里单独在「字母串 + 空格 + 题号+汉字」处切。

    第三种（实测 Z20 卷）：题号整段黏在上一块的句末——
    「【注】①支道林：…③土锉：…炊具。15.下列对这首诗…」，整行被当成注释读走，
    第 15 题凭空消失。凡是「句末标点 + 题号 + 汉字/引号」都切开。
    """
    if not re.search(r"\d{1,2}\s*[.．、]", line):
        return [line]
    line = re.sub(r"(?<=[A-H])\s+(?=\d{1,2}\s*[.．、]\s*[\u4e00-\u9fa5])", "\n", line)
    line = re.sub(r"(?<=[。！？；])[ \t　]*(?=\d{1,2}\s*[.．、]\s*[\u4e00-\u9fa5“（])",
                  "\n", line)
    parts = []
    for seg in line.split("\n"):
        parts.extend(re.split(r"(?<=\S)\s{2,}(?=\d{1,2}\s*[.．、]\s*\S)", seg))
    return parts if len(parts) > 1 else [line.replace("\n", " ")]


def expand_inline_questions(lines):
    out = []
    for ln in lines:
        out.extend(split_inline_questions(ln))
    return out


def _para(chunk):
    txt = "\n".join(chunk).strip("\n")
    return {"type": "para", "text": tex_escape(txt)} if txt.strip() else None


def parse_qnum(s: str):
    """行首题号 → (no, stem)；认不出来返回 None。

    兼容三种 OCR 写法：
      1. 题干                （标准，点号分隔）
      23（60分）             （作文题，题号后直接跟分值括号）
      23 题：…               （答案卷偶尔的写法，由 parse_daan 处理）
    """
    m = RE_QNUM.match(s)
    if m:
        return int(m.group(1)), m.group(2).strip()
    m = RE_QNUM_SCORE.match(s)
    if m:
        return int(m.group(1)), f"（{m.group(2)}分）" + m.group(3).strip()
    m = re.match(r"^(\d{1,2})\s*题\s*[：:]\s*(.*)$", s)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None


def visible_len(text):
    """选项可见字符数（忽略空白、花括号、反斜杠、$）。"""
    return len(re.sub(r"[\s{}\\$]", "", str(text)))


INLINE_OPTION_MAXLEN = 8      # 四选项都 ≤8 字 → 原卷多为一行四列（TASKS-COL-001）


def rescue_orphan_options(blocks):
    """把掉进 para 块的 A/B/C/D 选项捞回最近的题目。

    OCR 常把选项插进材料段落或题干行里，主解析的 take_options 只认紧邻的连续
    选项行，漏掉的会落进 para。这里做后处理：抽出行首 A./B./C./D.（含同行多项），
    攒够四项就挂到后面最近的、还没有 options 的题目上。
    """
    out = []
    pending = {}
    pending_lines = []      # 原始行：找不到归属时恢复，绝不丢内容

    def try_attach():
        nonlocal pending
        # 选项可能跨多个 para，且题目可能在选项之前或之后：
        # 攒够四项就回挂到最近一个还没有 options 的题目
        if len(pending) != 4:
            return
        for prev in reversed(out):
            if prev.get("type") == "question" and "options" not in prev:
                prev["options"] = [tex_escape(pending[k]) for k in "ABCD"]
                pending = {}
                pending_lines.clear()
                break

    for b in blocks:
        if b.get("type") == "para":
            kept = []
            for ln in b["text"].splitlines():
                s = ln.strip()
                inline = split_inline_options(s)
                if inline:
                    for label, body in zip("ABCD", inline):
                        pending[label] = body
                    pending_lines.append(ln)
                    continue
                m = RE_OPT_LINE.match(s)
                if m and m.group(1) in "ABCD":
                    pending[m.group(1)] = m.group(2).strip()
                    pending_lines.append(ln)
                    continue
                kept.append(ln)
            if any(x.strip() for x in kept):
                out.append({"type": "para", "text": "\n".join(kept).strip("\n")})
            try_attach()
            continue

        out.append(b)
        try_attach()

    # 没有归属的选项原样放回，宁可留在正文也不能丢
    if pending_lines:
        out.append({"type": "para", "text": "\n".join(pending_lines)})
    return out


# ── 试题解析 ──────────────────────────────────────────────────

def parse_shiti(lines, meta):
    lines = expand_inline_questions(lines)
    blocks = []
    i = 0
    pending = []            # 未归类文本缓冲
    material = None         # 当前材料块
    in_notice = False       # 卷首「注意事项」区内，1./2./3. 不是题目
    seen_title = False      # 卷首 # 标题已消费

    def flush():
        nonlocal pending
        if pending:
            b = _para(pending)
            if b:
                blocks.append(b)
            pending = []

    def flush_material():
        nonlocal material
        if material is not None:
            blocks.append(material)
            material = None

    while i < len(lines):
        s = lines[i].strip()
        if not s:
            pending.append("")
            i += 1
            continue

        # 标题行
        m = RE_HEAD.match(s)
        content = m.group(1).strip() if m else s

        # 卷首第一个 `#` 一级标题已进 meta，正文不再重复；
        # `##` 大题标题必须保留，不能当卷首标题跳过
        if m and not seen_title and s.lstrip().startswith("# "):
            seen_title = True
            i += 1
            continue

        # 任何标题行都意味着离开卷首注意事项区
        if m:
            in_notice = False

        # 卷首「注意事项」区：其中的 1./2./3. 条目不是题目
        if RE_NOTICE_HEAD.match(content) or RE_NOTICE_HEAD.match(s):
            in_notice = True
            pending.append(content if m else s)
            i += 1
            continue

        # 大题标题
        if m and RE_SEC.match(content):
            flush_material(); flush()
            blocks.append({"type": "sechead", "text": tex_escape(content)})
            i += 1
            continue

        # 材料标签
        mm = RE_MATERIAL.match(content)
        if mm:
            flush_material(); flush()
            material = {"type": "material", "label": f"材料{mm.group(1)}：",
                        "text": [], "source": None}
            i += 1
            continue

        # 小题标题（排除纯材料标签与题号）
        if m and RE_SUBSEC.match(content) and not RE_QNUM.match(content):
            flush_material(); flush()
            blocks.append({"type": "subsechead", "text": tex_escape(content)})
            i += 1
            continue

        # 导语
        if RE_LEAD.match(content):
            flush_material(); flush()
            blocks.append({"type": "lead", "text": tex_escape(content)})
            i += 1
            continue

        # 出处 → 归入最近的材料，并结束材料块（后面的选项/题目不属于材料）
        if RE_SOURCE.match(s):
            flush()
            if material is None:
                material = {"type": "material", "label": None,
                            "text": [], "source": None}
            material["source"] = tex_escape(s)
            flush_material()
            i += 1
            continue

        # 题号（卷首注意事项里的 1./2./3. 不算题目）
        # 用 content 而非 s：MinerU 常把题干排成标题行 `## 6.下列对本文…`，
        # 只看行首原始文本会漏（实测 Z20 卷第 6 题因此丢失）
        parsed = parse_qnum(content)
        if parsed and not in_notice and not RE_NOTICE_ITEM.match(parsed[1]):
            no, stem = parsed
            # OCR 偶尔把题干与 A/B/C/D 写在同一行；先拆出选项再继续
            inline = split_inline_options(stem)
            if inline:
                mpos = RE_INLINE_OPTS.search(stem)
                if mpos:
                    stem = stem[:mpos.start()].strip()
                opts = inline
            else:
                opts = None

            # 断句题的下一行字母串单独标记
            flush_material(); flush()
            i += 1
            if not opts:                   # 题干里没有，才从后续行收集
                opts, i = take_options(lines, i)

            # 断句行：题干含「断句」且下一行是 A/B/C 混排
            sub = []
            if "断句" in stem and i < len(lines):
                cand = lines[i].strip()
                if re.search(r"[A-H]", cand) and len(cand) > 12:
                    sub.append({"type": "duanju", "text": tex_escape(cand)})
                    i += 1

            q = {"type": "question", "no": no, "stem": tex_escape(stem)}
            if opts and len(opts) == 4:
                q["options"] = [tex_escape(o) for o in opts]
                # 短选项（1~3 字）原卷是一行四列，纵排会白占 4 行甚至多出一页
                if max(visible_len(o) for o in opts) <= INLINE_OPTION_MAXLEN:
                    q["choices_layout"] = "inline"
            else:
                q["space"] = True
            blocks.append(q)
            blocks.extend(sub)
            continue

        # 注释
        if RE_NOTE.match(s):
            flush_material(); flush()
            blocks.append({"type": "note", "text": tex_escape(s)})
            i += 1
            continue

        # 材料正文段落
        if material is not None:
            material["text"].append(tex_escape(s))
            i += 1
            continue

        # 未识别的标题行（篇名、作者等）去掉 # 前缀后按段落保留
        pending.append(content if m else s)
        i += 1

    flush_material(); flush()
    return blocks


# ── 答案解析 ──────────────────────────────────────────────────

def parse_daan(lines, meta):
    # OCR 常把相邻两题答案并到一行（「…（2分）。5. ①借助…」），先按句号拆开
    expanded = []
    for ln in lines:
        expanded.extend(re.split(r"(?<=[。）])\s*(?=\d{1,2}\s*[.．]\s*)", ln))
    lines = expanded
    lines = expand_inline_questions(lines)

    blocks = []
    i = 0
    pending = []

    def flush():
        nonlocal pending
        if pending:
            b = _para(pending)
            if b:
                blocks.append(b)
            pending = []

    # 头部「选择题：1.C 2.D …」汇总行 → 一组 ans
    while i < len(lines):
        s = lines[i].strip()
        if RE_CHOICE_LIST.match(s):
            flush()
            for m in re.finditer(r"(\d{1,2})\s*[.．、]?\s*([A-G](?:\s*[A-G])*)", s):
                blocks.append({"type": "ans", "no": int(m.group(1)),
                               "text": tex_escape(m.group(2).replace(" ", ""))})
            i += 1
            continue

        m = RE_HEAD.match(s)
        content = m.group(1).strip() if m else s
        if m and (RE_SEC.match(content) or RE_SUBSEC.match(content)):
            flush()
            typ = "sechead" if RE_SEC.match(content) else "subsechead"
            blocks.append({"type": typ, "text": tex_escape(content)})
            i += 1
            continue

        # 答案题号：3.（1）… / 17. … / 23（60分）/ 23 题：…
        # 用 content 而非 s：答案常被排成标题行 `## 15. (3分)C…`，
        # 只看原始行会漏号，且 `##` 会原样印进 PDF（实测成都三诊）
        pq = parse_qnum(content)
        if pq:
            flush()
            no, body = pq
            blocks.append({"type": "ans", "no": no, "text": tex_escape(body)})
            i += 1
            continue

        # 评分说明
        if RE_SCORE.match(s):
            flush()
            blocks.append({"type": "scorenote", "text": tex_escape(s)})
            i += 1
            continue

        # 子项答案：示例（1）：… / （1）…
        ms = re.match(r"^(示例\s*)?[（(](\d{1,2})[）)]\s*[：:]?\s*(.{2,})$", s)
        if ms:
            flush()
            label = f"示例（{ms.group(2)}）" if ms.group(1) else f"（{ms.group(2)}）"
            blocks.append({"type": "subans", "label": label,
                           "text": tex_escape(ms.group(3))})
            i += 1
            continue

        pending.append(content if m else s)
        i += 1

    flush()
    return blocks


# ── HTML 表格 ─────────────────────────────────────────────────

# MinerU 对表格材料/表格题会直接输出 `<table><tr><td>…`；原实现把标签一剥，
# 单元格全挤成一行（「语言"磨损"的"后遗症"①②③」），表格结构彻底丢失。
# 这里整块抓出来单独转 tabular，用占位符隔开，路由到 IR 的 raw 块。
TABLE_BLOCK_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)
TABLE_TOKEN = "@@YWTABLE%d@@"
# 表格单元格不经 clean_markdown，圈号要在这里自己转 \xq（否则缺字形丢字）
CIRCLED_RE = re.compile(r"[\u2460-\u2473]")


def _xq(s: str) -> str:
    return CIRCLED_RE.sub(
        lambda m: "\\xq{%d}" % (ord(m.group(0)) - 0x2460 + 1), s)


def table_html_to_latex(html: str) -> str:
    """HTML 表格 → 居中 tabular（booktabs 风格边框）。

    rowspan/colspan 一律忽略（原卷合并单元格只影响视觉，不影响取字），
    缺格补空串，列数取各行最大值；长单元格自动改 p{} 列宽避免溢出。
    """
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                 for c in cells]
        if cells:
            rows.append([_xq(tex_escape(c)) for c in cells])
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    longest = max((len(c) for r in rows for c in r), default=0)
    if longest > 10:
        # 列宽必须扣掉每列 2\tabcolsep，否则 5~6 列的评分标准表必然 Overfull
        # （实测 6 列 p{0.15\linewidth} 溢出 25.9pt）
        w = f"\\dimexpr 0.98\\linewidth/{ncol}-2\\tabcolsep\\relax"
        spec = "|" + "|".join([f"p{{{w}}}"] * ncol) + "|"
    else:
        spec = "|" + "|".join(["c"] * ncol) + "|"
    out = ["\\begin{center}", f"\\begin{{tabular}}{{{spec}}}", "\\hline"]
    for i, r in enumerate(rows):
        r = r + [""] * (ncol - len(r))
        out.append(" & ".join(r) + " \\\\")
        out.append("\\hline")
    out += ["\\end{tabular}", "\\end{center}"]
    return "\n".join(out)


def extract_tables(md_text: str):
    """把 HTML 表格换成占位符；返回 (新文本, {占位符: LaTeX})。"""
    tables = {}

    def _stash(m):
        key = TABLE_TOKEN % len(tables)
        tex = table_html_to_latex(m.group(0))
        if not tex:
            return ""
        tables[key] = tex
        return f"\n{key}\n"

    return TABLE_BLOCK_RE.sub(_stash, md_text), tables


def resolve_tables(blocks, tables):
    """占位符段落 → raw 块（表格前后同段的文字仍按段落保留）。"""
    if not tables:
        return blocks
    out = []
    for b in blocks:
        if b.get("type") not in ("para", "lead", "note"):
            out.append(b)
            continue
        txt = str(b.get("text") or "")
        hit = next((k for k in tables if k in txt), None)
        if hit is None:
            out.append(b)
            continue
        before, _, after = txt.partition(hit)
        if before.strip():
            out.append(dict(b, text=before.rstrip()))
        out.append({"type": "raw", "tex": tables[hit]})
        if after.strip():
            out.append(dict(b, text=after.lstrip()))
    return out


# ── 主入口 ────────────────────────────────────────────────────

# 题干后紧跟这些块时，题干后的留白会把题干与内容隔开（本次无锡卷 7 题踩过）
FOLLOW_CONTENT = {"para", "duanju", "material", "note", "poem", "heading",
                  "figure", "raw"}


def fix_space_before_content(blocks):
    """删掉「题干后紧跟内容块」的主观题 space。

    渲染器对「无选项、无小问」的主观题会在题干后插 \\par\\vspace{2.2em}
    （本意是留作答空白）。若下一块是作文材料/断句行/填空句，这段空白就错落在
    题干与内容之间。这里在 IR 层删掉 space（保留 IR→tex 的确定性）。
    确需留白时在 IR 里显式写 keep_space: true。
    """
    for i, b in enumerate(blocks):
        if b.get("type") != "question" or not b.get("space"):
            continue
        if b.get("options") or b.get("subs") or b.get("keep_space"):
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if nxt and nxt.get("type") in FOLLOW_CONTENT:
            b.pop("space", None)
    return blocks


def _norm(s):
    return re.sub(r"[\s　]+", "", str(s or ""))


# 卷首重复行：正标题/副标题的重复，以及「语 文 / 2026.11」这类栏目行
RE_MASTHEAD = re.compile(r"^(语文|数学|英语|物理|化学|生物|历史|地理|政治)"
                         r"[\s　]*[/／·.．]?[\s　]*\d{4}")
# 单独一行的科目名 / 年月（MinerU 常把卷头栏目拆成两行）
RE_SUBJECT_LINE = re.compile(r"^(语文|数学|英语|物理|化学|生物|历史|地理|政治)$")
RE_DATELINE = re.compile(r"^\d{4}([.．\-—/年]\d{1,2})?(月|日)?$")


def dedupe_leading_noise(blocks, meta, window=6):
    """卷首重复块去重。

    MinerU 会把卷头排成 「语 文」/「2026.11」/ 标题 / 副标题 / 「评分参考」，
    渲染后出现两三行重复大标题。这里只清**开头 window 块内**、且与
    title/subtitle 等价的 para/lead 行，正文里同名段落不动。
    一个 para 里多行栏目（「语 文」+「2026.11」）时只删命中行，其余保留。
    """
    targets = {_norm(meta.get("title")), _norm(meta.get("subtitle"))}
    targets.discard("")
    out = []
    for idx, b in enumerate(blocks):
        if idx < window and b.get("type") in ("para", "lead"):
            raw = str(b.get("text") or "")
            lines = [ln for ln in raw.splitlines() if ln.strip()]
            kept = [ln for ln in lines
                    if _norm(ln) not in targets
                    and not RE_MASTHEAD.match(_norm(ln))
                    and not RE_SUBJECT_LINE.match(_norm(ln))
                    and not RE_DATELINE.match(_norm(ln))]
            if not kept:
                continue
            if len(kept) != len(lines):
                b = dict(b, text="\n".join(kept))
        out.append(b)
    return out


def convert(md_text, kind="shiti", title=None, fig_width="0.5", keep_roman=False):
    md_text, tables = extract_tables(md_text)
    text = clean_markdown(md_text, fig_width, keep_roman)
    lines = text.splitlines()

    heads = [RE_HEAD.match(ln.strip()).group(1).strip()
             for ln in lines if ln.strip() and RE_HEAD.match(ln.strip())]
    meta = {
        "title": tex_escape(title or (heads[0] if heads else "")),
        "subtitle": "语文试题卷" if kind == "shiti" else "语文参考答案",
        "kind": kind,
        "footer": "语文试题卷" if kind == "shiti" else "语文参考答案",
    }
    if len(heads) > 1 and "答案" in heads[1]:
        meta["subtitle"] = tex_escape(heads[1])

    blocks = parse_shiti(lines, meta) if kind == "shiti" else parse_daan(lines, meta)
    if kind == "shiti":
        blocks = rescue_orphan_options(blocks)
        blocks = fix_space_before_content(blocks)
    blocks = resolve_tables(blocks, tables)
    # 表格转成 raw 块后，题干后紧跟的就是内容块 → 不起作用的留白再去一次
    blocks = fix_space_before_content(blocks)
    blocks = dedupe_leading_noise(blocks, meta)
    return {"meta": meta, "blocks": blocks}


def main():
    ap = argparse.ArgumentParser(description="OCR Markdown → 语文块流 IR")
    ap.add_argument("md", help="MinerU 提取的 .md")
    ap.add_argument("-o", "--output", help="输出 chinese.json（默认同名 .json）")
    ap.add_argument("--kind", choices=["shiti", "daan"], default="shiti")
    ap.add_argument("--title", help="覆盖卷首考试名")
    ap.add_argument("--fig-width", default="0.5",
                    help="配图宽度（相对 \\linewidth，默认 0.5；被推页时缩到 0.44）")
    ap.add_argument("--keep-roman", action="store_true",
                    help="保留 Ⅰ-Ⅻ 罗马数字（默认转 ASCII：部分字体缺字形会静默丢字）")
    args = ap.parse_args()

    ir = convert(Path(args.md).read_text(encoding="utf-8"), args.kind,
                 args.title, args.fig_width, args.keep_roman)
    out = Path(args.output) if args.output else Path(args.md).with_suffix(".json")
    out.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")

    kinds = {}
    for b in ir["blocks"]:
        kinds[b["type"]] = kinds.get(b["type"], 0) + 1
    print(f"[OK] {out}")
    print(f"     kind={args.kind} blocks={len(ir['blocks'])} "
          + " ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
