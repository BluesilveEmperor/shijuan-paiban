#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""md2english.py — MinerU OCR Markdown → 英语块流 IR（english.json）

以 52 份成品 tex 的 IR 为监督目标（``tex2english.py``），把 OCR Markdown 解析成同构的
``english.json``。解析前先经过 ``english_clean.py`` 清洗水印 / 垃圾串 / 标题泄漏。

映射规则（见 docs/english-corpus-findings.md）::

    # 考试名 / # 英语            → exam_title
    注意事项：+ 1./2./3.          → notice
    ## 第X部分 …                 → part
    ## 第X节 … / 第X节（…）        → section
    ## A / B / C / D              → passage_label
    N. 英文题干                   → question（「例：」例题无题号，EC-016）
    A. … B. … C. …（3 项）         → choices(3) 听力
    A. … B. … C. … D. …（4 项）    → choices(2) 阅读
    A. … G.（5–7 项）              → choices(1) 七选五
    N. A. … B. … C. … D.（同行）   → cloze（完形，每行一题）
    \_36\_ / \_\_\_\_41\_\_\_\_    → \blanknum{36}（嵌在 para.text）
    Paragraph 1: …               → writing_para + writing_lines{8}
    <table>…</table>             → raw（tabular，逃生舱）
    ![](images/…)                 → 丢弃并告警（EC-009：图片尚未打通）

用法::

    python scripts/render/md2english.py 试题.md -o english.json
    python scripts/render/md2english.py --schema
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from english_clean import CleaningStats, clean_markdown  # noqa: E402

RE_H1 = re.compile(r"^#\s+(.+?)\s*$")
RE_H2 = re.compile(r"^##\s+(.+?)\s*$")
RE_PART = re.compile(r"^第[一二三四五六七八九十]+部分")
RE_SECTION = re.compile(r"^第[一二三四五六七八九十]+节")
RE_PASSAGE = re.compile(r"^[A-D]$")
RE_READING_HINT = re.compile(r"阅读下列短文|阅读以下短文|阅读下面短文")
# 注意事项：OCR 可能是裸行、## 标题行，或带冒号
RE_NOTICE = re.compile(r"^(?:#{1,3}\s*)?(?:注意事项|考生须知|考生注意)\s*[：:]?\s*$")
# 编号条目：允许「1. 」「1.」「1．」「(1)」等；正文可能紧跟无空格
RE_NOTICE_ITEM = re.compile(r"^(?:\d{1,2}\s*[.．、]\s*|\(\d{1,2}\)\s*)")
RE_QNUM = re.compile(r"^(\d{1,2})\s*[.．、]\s*(.*)$")
RE_OPT = re.compile(r"^([A-G])\s*[.．、]\s*(.*)$")
RE_CLOZE_LINE = re.compile(r"^(\d{1,2})\s*[.．、]\s*A\s*[.．]?\s*(.*)$")
RE_INLINE_OPT = re.compile(r"([A-G])\s*[.．]\s*")
# 完形续行选项：B. / C. / D.（允许 OCR 用冒号或缺分隔点）
RE_CLOZE_NEXT = re.compile(r"^([B-D])\s*[.．:：]?\s*(.*)$")
RE_WRITING_PARA = re.compile(r"^Paragraph\s+([12])\s*:\s*(.*)$")
# 填空：匹配任意个「\_」或「_」包裹的 1-2 位题号。
# 旧式 r"\\_+\s*(\d*)\s*\\_+" 会对 \_\_\_\_36\_\_\_\_ 贪婪吞掉前两个 \_ 导致数字丢失。
RE_BLANK = re.compile(r"(?:\\?_)+\s*(\d{1,2})\s*(?:\\?_)+")
RE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
RE_QNUM_IN_TEXT = re.compile(r"^(\d+)\.")
# 裸数字填空（OCR 丢失 \_ 标记）：独立 2 位数字，前后非单词字符/反斜杠/百分号
RE_BARE_NUM = re.compile(r"(?<![\w\\])([3-6]\d)(?![\w%])")
ASCII_LETTER = re.compile(r"[A-Za-z]")

# 各 section 内裸数字应落入的填空号区间（EC-002）
SECTION_BARE_RANGE = {
    "seven": (36, 40),    # 七选五
    "grammar": (56, 65),  # 语法填空
}


def near_image(lines: list, i: int, span: int = 2) -> bool:
    """当前行附近（前 span 行内）是否有图片引用。"""
    for k in range(max(0, i - span), i):
        if RE_IMAGE.search(lines[k]):
            return True
    return False


def section_kind(text: str) -> str | None:
    """由小节标题推断题型，用于裸数字填空的范围约束。"""
    t = re.sub(r"\s+", "", text)
    m = re.search(r"每小题([\d.]+)分", t)
    score = float(m.group(1)) if m else None
    n = re.search(r"共(\d+)小题", t)
    num = int(n.group(1)) if n else None
    if num == 5 and score == 2.5:
        return "seven"
    if num in (5,) and score == 2.0:
        return "seven"
    if num == 10 and score == 1.5:
        return "grammar"
    if num == 15 and score == 2.5:
        return "reading"
    if num == 15 and score == 1.0:
        return "cloze"
    if score == 1.5:
        return "listening"
    return None


def section_columns(kind: str | None, nitems: int) -> int:
    """列数：优先由 section 题型决定（听力3/阅读2/七选五1），回退到选项个数。"""
    if kind == "listening":
        return 3
    if kind == "reading":
        return 2
    if kind == "seven":
        return 1
    return 3 if nitems <= 3 else (2 if nitems == 4 else 1)


class ParseReport:
    def __init__(self):
        self.warnings = []
        self.cleaning = CleaningStats()

    def warn(self, msg):
        self.warnings.append(msg)


def tex_escape(s: str, report: ParseReport | None = None,
               bare_range: tuple[int, int] | None = None) -> str:
    """Markdown 文本 → TeX-ready 文本；保护 \blanknum / 已有转义。

    ``bare_range`` 指定时，在该题号区间内的“裸数字”（OCR 丢失 \\_ 标记，
    如 ``… mind. 36 From focusing…``）也补成 \\blanknum{N}。
    """
    if not s:
        return ""
    s = RE_IMAGE.sub("", s)
    holders = []

    def hold(text):
        holders.append(text)
        return f"\x00{len(holders) - 1}\x00"

    s = RE_BLANK.sub(lambda m: hold(f"\\blanknum{{{m.group(1)}}}"), s)
    if bare_range:
        lo, hi = bare_range
        def bare(m):
            n = int(m.group(1))
            if lo <= n <= hi:
                return hold(f"\\blanknum{{{n}}}")
            return m.group(0)
        s = RE_BARE_NUM.sub(bare, s)
    # 数学段 $...$ 整段保护：避免 $ → \$ 后其中的 \mathrm 等脱离数学模式报错。
    # 起止 $ 前不能是反斜杠（否则 \$215 … \$900 的中间段会被误当数学段，
    # 留下孤立 \ 被后续清理误伤成 ／）；非贪婪避免一次吞掉两段。
    s = re.sub(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", lambda m: hold(m.group(0)), s)
    s = re.sub(r"\\[%#&_$]", lambda m: hold(m.group(0)), s)
    # OCR 把分隔符 "/" 识成反斜杠 → 还原，避免 LaTeX 当成未定义命令
    s = re.sub(r"\\(?=[\u4e00-\u9fff])", "／", s)
    s = re.sub(r"\\(?![a-zA-Z\\\{}\[\]])", "／", s)
    s = s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
    s = s.replace("_", r"\_").replace("$", r"\$")
    for i, v in enumerate(holders):
        s = s.replace(f"\x00{i}\x00", v)
    return s.strip()


def split_inline_opts(text: str, first: str = "A") -> tuple:
    """拆行内选项：返回 (题干前缀, [(label, body)...])；无选项返回 (text, [])。

    与旧版不同：即使只识别到 1 个选项也返回列表，交给调用方做跨行续接。
    """
    parts = RE_INLINE_OPT.split(text)
    if len(parts) < 3 or parts[1] != first:
        return text, []
    stem = parts[0].rstrip()
    found = []
    for k in range(1, len(parts) - 1, 2):
        label, body = parts[k], parts[k + 1].strip()
        found.append((label, body))
        if label == "G":
            break
    return stem, found


def take_cloze(lines: list, i: int, report: ParseReport) -> tuple:
    """解析一行完形题：题号 + 4 选项，选项可跨行。返回 (cloze块, new_i)。

    处理两类 OCR 形态::

        41.A.friend B.neighbor C.teacher D.classmate     （同行 4 项）
        48. A. condition                                   （首项同行）
        B. attack / C. impact / D. symptom                （其余续行）
    """
    s = lines[i].strip()
    m = RE_CLOZE_LINE.match(s)
    if not m:
        return None, i
    number = int(m.group(1))
    # 完形题号固定 41-55（EC-002）；用范围兜底避免把
    # "1. A survey shows..." 这类 question 误判为完形
    if not 41 <= number <= 55:
        return None, i
    _, found = split_inline_opts(s, "A")
    opts = {lab: body for lab, body in found if lab in "ABCD" and body}
    # 若同行选项不足，从后续行按 B/C/D 顺序续接（允许空行）
    j = i + 1
    while opts and len(opts) < 4 and j < len(lines):
        nxt = lines[j].strip()
        if not nxt:
            j += 1
            continue
        if (RE_CLOZE_LINE.match(nxt) or RE_QNUM.match(nxt)
                or nxt.startswith("#") or RE_SECTION.match(nxt)
                or RE_PART.match(nxt)):
            break
        mo = RE_CLOZE_NEXT.match(nxt)
        if not mo:
            break
        label, body = mo.group(1), mo.group(2).strip()
        expected = chr(ord("A") + len(opts))
        if label != expected or not body:
            break
        opts[label] = body
        j += 1
    if not opts:
        return None, i
    ordered = [opts.get(c, "") for c in "ABCD"]
    if any(not x for x in ordered):
        report.warn(f"完形第 {number} 题选项不足 4 项，已保留 {len(opts)} 项")
    return {"type": "cloze", "number": number, "options": ordered}, j


def take_notice(lines: list, i: int, report: ParseReport) -> tuple:
    """从注意事项标题后收集编号条目（跳过空行），返回 (lines, new_i)。"""
    items = []
    j = i
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            j += 1
            continue
        if not RE_NOTICE_ITEM.match(s):
            break
        items.append("\\par " + tex_escape(s, report) + "\\par")
        j += 1
    return items, j


def take_options(lines: list, i: int, report: ParseReport) -> tuple:
    """收集选项（允许同行多项与中间空行），返回 (items, new_i)。

    处理两种 OCR 形态::

        A. Raising funds for bench care.       （一行一项）
        A. Business    B. Sports    C. Nature  （一行多项）
    """
    items = []
    j = i
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            # 仅在已收集到选项时跳过空行，避免开头空行吞掉后续无关段落
            if items:
                # 若空行后不是选项，则停止
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k >= len(lines) or not RE_OPT.match(lines[k].strip()):
                    break
            j += 1
            continue
        m = RE_OPT.match(s)
        if not m:
            break
        # 同行多选项：用行内拆分
        _, found = split_inline_opts(s, m.group(1))
        if len(found) >= 2:
            items.extend(tex_escape(body, report) for _, body in found)
        else:
            items.append(tex_escape(m.group(2), report))
        j += 1
    if not items:
        return None, i
    return items, j


def repair_blocks(blocks: list, report: ParseReport) -> list:
    """后处理修正两类 OCR 结构误判：

    1. 选项被 OCR 识成题号（如 ``A. By bus.`` / ``3. By taxi.`` / ``C. By subway.``）:
       表现为 question 前后的 choices 都是残片（<3 项）。把该题号块还原为选项并合并。
    2. 正文编号条款被误判为 question（如阅读文章里的 ``1. Your contest entry…``）:
       监督 IR 中 question 后必跟 choices；无 choices 的 question 降级为 para。
    """
    out = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["type"] != "question":
            out.append(b)
            i += 1
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        has_choices = bool(nxt and nxt["type"] == "choices")
        prev = out[-1] if out else None
        # 规则 1：前后 choices 都是残片 → 还原为选项并合并
        if (has_choices and len(nxt["items"]) < 3 and prev
                and prev["type"] == "choices" and len(prev["items"]) < 3):
            option = re.sub(r"^\s*\d+\s*[.．、]\s*", "", b["text"]).strip()
            merged = prev["items"] + [option] + nxt["items"]
            prev["items"] = merged
            prev["columns"] = 3 if len(merged) <= 3 else (2 if len(merged) == 4 else 1)
            report.warn(f"还原被 OCR 误识为选项的题号：{b['text'][:24]}")
            i += 2
            continue
        # 规则 2：question 后无 choices → 正文编号，降级为 para
        if not has_choices:
            out.append({"type": "para", "text": b["text"], "blanks": []})
            report.warn(f"题号块后无选项，降级为正文：{b['text'][:24]}")
            i += 1
            continue
        out.append(b)
        i += 1
    return out


def table_block(lines: list, i: int, report: ParseReport) -> tuple:
    """把 HTML <table> 转成两列 tabular 的 raw 块。"""
    j = i
    buf = []
    while j < len(lines) and "</table>" not in lines[j].lower():
        buf.append(lines[j])
        j += 1
    if j < len(lines):
        j += 1
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", "\n".join(buf), re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", td).strip()
                 for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        cells = [tex_escape(c, report) for c in cells]
        if cells:
            rows.append(cells)
    if not rows:
        report.warn("HTML 表格未能解析，已跳过")
        return None, j
    out = ["\\begin{center}", "\\begin{tabular}{|p{0.45\\linewidth}|p{0.45\\linewidth}|}", "\\hline"]
    for r in rows:
        out.append(" & ".join(r[:2]) + " \\\\")
        if len(rows) == 1 or r is rows[0]:
            out.append("\\hline")
    out.extend(["\\hline", "\\end{tabular}", "\\end{center}"])
    return {"type": "raw", "lines": out}, j


def parse_markdown(text: str, source: str = "") -> tuple:
    report = ParseReport()
    cleaned = clean_markdown(text, report.cleaning)
    lines = cleaned.splitlines()
    blocks = []
    para = []
    cur_bare_range = None  # 当前 section 的裸数字填空区间上下文

    def flush():
        if para:
            joined = " ".join(x.strip() for x in para if x.strip())
            para.clear()
            if joined:
                blocks.append({"type": "para", "text": tex_escape(
                    joined, report, bare_range=cur_bare_range), "blanks": []})

    exam_seen = False
    seen_part = False
    reading_seen = False  # 阅读说明出现后，裸行 A-D 认定为 passage_label
    last_section_text = ""  # 最近小节标题，用于推断 choices 列数
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            flush()
            i += 1
            continue

        if RE_IMAGE.search(ln):
            report.warn("源 md 含图片引用，已丢弃（EC-009）")
            i += 1
            continue

        if "<table" in ln.lower():
            flush()
            b, i = table_block(lines, i, report)
            if b:
                blocks.append(b)
            continue

        m = RE_H1.match(ln)
        if m:
            flush()
            value = m.group(1).strip()
            if not exam_seen:
                subject = value
                if i + 1 < len(lines):
                    m2 = RE_H1.match(lines[i + 1].strip())
                    if m2:
                        subject = m2.group(1).strip()
                        i += 1
                subject = subject.replace("试卷", "").strip() or "英语"
                blocks.append({"type": "exam_title", "mark": "", "title": value,
                               "subject": subject})
                exam_seen = True
            else:
                blocks.append({"type": "para", "text": tex_escape(value, report), "blanks": []})
            i += 1
            continue

        m = RE_H2.match(ln)
        if m:
            value = m.group(1).strip()
            # 「## 注意事项：」：H2 形态的注意事项，整块收集
            if RE_NOTICE.match(ln):
                flush()
                items, i = take_notice(lines, i + 1, report)
                if items:
                    blocks.append({"type": "notice", "lines": items})
                continue
            flush()
            cur_bare_range = None
            if RE_PART.match(value):
                blocks.append({"type": "part", "text": tex_escape(value, report)})
                seen_part = True
            elif RE_SECTION.match(value):
                blocks.append({"type": "section", "text": tex_escape(value, report)})
                last_section_text = value
                cur_bare_range = SECTION_BARE_RANGE.get(section_kind(value))
            elif RE_PASSAGE.match(value):
                blocks.append({"type": "passage_label", "text": value})
            else:
                blocks.append({"type": "para", "text": tex_escape(value, report), "blanks": []})
            i += 1
            continue

        if RE_NOTICE.match(ln) and not seen_part:
            flush()
            items, i = take_notice(lines, i + 1, report)
            if items:
                blocks.append({"type": "notice", "lines": items})
            continue

        # 裸行小节 / 部分（无 ## 前缀，OCR 常见）
        if RE_SECTION.match(ln) or RE_PART.match(ln):
            flush()
            cur_bare_range = None
            if RE_PART.match(ln):
                blocks.append({"type": "part", "text": tex_escape(ln, report)})
                seen_part = True
            else:
                blocks.append({"type": "section", "text": tex_escape(ln, report)})
                last_section_text = ln
                cur_bare_range = SECTION_BARE_RANGE.get(section_kind(ln))
            i += 1
            continue

        m = RE_WRITING_PARA.match(ln)
        if m:
            flush()
            blocks.append({"type": "writing_para",
                           "text": tex_escape("Paragraph " + m.group(1) + ": " + m.group(2), report)})
            blocks.append({"type": "writing_lines", "count": 8})
            i += 1
            continue

        if RE_CLOZE_LINE.match(ln):
            cloze, j = take_cloze(lines, i, report)
            if cloze:
                flush()
                blocks.append(cloze)
                i = j
                continue

        m = RE_QNUM.match(ln)
        if m and ASCII_LETTER.search(m.group(2)):
            flush()
            stem, found = split_inline_opts(ln, "A")
            opts = [body for _, body in found]
            question = tex_escape(stem, report)
            blocks.append({"type": "question", "text": question})
            if opts:
                cols = section_columns(section_kind(last_section_text), len(opts))
                blocks.append({"type": "choices", "columns": cols,
                               "indent": "  ", "items": [tex_escape(o, report) for o in opts]})
            i += 1
            continue

        if RE_OPT.match(ln):
            flush()
            items, i = take_options(lines, i, report)
            if items:
                cols = section_columns(section_kind(last_section_text), len(items))
                blocks.append({"type": "choices", "columns": cols,
                               "indent": "  ", "items": items})
            continue

        # 裸行 A-D：阅读说明之后认定为 passage_label（如第 1 篇 "A" 无 ## 前缀）。
        # 排除图片区（40 卷图片下方 A/B/C/D 是图注，不是篇章标记）。
        if reading_seen and RE_PASSAGE.match(ln) and not near_image(lines, i):
            flush()
            blocks.append({"type": "passage_label", "text": ln})
            i += 1
            continue

        if RE_READING_HINT.search(ln):
            reading_seen = True
        para.append(ln)
        i += 1

    flush()
    blocks = repair_blocks(blocks, report)

    questions, blanks, examples = [], set(), 0
    for b in blocks:
        t = b["type"]
        if t == "question":
            if b["text"].startswith("例："):
                examples += 1
            mq = RE_QNUM_IN_TEXT.match(b["text"])
            if mq:
                questions.append(int(mq.group(1)))
        elif t == "para":
            blanks.update(int(n) for n in re.findall(r"\\blanknum\{(\d+)\}", b["text"]))
            b["blanks"] = [int(n) for n in re.findall(r"\\blanknum\{(\d+)\}", b["text"])]
        elif t == "cloze":
            blanks.add(b["number"])
    titles = [b for b in blocks if b["type"] == "exam_title"]
    first = titles[0] if titles else {}

    meta = {
        "subject": "english",
        "kind": "shiti",
        "source": source,
        "title": first.get("title", ""),
        "exam_subject": first.get("subject", "英语"),
        "variant": "full" if questions and questions[0] == 1 else "no_listening",
        "question_count": sum(1 for b in blocks if b["type"] == "question"),
        "question_numbers": questions,
        "example_count": examples,
        "blank_numbers": sorted(blanks),
        "block_count": len(blocks),
        "cleaning": report.cleaning.as_dict(),
        "warnings": report.warnings,
    }
    return {"meta": meta, "blocks": blocks}, report


SCHEMA_EXAMPLE = {
    "meta": {
        "subject": "english", "kind": "shiti", "source": "01_2402武汉二调.md",
        "variant": "full", "title": "武汉市 2024 届高中毕业生二月调研考试",
        "exam_subject": "英语", "question_count": 35,
        "cleaning": {"watermark": 0, "garbage": 0, "section_leak": 0,
                     "entities": 0, "quotes": 0, "punctuation": 0},
    },
    "blocks": [
        {"type": "exam_title", "mark": "", "title": "武汉市 2024 届高中毕业生二月调研考试", "subject": "英语"},
        {"type": "notice", "lines": ["\\par 1. 答题前…\\par"]},
        {"type": "part", "text": "第一部分 听力（共两节，满分 30 分）"},
        {"type": "section", "text": "第一节（共5小题；每小题1.5分，满分7.5分）"},
        {"type": "question", "text": "1. What are the speakers probably doing?"},
        {"type": "choices", "columns": 3, "indent": "  ",
         "items": ["Discussing at work.", "Talking on phone.", "Driving on the way."]},
        {"type": "para", "text": "… \\blanknum{36} …", "blanks": [36]},
        {"type": "cloze", "number": 41, "options": ["crowded", "physical", "creature", "necessary"]},
        {"type": "writing_para", "text": "Paragraph 1: …"},
        {"type": "writing_lines", "count": 8},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?", help="OCR Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 english.json")
    ap.add_argument("--stdout", action="store_true", help="打印 JSON 到 stdout")
    ap.add_argument("--schema", action="store_true", help="打印 IR schema 示例")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not args.md:
        ap.error("需要提供 md 路径，或使用 --schema")

    src = Path(args.md)
    ir, report = parse_markdown(src.read_text(encoding="utf-8"), source=src.name)
    payload = json.dumps(ir, ensure_ascii=False, indent=2) + "\n"
    m = ir["meta"]
    print(f"[INFO] 清洗：{m['cleaning']}")
    for w in report.warnings[:10]:
        print(f"[WARN] {w}")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"[OK] {out}：{m['block_count']} 块 / {m['question_count']} 题 / "
              f"{len(m['blank_numbers'])} 个填空号")
    else:
        print(payload if args.stdout else
              f"[OK] {src.name}：{m['block_count']} 块（用 -o 写入或用 --stdout 打印）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
