#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""tex2english.py — 英语成品 tex → 块流 IR（english.json）

设计原则与 ``tex2chinese.py`` 一致：**保真优先，结构化其次**。

- 行级语法覆盖 52 套样本的全部命令（题干、选项、完形、填空、写作、分节、
  卷头、注意事项）；表格等复杂结构整块收进 ``raw`` 块，逐字保留。
- 每个块同时携带结构化字段与原文信息，``render_english.py`` 只做块→命令直译，
  不重写排版。52 套样本可逐字节往返。

题号约定（EC-002，见 docs/english-corpus-findings.md）::

    question        1-35（无听力卷 21-35）
    \blanknum       36-65（七选五 36-40 / 完形 41-55 / 语法填空 56-65，嵌在 para 内）
    \cz             41-55（完形选项，每行一题）
    写作            66/67 不编号，\writingpara + \writinglines{8}

用法::

    python scripts/render/tex2english.py 01_2402武汉二调.tex -o english.json
    python scripts/render/tex2english.py --schema
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # ACCESS-001：技能目录只读

EXAM_RE = re.compile(
    r"^\\examtitle(?:\[([^\]]*)\])?\{((?:[^{}]|\{[^{}]*\})*)\}\{([^}]*)\}$")
PARA_RE = re.compile(r"^\\par (.*)\\par$")
PART_RE = re.compile(r"^\\parttitle\{(.*)\}$")
SECTION_RE = re.compile(r"^\\sectitle\{(.*)\}$")
QUESTION_RE = re.compile(r"^\\question\{(.*)\}$")
PASSAGE_RE = re.compile(r"^\\passagelabel\{(.*)\}$")
WRITING_PARA_RE = re.compile(r"^\\writingpara\{(.*)\}$")
WRITING_LINES_RE = re.compile(r"^\\writinglines\{(\d+)\}$")
CLOZE_RE = re.compile(
    r"^\\cz\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}$")
CHOICES_BEGIN_RE = re.compile(r"^\\begin\{choices\}\((\d+)\)$")
ITEM_RE = re.compile(r"^(\s*)\\item (.*)$")
BLANK_RE = re.compile(r"\\blanknum\{(\d+)\}")

NOTICE_BEGIN = "\\begin{notice}"
NOTICE_END = "\\end{notice}"
CHOICES_END = "\\end{choices}"
DOC_BEGIN = "\\begin{document}"
DOC_END = "\\end{document}"


def _first_group(text: str, rx: re.Pattern) -> list:
    m = rx.match(text)
    return list(m.groups()) if m else []


def parse_choices(lines: list, columns: int) -> dict:
    """解析 choices 环境；任何非标准行都退回 raw 保真。"""
    items, indent = [], "  "
    for line in lines[1:-1]:                      # 去 begin/end 行
        m = ITEM_RE.match(line)
        if not m:
            return {"type": "raw", "lines": list(lines)}
        indent = m.group(1)
        items.append(m.group(2))
    return {"type": "choices", "columns": columns,
            "indent": indent, "items": items}


def parse_tex(text: str, source: str = "") -> dict:
    """把一份英语成品 tex 解析为 english.json。"""
    lines = text.splitlines()
    begin = next((i for i, ln in enumerate(lines) if ln.strip() == DOC_BEGIN), None)
    if begin is None:
        raise ValueError("找不到 \\begin{document}")
    preamble = "\n".join(lines[:begin + 1]) + "\n"
    body = lines[begin + 1:]

    end = next((i for i, ln in enumerate(body) if ln.strip() == DOC_END), len(body))
    postamble = "\n".join(body[end:]) + ("\n" if body[end:] else "")
    body = body[:end]

    blocks = []
    raw = []
    i = 0

    def flush_raw():
        if raw:
            blocks.append({"type": "raw", "lines": list(raw)})
            raw.clear()

    while i < len(body):
        line = body[i]

        # notice 环境：整块收集
        if line == NOTICE_BEGIN:
            flush_raw()
            j = i + 1
            while j < len(body) and body[j] != NOTICE_END:
                j += 1
            if j >= len(body):
                raise ValueError("notice 环境未闭合")
            blocks.append({"type": "notice", "lines": list(body[i + 1:j])})
            i = j + 1
            continue

        # choices 环境：整块收集
        m = CHOICES_BEGIN_RE.match(line)
        if m:
            flush_raw()
            j = i + 1
            while j < len(body) and body[j] != CHOICES_END:
                j += 1
            if j >= len(body):
                raise ValueError("choices 环境未闭合")
            blocks.append(parse_choices(body[i:j + 1], int(m.group(1))))
            i = j + 1
            continue

        # 已知单行命令
        block = None
        g = _first_group(line, EXAM_RE)
        if g:
            block = {"type": "exam_title", "mark": g[0] or "", "title": g[1],
                     "subject": g[2]}
        g = _first_group(line, PARA_RE)
        if g:
            block = {"type": "para", "text": g[0],
                     "blanks": [int(n) for n in BLANK_RE.findall(g[0])]}
        g = _first_group(line, PART_RE)
        if g:
            block = {"type": "part", "text": g[0]}
        g = _first_group(line, SECTION_RE)
        if g:
            block = {"type": "section", "text": g[0]}
        g = _first_group(line, QUESTION_RE)
        if g:
            block = {"type": "question", "text": g[0]}
        g = _first_group(line, PASSAGE_RE)
        if g:
            block = {"type": "passage_label", "text": g[0]}
        g = _first_group(line, WRITING_PARA_RE)
        if g:
            block = {"type": "writing_para", "text": g[0]}
        g = _first_group(line, WRITING_LINES_RE)
        if g:
            block = {"type": "writing_lines", "count": int(g[0])}
        g = _first_group(line, CLOZE_RE)
        if g:
            block = {"type": "cloze", "number": int(g[0]), "options": list(g[1:])}

        if block is not None:
            flush_raw()
            blocks.append(block)
        else:
            raw.append(line)                 # 表格/未识别写法：原样保留
        i += 1

    flush_raw()

    questions = []
    examples = 0
    question_blocks = 0
    blanks = set()
    for b in blocks:
        if b["type"] == "question":
            question_blocks += 1
            if b["text"].startswith("例："):
                examples += 1                      # 听力例题，无题号（EC-016）
            m = re.match(r"(\d+)\.", b["text"])
            if m:
                questions.append(int(m.group(1)))
        if b["type"] == "para":
            blanks.update(b.get("blanks", []))
        if b["type"] == "cloze":
            blanks.add(b["number"])
    titles = [b for b in blocks if b["type"] == "exam_title"]
    first = titles[0] if titles else {}

    meta = {
        "subject": "english",
        "kind": "daan" if "[answers]" in preamble else "shiti",
        "source": source,
        "preamble": preamble,
        "postamble": postamble,
        "title": first.get("title", ""),
        "exam_subject": first.get("subject", "英语"),
        "variant": "full" if questions and questions[0] == 1 else "no_listening",
        "question_count": question_blocks,
        "question_numbers": questions,
        "example_count": examples,
        "blank_numbers": sorted(blanks),
        "block_count": len(blocks),
    }
    return {"meta": meta, "blocks": blocks}


SCHEMA_EXAMPLE = {
    "meta": {
        "subject": "english", "kind": "shiti", "source": "01_2402武汉二调.tex",
        "variant": "full", "preamble": "% !TEX program = xelatex\n\\documentclass{英语试卷}\n\\begin{document}\n",
        "postamble": "\\end{document}\n",
        "title": "武汉市 2024 届高中毕业生二月调研考试", "exam_subject": "英语",
        "question_count": 35, "question_numbers": [1, 2, 3],
        "blank_numbers": [36, 40, 41, 55, 56, 65], "block_count": 9,
    },
    "blocks": [
        {"type": "exam_title", "mark": "", "title": "武汉市 2024 届高中毕业生二月调研考试",
         "subject": "英语"},
        {"type": "para", "text": "武汉市 2024 届高中毕业生二月调研考试",
         "blanks": []},
        {"type": "notice", "lines": ["\\par 1. 答题前…\\par"]},
        {"type": "part", "text": "第一部分 听力（共两节，满分 30 分）"},
        {"type": "section", "text": "第一节（共5小题；每小题1.5分，满分7.5分）"},
        {"type": "question", "text": "1. What are the speakers probably doing?"},
        {"type": "choices", "columns": 3, "indent": "  ",
         "items": ["Discussing at work.", "Talking on phone.", "Driving on the way."]},
        {"type": "cloze", "number": 41, "options": ["crowded", "physical", "creature", "necessary"]},
        {"type": "raw", "lines": ["\\begin{center}", "\\begin{tabular}{ll}", "…", "\\end{tabular}", "\\end{center}"]},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tex", nargs="?", help="英语成品 tex")
    ap.add_argument("-o", "--output", help="输出 english.json")
    ap.add_argument("--stdout", action="store_true", help="打印 JSON 到 stdout")
    ap.add_argument("--schema", action="store_true", help="打印 IR schema 示例")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not args.tex:
        ap.error("需要提供 tex 路径，或使用 --schema")

    src = Path(args.tex)
    text = src.read_text(encoding="utf-8")
    ir = parse_tex(text, source=src.name)
    payload = json.dumps(ir, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        m = ir["meta"]
        print(f"[OK] {out}：{m['block_count']} 块 / {m['question_count']} 题 / "
              f"{len(m['blank_numbers'])} 个填空号")
    else:
        print(payload if args.stdout else
              f"[OK] {src.name}：{ir['meta']['block_count']} 块（用 -o 写入或用 --stdout 打印）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
