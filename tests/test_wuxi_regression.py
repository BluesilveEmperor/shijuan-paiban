#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_wuxi_regression.py — 无锡卷真实案例回归（2026-11 交付件）

夹具来自一次真实排版：`evals/fixtures_wuxi/` 下的
  shiti.md / daan.md               MinerU OCR 清洗后的 Markdown（入参）
  manual_shiti_ir.json / manual_daan_ir.json
                                   人工逐条修正后的 IR（**基准**）

断言「自动解析是否已复现人工修正」，这是 OCR 容错补丁的核心门禁：

  1. 题号 1–23 连续（人工修的是缺失的 9、11、23）
  2. `space` 集合一致（人工删了 7 道「题干后紧跟内容块」的错位留白）
  3. `choices_layout: inline` 只在第 18 题（2 字选项）
  4. 选择题 8 组 × 4 选项
  5. 答案卷 ans 题号 1–23 齐全

`--compile` 追加真编译，校验页数与交付件一致（试题 8 页 / 答案 4 页）。
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))

import md2chinese      # noqa: E402
import render_chinese  # noqa: E402

FIX = ROOT / "evals" / "fixtures_wuxi"
STY = ROOT / "templates" / "chinese" / "ywexam.sty"
FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}\n  expected={expected!r}\n  actual  ={actual!r}")


def auto_ir(md_name, kind):
    return md2chinese.convert((FIX / md_name).read_text(encoding="utf-8"), kind)


def questions(blocks):
    return {b["no"]: b for b in blocks if b["type"] == "question"}


def test_shiti_matches_manual():
    auto = auto_ir("shiti.md", "shiti")["blocks"]
    manual = json.loads((FIX / "manual_shiti_ir.json").read_text(encoding="utf-8"))["blocks"]
    aq, mq = questions(auto), questions(manual)

    eq(sorted(aq), list(range(1, 24)), "自动解析题号 1–23 连续")
    eq(sorted(aq), sorted(mq), "自动解析与人工 IR 题号一致")

    eq(sorted(n for n, b in aq.items() if b.get("space")),
       sorted(n for n, b in mq.items() if b.get("space")),
       "space 集合与人工 IR 一致（7 道错位留白已自动去掉）")

    eq(sorted(n for n, b in aq.items() if b.get("choices_layout")),
       sorted(n for n, b in mq.items() if b.get("choices_layout")),
       "choices_layout 与人工 IR 一致（仅第 18 题）")

    eq({n: len(b.get("options") or []) for n, b in aq.items() if b.get("options")},
       {n: len(b.get("options") or []) for n, b in mq.items() if b.get("options")},
       "选择题选项数与人工 IR 一致")


def test_daan_matches_manual():
    auto = auto_ir("daan.md", "daan")["blocks"]
    manual = json.loads((FIX / "manual_daan_ir.json").read_text(encoding="utf-8"))["blocks"]
    a_nos = sorted(b["no"] for b in auto if b["type"] == "ans")
    m_nos = sorted(b["no"] for b in manual if b["type"] == "ans")
    eq(a_nos, list(range(1, 24)), "答案卷 ans 题号 1–23 齐全")
    eq(a_nos, m_nos, "答案卷 ans 题号与人工 IR 一致")


def find_tool(name):
    import glob
    p = shutil.which(name)
    if p:
        return p
    for pat in (rf"D:\texlive\*\bin\windows\{name}.exe",
                rf"/usr/local/texlive/*/bin/*/{name}"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def pdf_pages(pdfinfo, pdf):
    out = subprocess.run([pdfinfo, str(pdf)], capture_output=True).stdout.decode(
        "utf-8", "replace")
    for ln in out.splitlines():
        if ln.startswith("Pages:"):
            return int(ln.split()[1])
    return None


def test_compile_pages():
    xelatex, pdfinfo = find_tool("xelatex"), find_tool("pdfinfo")
    if not (xelatex and pdfinfo):
        print("SKIP 缺 xelatex / pdfinfo，跳过编译比对")
        return

    jobs = [("shiti.md", "shiti", 1.35, "高三期中考试试卷", 8),
            ("daan.md", "daan", 1.35, "高三期中考试试卷·语文参考答案", 4)]
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        shutil.copy2(STY, work / STY.name)
        # 占位图与原卷配图同宽高比（892×473），只影响分页、不含原图水印
        shutil.copy2(FIX / "figure1.jpg", work / "figure1.jpg")
        for md, kind, ls, title, want in jobs:
            ir = auto_ir(md, kind)
            ir["meta"]["linespread"] = ls
            ir["meta"]["title"] = title
            if kind == "daan":
                ir["meta"]["subtitle"] = ""      # 只出一行大标题
            tex, _rep = render_chinese.render_paper(ir)
            f = work / f"{kind}.tex"
            f.write_text(tex, encoding="utf-8")
            for _ in range(2):
                subprocess.run([xelatex, "-interaction=nonstopmode", f.name],
                               cwd=str(work), stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            pdf = work / f"{kind}.pdf"
            if not pdf.exists():
                FAILS.append(f"FAIL {md} 编译未产出 PDF")
                continue
            got = pdf_pages(pdfinfo, pdf)
            eq(got, want, f"{md} 页数（交付件 {want} 页）")


def main():
    test_shiti_matches_manual()
    test_daan_matches_manual()
    if "--compile" in sys.argv:
        test_compile_pages()

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_wuxi_regression: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
