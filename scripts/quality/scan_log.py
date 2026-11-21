#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_log.py — 编译日志体检：缺字形 / 溢出 / 报错 / 未解析引用

xelatex 的很多问题**不会**让编译失败，只是静默丢字或撑破版心：

    Missing character: There is no 郤 (U+90E5) in font ...
    Overfull \\hbox (12.3pt too wide) in paragraph at lines 210--212
    LaTeX Warning: Reference `LastPage' on page 1 undefined

语文卷尤其常见：楷体/西文字体缺字形时字直接消失，肉眼要逐字核对才能发现。
本脚本把 .log 里的这类行汇总成表，一次看全。

用法::

    python scripts/quality/scan_log.py 语文试题卷.log
    python scripts/quality/scan_log.py .                  # 扫目录下所有 .log
    python scripts/quality/scan_log.py a.log --json       # 机器可读
    python scripts/quality/scan_log.py a.log --fail-on missing   # 有缺字形则退出码 1

退出码：0 无 error 级问题；1 有 `!` 错误或缺字形（仅 --fail-on 指定时）；2 文件不存在
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # ACCESS-001

RE_MISSING = re.compile(r"Missing character: There is no (.+?) (\(U\+[0-9A-Fa-f]+\))? in font")
RE_OVERFULL = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\)(?:.*?)(?:at lines? (\d+)(?:--(\d+))?)?")
RE_UNDERFULL = re.compile(r"Underfull \\vbox")
RE_ERROR = re.compile(r"^! (.+)$")
RE_UNDEF_REF = re.compile(r"Reference `([^']+)' on page (\d+) undefined")
RE_FONT_WARN = re.compile(r"Could not resolve font \"([^\"]+)\"")


def scan_one(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    res = {
        "log": str(path),
        "missing": {},
        "overfull": [],
        "errors": [],
        "undefined_refs": [],
        "font_warns": [],
        "underfull": 0,
    }
    for ln in text.splitlines():
        m = RE_MISSING.search(ln)
        if m:
            key = m.group(1).strip()
            res["missing"][key] = res["missing"].get(key, 0) + 1
            continue
        m = RE_OVERFULL.search(ln)
        if m:
            res["overfull"].append({"pt": float(m.group(1)),
                                    "lines": [m.group(2), m.group(3)]})
            continue
        if RE_UNDERFULL.search(ln):
            res["underfull"] += 1
            continue
        m = RE_ERROR.match(ln)
        if m:
            res["errors"].append(m.group(1).strip())
            continue
        m = RE_UNDEF_REF.search(ln)
        if m:
            res["undefined_refs"].append({"ref": m.group(1), "page": m.group(2)})
            continue
        m = RE_FONT_WARN.search(ln)
        if m:
            res["font_warns"].append(m.group(1))
    return res


def report(res, verbose=True):
    ok = True
    name = Path(res["log"]).name
    print(f"=== {name} ===")

    if res["missing"]:
        ok = False
        chars = "、".join(f"{c}×{n}" if n > 1 else c for c, n in res["missing"].items())
        print(f"[FAIL] 缺字形 {len(res['missing'])} 种（字会直接消失）：{chars}")
        print("       处置：换覆盖更全的字体（ywexam 已按 SimSun→Noto Serif CJK SC 回退），"
              "或单字用 \\fullglyph{字}")
    if res["errors"]:
        ok = False
        print(f"[FAIL] 报错 {len(res['errors'])} 条：")
        for e in res["errors"][:5]:
            print(f"       ! {e}")
    if res["overfull"]:
        worst = max(res["overfull"], key=lambda x: x["pt"])
        print(f"[WARN] Overfull \\hbox {len(res['overfull'])} 处，最宽 {worst['pt']}pt"
              f"（行 {worst['lines'][0]}）")
        print("       处置：选项改 2 列 / 图缩宽 / \\dfrac 改 \\frac")
    if res["undefined_refs"]:
        refs = {r["ref"] for r in res["undefined_refs"]}
        print(f"[WARN] 未解析引用：{'、'.join(sorted(refs))}（连编两次即可消除）")
    if res["font_warns"]:
        uniq = sorted(set(res["font_warns"]))
        print(f"[INFO] 字体缺字重：{'、'.join(uniq[:4])}" +
              ("…" if len(uniq) > 4 else "") + "（通常只是斜体/粗体回退，可忽略）")
    if res["underfull"]:
        print(f"[INFO] Underfull \\vbox {res['underfull']} 处（多为分页拉伸，一般不影响）")

    if not any((res["missing"], res["errors"], res["overfull"],
                res["undefined_refs"])):
        print("[OK] 无缺字形 / 报错 / 溢出")
    if verbose:
        print()
    return ok


def main():
    ap = argparse.ArgumentParser(description="xelatex 日志体检（缺字形/溢出/报错）")
    ap.add_argument("log", help=".log 文件或目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--fail-on", choices=["none", "missing", "error"],
                    default="none",
                    help="none（默认，恒 0）| missing（有缺字形则 1）| error（有 ! 或缺字形则 1）")
    args = ap.parse_args()

    p = Path(args.log)
    if not p.exists():
        print(f"[ERROR] 找不到 {p}", file=sys.stderr)
        return 2
    logs = sorted(p.glob("*.log")) if p.is_dir() else [p]
    if not logs:
        print(f"[ERROR] {p} 下没有 .log", file=sys.stderr)
        return 2

    results = [scan_one(x) for x in logs]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            report(r)

    if args.fail_on == "missing" and any(r["missing"] for r in results):
        return 1
    if args.fail_on == "error" and any(r["missing"] or r["errors"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
