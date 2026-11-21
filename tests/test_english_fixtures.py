#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_english_fixtures.py — 英语分支资源回归

静态检查（默认）：52 套 md/tex 齐全、manifest 映射有效、模板快照一致、
答题卡模板路径可解析、tex 环境配对、仓库内无编译产物。
``--compile`` 额外抽样真编译 1 份（需 XeLaTeX；缺失时跳过）。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "evals" / "fixtures_english"
TPL = ROOT / "templates" / "english"
ANSWER_SHEET_SAMPLES = (
    "全国卷英语A4答题卡条形码版/英语答题卡A4条形码版.tex",
    "全国卷英语A4答题卡考生号版/英语答题卡A4考生号版.tex",
)

FAILS = []


def check(cond, label):
    if not cond:
        FAILS.append(f"FAIL {label}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compile", action="store_true", help="抽样真编译 1 份英语 tex")
    args = ap.parse_args()

    # 1. manifest 与 52 套样本
    mf_path = FIX / "manifest.json"
    if not mf_path.is_file():
        print("FAIL manifest.json 不存在")
        return 1
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    papers = mf.get("papers", [])
    check(mf.get("subject") == "english", "manifest.subject=english")
    check(len(papers) == 52, "manifest 卷数=52")
    check([p["index"] for p in papers] == list(range(1, 53)), "编号 1..52 连续")
    check(len(list((FIX / "md").glob("*.md"))) == 52, "md 份数=52")
    check(len(list((FIX / "tex").glob("*.tex"))) == 52, "tex 份数=52")

    env_re = {e: (re.compile(r"\\begin\{" + e + r"\}"),
                   re.compile(r"\\end\{" + e + r"\}"))
              for e in ("document", "choices", "cloze", "notice", "tabular")}
    for p in papers:
        idx = p.get("index")
        md = FIX / p["md"]
        tex = FIX / p["tex"]
        check(md.is_file(), f"#{idx} md 存在: {p['md']}")
        check(tex.is_file(), f"#{idx} tex 存在: {p['tex']}")
        check(bool(p.get("source_dir")) and bool(p.get("source_pdf")),
              f"#{idx} 原卷 PDF 映射完整")
        if not tex.is_file():
            continue
        text = tex.read_text(encoding="utf-8")
        check(r"\documentclass{英语试卷}" in text
              or r"\documentclass[answers]{英语试卷}" in text,
              f"#{idx} 使用英语文档类")
        for env, (beg, end) in env_re.items():
            check(len(beg.findall(text)) == len(end.findall(text)),
                  f"#{idx} {env} 环境配对")

    # 2. 不入库编译产物
    artifacts = [p for p in FIX.rglob("*")
                 if p.is_file() and (p.suffix.lower() in
                 {".pdf", ".aux", ".log", ".out", ".toc"}
                 or p.name.lower().endswith(".synctex.gz"))]
    check(not artifacts, "fixtures 内无编译产物: " +
          ", ".join(str(p.relative_to(FIX)) for p in artifacts[:3]))

    # 3. 模板与样本快照一致
    for name in ("英语试卷.cls", "英语试卷.sty"):
        src = TPL / name
        snap = FIX / "tex" / name
        check(src.is_file() and snap.is_file(), f"模板 {name} 存在")
        if src.is_file() and snap.is_file():
            check(src.read_bytes() == snap.read_bytes(), f"模板快照一致: {name}")

    # 4. 答题卡模板：样例 tex 里的 ../英语答题卡.sty 必须可解析
    sheet_dir = TPL / "answer-sheet"
    check((sheet_dir / "英语答题卡.sty").is_file(), "英语答题卡.sty 存在")
    for rel in ANSWER_SHEET_SAMPLES:
        sample = sheet_dir / rel
        check(sample.is_file(), f"答题卡样例存在: {rel}")
        if sample.is_file():
            check((sample.parent.parent / "英语答题卡.sty").is_file(),
                  f"答题卡 ../sty 可解析: {rel}")

    # 5. 模板清单已注册英语
    tpl_mf = json.loads((ROOT / "templates" / "manifest.json").read_text(encoding="utf-8"))
    check(tpl_mf.get("layout", {}).get("english") == "english/", "layout.english 已注册")
    check(tpl_mf.get("templates", {}).get("english", {}).get("subject") == "english",
          "templates.english 已注册")

    # 6. 抽样真编译
    if args.compile:
        xelatex = shutil.which("xelatex")
        if not xelatex:
            print("[SKIP] 未安装 XeLaTeX，跳过英语样本编译")
        else:
            sample = FIX / papers[0]["tex"]
            with tempfile.TemporaryDirectory(prefix="eng-fixture-") as td:
                work = Path(td)
                for name in ("英语试卷.cls", "英语试卷.sty"):
                    shutil.copy2(TPL / name, work / name)
                shutil.copy2(sample, work / sample.name)
                for _ in range(2):
                    run = subprocess.run(
                        [xelatex, "-interaction=nonstopmode", sample.name],
                        cwd=str(work), capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
                    if run.returncode != 0:
                        tail = "\n".join((run.stdout or "").splitlines()[-12:])
                        check(False, f"抽样编译失败 {sample.name}: {tail}")
                        break
                check((work / (sample.stem + ".pdf")).is_file(),
                      f"抽样编译产出 PDF: {sample.stem}.pdf")

    if FAILS:
        for f in FAILS:
            print(f)
        print(f"test_english_fixtures: {len(FAILS)} failed")
        return 1
    print("test_english_fixtures: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
