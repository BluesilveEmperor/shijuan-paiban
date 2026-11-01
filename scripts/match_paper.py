#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_paper.py - 答案文档 → 同目录试题 .tex 三段式匹配

阶段一：精确剥离 -答案 / _答案 / 答案 后缀
阶段二：与同目录 .tex 求最长公共前缀（≥ 3 字符）
阶段三：返回 None，由调用方回退到从输入文件重新提取

用法:
  python scripts/match_paper.py "新一卷数学-答案.docx"
  python scripts/match_paper.py "新一卷数学-答案.docx" --json
"""

import argparse
import json
import os
import re
import sys

ANSWER_SUFFIX_PATTERNS = [
    r"-答案$", r"_答案$", r"答案$", r"答案-", r"答案_",
    r"-参考答案$", r"_参考答案$",
]
EXCLUDE_HINTS = ("教师版", "template", "gaokao", "答案")
MIN_PREFIX = 3


def strip_ext(name: str) -> str:
    for ext in (".docx", ".pdf", ".tex", ".md"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def find_matching_tex(input_path: str):
    """返回 (tex路径 或 None, 命中阶段, 说明)"""
    input_dir = os.path.dirname(os.path.abspath(input_path))
    stem = strip_ext(os.path.basename(input_path))

    # ── 阶段一：精确剥离答案后缀 ──
    for pat in ANSWER_SUFFIX_PATTERNS:
        candidate = re.sub(pat, "", stem)
        if candidate == stem:
            continue
        tex_path = os.path.join(input_dir, candidate + ".tex")
        if os.path.exists(tex_path):
            return tex_path, "stage1", f"剥离后缀得到 {candidate}"

    # ── 阶段二：最长公共前缀 ──
    clean_stem = re.sub(r"[-_ ]?参考答案[-_ ]?", "", stem)
    clean_stem = re.sub(r"[-_ ]?答案[-_ ]?", "", clean_stem)

    try:
        tex_files = [
            f for f in os.listdir(input_dir)
            if f.endswith(".tex")
            and not any(h in f for h in EXCLUDE_HINTS)
        ]
    except OSError:
        tex_files = []

    best, best_score = None, 0
    for tf in tex_files:
        other = tf[:-4]
        i = 0
        while i < min(len(clean_stem), len(other)) and clean_stem[i] == other[i]:
            i += 1
        if i > best_score:
            best_score, best = i, tf

    if best and best_score >= MIN_PREFIX:
        return (os.path.join(input_dir, best), "stage2",
                f"公共前缀 {best_score} 字符")

    # ── 阶段三：回退 ──
    return None, "stage3", "未匹配到同目录试题 tex，需从输入文件重新提取"


def main():
    ap = argparse.ArgumentParser(description="答案文档匹配同目录试题 tex")
    ap.add_argument("input", help="答案文档路径（.docx / .pdf）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] 文件不存在: {args.input}", file=sys.stderr)
        return 2

    tex, stage, note = find_matching_tex(args.input)

    if args.json:
        print(json.dumps(
            {"input": args.input, "matched": tex, "stage": stage, "note": note},
            ensure_ascii=False, indent=2,
        ))
    else:
        if tex:
            print(f"[OK] {stage}: {tex}  ({note})")
        else:
            print(f"[FALLBACK] {stage}: {note}")

    return 0 if tex else 1


if __name__ == "__main__":
    sys.exit(main())
