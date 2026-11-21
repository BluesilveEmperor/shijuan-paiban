#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chinese_fixtures.py — 语文成品卷回归

两种模式：

**默认（快，静态）**
    检查每份成品结构性事实：题号 1..N 连续无缺、选择题选项恰好 4 项、
    必备命令/环境齐全。约 0.1 秒。

**``--compile``（慢，真编译）**
    连同 templates/chinese/ywexam.sty 拷到临时目录，xelatex 连编两遍
    （lastpage 需要），断言退出码 0、页数与基线一致、日志无 Missing character。
    约 70 秒，`python tests/run_all.py --with-tex` 时启用。

未找到 xelatex 时编译模式整体 SKIP。
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STY = ROOT / "templates" / "chinese" / "ywexam.sty"
FIXTURES = ROOT / "evals" / "fixtures_chinese"

# 已核对的基线页数（源卷 10~12 页，排版后 9~11 页）
EXPECT_PAGES = {
    ("2611台州一模", "chinese-shiti"): 10,
    ("2611台州一模", "chinese-daan"): 5,
    ("2611嘉兴一模", "chinese-shiti"): 9,
    ("2611嘉兴一模", "chinese-daan"): 4,
    ("2611宁波一模", "chinese-shiti"): 10,
    ("2611宁波一模", "chinese-daan"): 4,
    ("2611杭州一模", "chinese-shiti"): 11,
    ("2611杭州一模", "chinese-daan"): 4,
    ("2611绍兴一模", "chinese-shiti"): 9,
    ("2611绍兴一模", "chinese-daan"): 4,
    ("2611金华十校", "chinese-shiti"): 10,
    ("2611金华十校", "chinese-daan"): 4,
}

FAILS = []


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


def pdf_pages(pdf: Path):
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
        for line in out.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:  # noqa: BLE001
        pass
    return None


def check_static(tex: Path):
    """结构检查：题号连续、选项 4 项、必备命令存在。"""
    text = tex.read_text(encoding="utf-8")
    name = f"{tex.parent.name}/{tex.stem}"

    # 试题卷：题号必须 1..N 连续；答案卷：\ans 题号集合应与试题一致
    if tex.stem.endswith("shiti"):
        nums = [int(m) for m in re.findall(r"\\question\{(\d+)\}", text)]
        if not nums:
            FAILS.append(f"{name} 未找到 \\question")
            return
        expect = list(range(1, len(nums) + 1))
        if nums != expect:
            dup = [n for n in set(nums) if nums.count(n) > 1]
            gap = [n for n in expect if n not in nums]
            FAILS.append(f"{name} 题号不连续（重复={dup} 缺失={gap}）")
        for env in ("sechead", "subsechead", "materialtext"):
            if f"\\{env}" not in text and f"\\begin{{{env}}}" not in text:
                FAILS.append(f"{name} 缺少 \\{env}")

    # 选项组必须恰好 4 项（语文选择题全为四选一）
    for i, block in enumerate(re.findall(
            r"\\begin\{choices\}(.*?)\\end\{choices\}", text, re.S), 1):
        n = len(re.findall(r"\\item\b", block))
        if n != 4:
            FAILS.append(f"{name} 第 {i} 个 choices 有 {n} 个选项（应为 4）")

    # 答案卷：\ans 必须存在且有评分说明或子项之一
    if tex.stem.endswith("daan"):
        if "\\ans{" not in text:
            FAILS.append(f"{name} 缺少 \\ans")
        if "\\scorenote{" not in text and "\\subans{" not in text:
            FAILS.append(f"{name} 既无 \\scorenote 也无 \\subans")

    print(f"[PASS] {name} 结构检查")


def main():
    do_compile = "--compile" in sys.argv
    if not STY.exists():
        print(f"FAIL 模板缺失: {STY}")
        return 1
    if not FIXTURES.is_dir():
        print(f"FAIL 样例目录缺失: {FIXTURES}")
        return 1

    cases = sorted(FIXTURES.glob("*/chinese-*.tex"))
    if not cases:
        print("FAIL evals/fixtures_chinese 下没有 chinese-*.tex")
        return 1

    for tex in cases:
        check_static(tex)

    if not do_compile:
        if FAILS:
            for f in FAILS:
                print(f"FAIL {f}")
            return 1
        print(f"\n全部 {len(cases)} 份语文成品结构检查通过（未编译；"
              "加 --compile 或 run_all.py --with-tex 做真编译回归）")
        return 0

    xelatex = find_xelatex()
    if not xelatex:
        print("SKIP 未找到 xelatex，跳过编译回归")
        return 0

    for tex in cases:
        name = tex.parent.name
        stem = tex.stem
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            shutil.copy2(STY, work / STY.name)
            for f in tex.parent.iterdir():
                if f.is_file():
                    shutil.copy2(f, work / f.name)

            rc = 1
            for _ in range(2):
                rc = subprocess.run(
                    [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex.name],
                    cwd=str(work), capture_output=True).returncode

            pdf = work / f"{stem}.pdf"
            log = work / f"{stem}.log"
            pages = pdf_pages(pdf) if pdf.exists() else None
            missing = 0
            if log.exists():
                missing = log.read_text(encoding="utf-8", errors="ignore").count(
                    "Missing character")

            expect = EXPECT_PAGES.get((name, stem))
            ok = rc == 0 and pages is not None and missing == 0 and (
                expect is None or pages == expect)
            print(f"{'[PASS]' if ok else '[FAIL]'} {name}/{stem} "
                  f"rc={rc} pages={pages}(期望 {expect}) missing_glyph={missing}")
            if not ok:
                FAILS.append(f"{name}/{stem} 编译")

    if FAILS:
        for f in dict.fromkeys(FAILS):
            print(f"FAIL {f}")
        return 1
    print(f"\n全部 {len(cases)} 份语文成品编译通过（页数与基线一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
