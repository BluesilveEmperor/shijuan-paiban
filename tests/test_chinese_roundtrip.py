#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chinese_roundtrip.py — 语文往返回归：人工 tex → IR → tex → PDF

这是语文侧最强的一道门禁，验证「块流 IR 的表达能力」：

  ref  = 人工成品 `chinese-{shiti,daan}.tex` 编译出的 PDF
  gen  = 同目录 IR（`chinese-*.json`）经 render_chinese 渲染后再编译出的 PDF

断言：页数一致、`pdftotext -layout` 文本逐行一致、`pdftoppm` 像素逐页一致。

两种模式：
  默认          只做 IR 结构检查（JSON 合法、块数与 tex 命令数吻合），约 0.2 秒
  `--compile`   完整往返比对，12 份约 3 分钟；`run_all.py --with-tex` 时启用
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

FIXTURES = ROOT / "evals" / "fixtures_chinese"
STY = ROOT / "templates" / "chinese" / "ywexam.sty"

FAILS = []


def find_tool(name):
    import glob
    p = shutil.which(name)
    if p:
        return p
    for pat in (rf"D:\texlive\*\bin\windows\{name}.exe",
                rf"?:\texlive\*\bin\windows\{name}.exe",
                rf"/usr/local/texlive/*/bin/*/{name}"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True)


def pdf_pages(pdfinfo, pdf):
    out = run(pdfinfo, str(pdf)).stdout.decode("utf-8", "replace")
    for ln in out.splitlines():
        if ln.startswith("Pages:"):
            return int(ln.split()[1])
    return None


def check_static():
    """IR 与成品 tex 的块数必须对得上（避免解析器静默丢块）。"""
    for shiti in sorted(FIXTURES.glob("*/chinese-shiti.tex")):
        folder = shiti.parent
        ir_path = folder / "chinese-shiti.json"
        if not ir_path.exists():
            FAILS.append(f"{folder.name} 缺少 chinese-shiti.json（先跑 tex2chinese.py）")
            continue
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        tex = shiti.read_text(encoding="utf-8")

        n_q_ir = sum(1 for b in ir["blocks"] if b["type"] == "question")
        n_q_tex = len(re.findall(r"\\question\{", tex))
        if n_q_ir != n_q_tex:
            FAILS.append(f"{folder.name} 题数不一致 IR={n_q_ir} tex={n_q_tex}")

        # 题号必须是 1..N 连续
        nos = [b["no"] for b in ir["blocks"] if b["type"] == "question"]
        if nos != list(range(1, len(nos) + 1)):
            FAILS.append(f"{folder.name} IR 题号不连续: {nos[:5]}…")

        # 选择题组必须 4 项
        for b in ir["blocks"]:
            if b.get("options") and len(b["options"]) != 4:
                FAILS.append(f"{folder.name} 第 {b.get('no')} 题选项数="
                             f"{len(b['options'])}")
        print(f"[PASS] {folder.name} IR 结构（{len(ir['blocks'])} 块 / {n_q_ir} 题）")


def check_compile():
    xelatex = find_tool("xelatex")
    pdftotext = find_tool("pdftotext")
    pdfinfo = find_tool("pdfinfo")
    pdftoppm = find_tool("pdftoppm")
    if not (xelatex and pdftotext and pdfinfo):
        print("SKIP 缺 xelatex / pdftotext / pdfinfo，跳过往返编译")
        return

    cases = sorted(FIXTURES.glob("*/chinese-*.tex"))
    for tex in cases:
        folder = tex.parent
        ir_path = folder / f"{tex.stem}.json"
        if not ir_path.exists():
            FAILS.append(f"{folder.name}/{tex.stem} 缺少 IR")
            continue

        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        gen_tex, report = render_chinese.render_paper(ir)
        if report.warnings:
            FAILS.append(f"{folder.name}/{tex.stem} 渲染告警: {report.warnings}")

        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            shutil.copy2(STY, work / STY.name)
            for f in folder.iterdir():
                if f.is_file() and f.suffix in (".tex", ".png", ".pdf"):
                    shutil.copy2(f, work / f.name)

            (work / "gen.tex").write_text(gen_tex, encoding="utf-8")
            for name in ("gen.tex", tex.name):
                for _ in range(2):
                    rc = run(xelatex, "-interaction=nonstopmode", name,
                             cwd=str(work)).returncode
                    if rc != 0:
                        FAILS.append(f"{folder.name}/{name} 编译失败 rc={rc}")
                        break

            gen_pdf = work / "gen.pdf"
            ref_pdf = work / f"{tex.stem}.pdf"
            if not gen_pdf.exists() or not ref_pdf.exists():
                FAILS.append(f"{folder.name}/{tex.stem} 缺少 PDF")
                continue

            pg, pr = pdf_pages(pdfinfo, gen_pdf), pdf_pages(pdfinfo, ref_pdf)
            if pg != pr:
                FAILS.append(f"{folder.name}/{tex.stem} 页数 gen={pg} ref={pr}")

            tg = run(pdftotext, "-layout", str(gen_pdf)).stdout.decode("utf-8", "replace")
            tr = run(pdftotext, "-layout", str(ref_pdf)).stdout.decode("utf-8", "replace")
            if tg.splitlines() != tr.splitlines():
                diff = sum(1 for a, b in zip(tg.splitlines(), tr.splitlines()) if a != b)
                FAILS.append(f"{folder.name}/{tex.stem} 文本差 {diff} 行")

            px = "未比对"
            if pdftoppm:
                (work / "px").mkdir(exist_ok=True)
                run(pdftoppm, "-r", "110", "-png", str(gen_pdf), str(work / "px" / "g"))
                run(pdftoppm, "-r", "110", "-png", str(ref_pdf), str(work / "px" / "r"))
                gs = sorted((work / "px").glob("g-*.png"))
                rs = sorted((work / "px").glob("r-*.png"))
                same = len(gs) == len(rs) and all(
                    g.read_bytes() == r.read_bytes() for g, r in zip(gs, rs))
                px = "一致" if same else "不同"
                if not same:
                    FAILS.append(f"{folder.name}/{tex.stem} 像素不一致")

            ok = not any(f.startswith(f"{folder.name}/{tex.stem}") for f in FAILS)
            print(f"{'[PASS]' if ok else '[FAIL]'} {folder.name}/{tex.stem} "
                  f"{pg}页 文本{'一致' if ok else '不同'} 像素{px}")


def main():
    if not STY.exists():
        print(f"FAIL 模板缺失: {STY}")
        return 1
    check_static()
    if "--compile" in sys.argv:
        check_compile()

    if FAILS:
        for f in FAILS:
            print(f"FAIL {f}")
        return 1
    print(f"\n语文往返回归通过（{'含编译' if '--compile' in sys.argv else '静态'}模式）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
