#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_render_chinese.py — 语文块流渲染器回归

三层：
  1. 块类型 → 命令的逐条断言（纯字符串，无编译）
  2. 集成：chinese-sample.json 渲染出的结构签名，必须与人工作品
     `2611嘉兴一模/chinese-shiti.tex` 前 5 题区段完全一致
  3. 校验告警：选项数不为 4、题号跳号时必须报警

`--compile` 追加真编译（断言 3 页）。约 5 秒。
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))
sys.path.insert(0, str(ROOT / "scripts"))

import render_chinese  # noqa: E402

FIXTURE = ROOT / "evals" / "fixtures_chinese" / "2611嘉兴一模"
SAMPLE = FIXTURE / "chinese-shiti.json"
REF_TEX = FIXTURE / "chinese-shiti.tex"

FAILS = []
SIG_RE = re.compile(
    r"\\(sechead|subsechead|question|material|duanju|scorenote|subans|ans)\{")


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}\n  expected={expected!r}\n  actual  ={actual!r}")


def structure(tex):
    return [ln.strip() for ln in tex.splitlines() if SIG_RE.match(ln.strip())]


def test_blocks():
    r = render_chinese.RenderReport()

    eq(render_chinese.render_block({"type": "sechead", "text": "一、阅读"}, r),
       "\\sechead{一、阅读}", "sechead")
    eq(render_chinese.render_block({"type": "subsechead", "text": "（一）阅读I"}, r),
       "\\subsechead{（一）阅读I}", "subsechead")
    eq(render_chinese.render_block({"type": "duanju", "text": "甲B乙C"}, r),
       "\\duanju{甲B乙C}", "duanju")

    mat = render_chinese.render_block(
        {"type": "material", "label": "材料一：", "text": ["段一", "段二"],
         "source": "（摘自《X》）"}, r)
    eq("\\material{材料一：}" in mat, True, "material 标签")
    eq("\\begin{materialtext}" in mat and "段一\n\n段二" in mat, True,
       "material 多段用空行分隔")
    eq("\\begin{flushright}（摘自《X》）\\end{flushright}" in mat, True,
       "material 出处右对齐")

    poem = render_chinese.render_block({"type": "poem", "lines": ["茶。", "香叶，嫩芽。"]}, r)
    eq(poem, "\\begin{poem}\n茶。\\\\\n香叶，嫩芽。\n\\end{poem}", "poem")

    q = render_chinese.render_block(
        {"type": "question", "no": 1, "stem": "题干（3分）",
         "options": ["A项", "B项", "C项", "D项"]}, r)
    eq(q.startswith("\\question{1}{题干（3分）}\n\\begin{choices}"), True, "question+choices")
    eq(q.count("\\item"), 4, "choices 四项")

    q2 = render_chinese.render_block(
        {"type": "question", "no": 5, "stem": "题干", "subs": ["（1）甲", "（2）乙"]}, r)
    eq(q2.count("\\par\\vspace{2.2em}"), 2, "小问各留一份空白")

    eq(render_chinese.render_block({"type": "ans", "no": 1, "text": "B（错）"}, r),
       "\\ans{1}{B（错）}", "ans")
    eq(render_chinese.render_block({"type": "subans", "label": "（2）", "text": "示例"}, r),
       "\\subans{（2）}{示例}", "subans")
    eq(render_chinese.render_block({"type": "scorenote", "text": "（每点2分）"}, r),
       "\\scorenote{（每点2分）}", "scorenote")
    eq(r.warnings, [], "合法块不应产生告警")


def test_warnings():
    r = render_chinese.RenderReport()
    render_chinese.render_block(
        {"type": "question", "no": 1, "stem": "x", "options": ["A", "B", "C"]}, r)
    eq(any("选项" in w for w in r.warnings), True, "三项选项必须告警")

    ir = {"meta": {"title": "t"}, "blocks": [
        {"type": "question", "no": 1, "stem": "a"},
        {"type": "question", "no": 3, "stem": "b"},
    ]}
    r2 = render_chinese.RenderReport()
    render_chinese.check_numbering(ir["blocks"], r2)
    eq(any("题号不连续" in w for w in r2.warnings), True, "跳号必须告警")


def test_integration():
    ir = json.loads(SAMPLE.read_text(encoding="utf-8"))
    tex, report = render_chinese.render_paper(ir)
    eq(report.warnings, [], "样例 IR 渲染无告警")

    ref = structure(REF_TEX.read_text(encoding="utf-8"))
    got = structure(tex)
    eq(len(got), len(ref), "结构命令条数与人工成品一致")
    eq(got, ref, "结构签名与人工成品逐条一致")


def find_xelatex():
    import glob
    p = shutil.which("xelatex")
    if p:
        return p
    for pat in (r"D:\texlive\*\bin\windows\xelatex.exe",
                r"?:\texlive\*\bin\windows\xelatex.exe",
                r"/usr/local/texlive/*/bin/*/xelatex"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def test_compile():
    xelatex = find_xelatex()
    if not xelatex:
        print("SKIP 未找到 xelatex，跳过渲染编译")
        return
    ir = json.loads(SAMPLE.read_text(encoding="utf-8"))
    tex, _ = render_chinese.render_paper(ir)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        (work / "chinese-sample.tex").write_text(tex, encoding="utf-8")
        shutil.copy2(render_chinese.STY_DIR / render_chinese.STY_NAME,
                     work / render_chinese.STY_NAME)
        rc = 1
        for _ in range(2):
            rc = subprocess.run(
                [xelatex, "-interaction=nonstopmode", "chinese-sample.tex"],
                cwd=str(work), capture_output=True).returncode
        eq(rc, 0, "样例编译退出码")
        log = work / "chinese-sample.log"
        missing = log.read_text(encoding="utf-8", errors="ignore").count(
            "Missing character") if log.exists() else -1
        eq(missing, 0, "无 Missing character")


def main():
    test_blocks()
    test_warnings()
    test_integration()
    if "--compile" in sys.argv:
        test_compile()

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_render_chinese: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
