#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""render_english.py — 英语试卷 IR（english.json）→ LaTeX 确定性渲染器

与数学 ``render_tex.py`` 的区别：不做排版决策（列数、题号、答题空间都由 IR 给定），
只把块直译成 ``英语试卷.cls`` / ``英语试卷.sty`` 的命令；校验只告警不擅改。

配套 ``tex2english.py``：52 套成品 tex → IR → tex 可逐字节往返。

题号约定（EC-002）见 ``docs/english-corpus-findings.md``；\blanknum 嵌在 para 内，
不是独立块；\cz 每行一题承载完形 41-55。

用法::

    python scripts/render/render_english.py english.json -o out.tex
    python scripts/render/render_english.py english.json --compare-with 原卷.tex
    python scripts/render/render_english.py --schema
    python scripts/render/render_english.py english.json -o out.tex --copy-sty
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # ACCESS-001：技能目录只读

ROOT = Path(__file__).resolve().parents[2]
TPL_DIR = ROOT / "templates" / "english"
DOC_BEGIN = "\\begin{document}"
DOC_END = "\\end{document}"


class RenderReport:
    def __init__(self):
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)


def _esc(v):
    return "" if v is None else str(v)


def render_block(b: dict, report: RenderReport) -> str:
    t = b.get("type")
    if t == "exam_title":
        mark = b.get("mark") or ""
        opt = f"[{mark}]" if mark else ""
        return f"\\examtitle{opt}{{{_esc(b.get('title'))}}}{{{_esc(b.get('subject'))}}}\n"
    # ---- 参考答案专用块（\documentclass[answers]{英语试卷}）----
    if t == "answer_title":
        return f"\\answertitle{{{_esc(b.get('title'))}}}{{{_esc(b.get('subject', '英语'))}}}\n"
    if t == "answers":
        # 一条答案行；groups 为 [(起始号, 终止号, 答案串), ...]，拼成 “1-5 BABCA \quad 6-10 …”
        groups = b.get("groups") or []
        if groups:
            parts = []
            for g in groups:
                start, end, ans = g[0], g[1], g[2]
                rng = f"{start}-{end}" if str(end) != str(start) else str(start)
                parts.append(f"{rng} {_esc(ans)}")
            body = r" \quad ".join(parts)
        else:
            body = _esc(b.get("text", ""))
        return f"\\answerline{{{body}}}\n"
    if t == "blank_answers":
        # 语法填空：\blankanswer{56}{for} \quad \blankanswer{57}{but/yet}
        items = b.get("items") or []
        body = r" \quad ".join(
            f"\\blankanswer{{{_esc(n)}}}{{{_esc(a)}}}" for n, a in items)
        return f"\\answerline{{{body}}}\n"
    if t == "writing_sample":
        # 写作范文：小标题 + 逐段 \par…\par
        out = f"\\writingtitle{{{_esc(b.get('title', '第一节'))}}}\n"
        for para in b.get("paragraphs", []):
            out += "\\par " + _esc(para) + "\\par\n"
        return out
    if t == "para":
        return "\\par " + _esc(b.get("text")) + "\\par\n"
    if t == "notice":
        return "\\begin{notice}\n" + "\n".join(_esc(x) for x in b.get("lines", [])) + "\n\\end{notice}\n"
    if t == "part":
        return f"\\parttitle{{{_esc(b.get('text'))}}}\n"
    if t == "section":
        return f"\\sectitle{{{_esc(b.get('text'))}}}\n"
    if t == "question":
        return f"\\question{{{_esc(b.get('text'))}}}\n"
    if t == "passage_label":
        return f"\\passagelabel{{{_esc(b.get('text'))}}}\n"
    if t == "writing_para":
        return f"\\writingpara{{{_esc(b.get('text'))}}}\n"
    if t == "writing_lines":
        return f"\\writinglines{{{b.get('count', 8)}}}\n"
    if t == "cloze":
        opts = b.get("options") or []
        if len(opts) != 4:
            report.warn(f"完形第 {b.get('number')} 题有 {len(opts)} 个选项（应为 4）")
        args = "".join("{" + _esc(o) + "}" for o in opts)
        return f"\\cz{{{b.get('number', '')}}}{args}\n"
    if t == "choices":
        cols = b.get("columns", 2)
        indent = b.get("indent", "  ")
        items = b.get("items") or []
        lines = [f"\\begin{{choices}}({cols})"]
        lines.extend(f"{indent}\\item {_esc(x)}" for x in items)
        lines.append("\\end{choices}")
        return "\n".join(lines) + "\n"
    if t == "raw":
        return "\n".join(_esc(x) for x in b.get("lines", [])) + "\n"
    report.warn(f"未知 block 类型 {t!r}，按 raw 原样输出")
    return "\n".join(_esc(x) for x in b.get("lines", b.get("tex", "").splitlines())) + "\n"


def check_numbering(blocks: list, report: RenderReport):
    """EC-002 / EC-006：缺号只告警，绝不自动补题。"""
    import re

    nos = []
    blanks = set()
    for b in blocks:
        t = b.get("type")
        if t == "question":
            m = re.match(r"(\d+)\.", b.get("text", ""))
            if m:
                nos.append(int(m.group(1)))
        elif t == "para":
            blanks.update(int(n) for n in re.findall(r"\\blanknum\{(\d+)\}", b.get("text", "")))
        elif t == "cloze":
            try:
                blanks.add(int(b.get("number")))
            except (TypeError, ValueError):
                pass
    if not nos:
        # 参考答案卷没有 question 块（用 answers / blank_answers），跳过题号检查
        if not any(b.get("type") in ("answers", "blank_answers", "answer_title")
                   for b in blocks):
            report.warn("IR 没有 question 块")
        return
    if nos[0] not in (1, 21):
        report.warn(f"question 起号异常：{nos[0]}")
    expect = list(range(nos[0], nos[0] + len(nos)))
    if nos != expect:
        missing = [n for n in expect if n not in nos]
        report.warn(f"题号不连续：缺失 {missing[:12]}")
    missing_blanks = [n for n in range(36, 66) if n not in blanks]
    if missing_blanks:
        report.warn(f"填空号 36-65 缺失 {missing_blanks}（EC-006：只告警）")


def render_paper(ir: dict) -> tuple:
    meta = ir.get("meta") or {}
    blocks = ir.get("blocks") or []
    report = RenderReport()
    check_numbering(blocks, report)

    preamble = meta.get("preamble")
    if not preamble:
        opt = "[answers]" if meta.get("kind") in ("daan", "answer") else ""
        preamble = (f"% !TEX program = xelatex\n\\documentclass{opt}{{英语试卷}}\n"
                    f"{DOC_BEGIN}\n")
    out = [preamble]
    for b in blocks:
        out.append(render_block(b, report))
    out.append(meta.get("postamble") or DOC_END + "\n")
    return "".join(out), report


SCHEMA_EXAMPLE = {
    "meta": {
        "subject": "english", "kind": "shiti",
        "preamble": "% !TEX program = xelatex\n\\documentclass{英语试卷}\n\\begin{document}\n",
        "postamble": "\\end{document}\n",
        "title": "武汉市 2024 届高中毕业生二月调研考试", "exam_subject": "英语",
    },
    "blocks": [
        {"type": "exam_title", "title": "武汉市 2024 届高中毕业生二月调研考试", "subject": "英语"},
        {"type": "para", "text": "武汉市 2024 届高中毕业生二月调研考试", "blanks": []},
        {"type": "notice", "lines": ["\\par 1. 答题前…\\par"]},
        {"type": "part", "text": "第一部分 听力（共两节，满分 30 分）"},
        {"type": "section", "text": "第一节（共5小题；每小题1.5分，满分7.5分）"},
        {"type": "question", "text": "1. What are the speakers probably doing?"},
        {"type": "choices", "columns": 3, "indent": "  ",
         "items": ["Discussing at work.", "Talking on phone.", "Driving on the way."]},
        {"type": "para", "text": "It turned out to be a/an \\blanknum{41} journey.",
         "blanks": [41]},
        {"type": "cloze", "number": 41, "options": ["crowded", "physical", "creature", "necessary"]},
        {"type": "writing_para", "text": "Paragraph 1: But at mile 19, Jeff began to worry."},
        {"type": "writing_lines", "count": 8},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir", nargs="?", help="english.json")
    ap.add_argument("-o", "--output", help="输出 tex 路径")
    ap.add_argument("--stdout", action="store_true", help="打印 tex 到 stdout")
    ap.add_argument("--schema", action="store_true", help="打印 IR schema 示例")
    ap.add_argument("--copy-sty", action="store_true", help="复制英语模板 cls/sty 到输出目录")
    ap.add_argument("--compare-with", help="与指定 tex 逐字节比对（返回码 0/1）")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not args.ir:
        ap.error("需要提供 english.json 路径，或使用 --schema")

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    tex, report = render_paper(ir)
    for w in report.warnings:
        print(f"[WARN] {w}")

    if args.compare_with:
        ref = Path(args.compare_with).read_text(encoding="utf-8")
        if tex == ref:
            print(f"[PASS] 逐字节一致：{args.compare_with}")
            return 0
        import difflib
        diff = list(difflib.unified_diff(ref.splitlines(), tex.splitlines(),
                                         fromfile="ref", tofile="gen", n=1))
        print(f"[FAIL] 与 {args.compare_with} 不一致，前 20 行差异：")
        print("\n".join(diff[:20]))
        return 1

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tex, encoding="utf-8")
        if args.copy_sty:
            for name in ("英语试卷.cls", "英语试卷.sty"):
                shutil.copy2(TPL_DIR / name, out.parent / name)
        print(f"[OK] {out}（{len(ir.get('blocks', []))} 块，{len(report.warnings)} 条告警）")
    else:
        print(tex if args.stdout else
              f"[OK] {args.ir}：{len(ir.get('blocks', []))} 块（用 -o 写入或用 --stdout 打印）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
