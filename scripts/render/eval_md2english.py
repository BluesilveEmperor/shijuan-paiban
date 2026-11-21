#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""eval_md2english.py — 用 52 套成品 tex 的 IR 评估 md→IR 保真度

以 ``tex2english.parse_tex`` 的输出为监督目标，对 ``md2english.parse_markdown``
的结果逐套比对结构化指标；可用 ``--detail N`` 打印单卷差异明细。

指标：

    q_exact       题号序列（question_numbers）完全一致的卷数
    blank_exact   \blanknum 号集合完全一致的卷数
    cloze_exact   \cz 完形题号集合完全一致的卷数
    part_exact    part 块文本序列完全一致
    section_exact section 块文本序列完全一致
    notice_exact  notice 块数量一致
    passage_exact passage_label 序列一致
    cols_exact    choices 列数序列一致
    block_exact   块总数一致

用法::

    python scripts/render/eval_md2english.py
    python scripts/render/eval_md2english.py --detail 1
    python scripts/render/eval_md2english.py --detail 9 --show-lines
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from md2english import parse_markdown  # noqa: E402
from tex2english import parse_tex  # noqa: E402

FIX = ROOT / "evals" / "fixtures_english"


def seq(blocks: list, typ: str, key: str = "text") -> list:
    return [b[key] for b in blocks if b["type"] == typ]


def cols(blocks: list) -> list:
    return [b["columns"] for b in blocks if b["type"] == "choices"]


def load_papers() -> list:
    manifest = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
    return manifest["papers"]


def compare(ref: dict, got: dict) -> dict:
    rb, gb = ref["blocks"], got["blocks"]
    rmg, gmg = ref["meta"], got["meta"]
    return {
        "q": (rmg["question_numbers"] == gmg["question_numbers"]),
        "blank": (rmg["blank_numbers"] == gmg["blank_numbers"]),
        "cloze": (sorted(b["number"] for b in rb if b["type"] == "cloze") ==
                  sorted(b["number"] for b in gb if b["type"] == "cloze")),
        "part": (seq(rb, "part") == seq(gb, "part")),
        "section": (seq(rb, "section") == seq(gb, "section")),
        "notice": (sum(b["type"] == "notice" for b in rb) ==
                   sum(b["type"] == "notice" for b in gb)),
        "passage": (seq(rb, "passage_label") == seq(gb, "passage_label")),
        "cols": (cols(rb) == cols(gb)),
        "blocks": (len(rb) == len(gb)),
        "r_q": rmg["question_numbers"], "g_q": gmg["question_numbers"],
        "r_blank": rmg["blank_numbers"], "g_blank": gmg["blank_numbers"],
        "r_cloze": sorted(b["number"] for b in rb if b["type"] == "cloze"),
        "g_cloze": sorted(b["number"] for b in gb if b["type"] == "cloze"),
        "r_part": seq(rb, "part"), "g_part": seq(gb, "part"),
        "r_section": seq(rb, "section"), "g_section": seq(gb, "section"),
        "r_notice": sum(b["type"] == "notice" for b in rb),
        "g_notice": sum(b["type"] == "notice" for b in gb),
        "r_passage": seq(rb, "passage_label"), "g_passage": seq(gb, "passage_label"),
        "r_cols": cols(rb), "g_cols": cols(gb),
        "r_blocks": len(rb), "g_blocks": len(gb),
    }


def detail_line(idx: int, exam: str, d: dict) -> str:
    lines = [f"=== {idx:02d} {exam} ==="]
    if not d["q"]:
        lines.append(f"  题号 ref({len(d['r_q'])}): {d['r_q']}")
        lines.append(f"       got({len(d['g_q'])}): {d['g_q']}")
    if not d["blank"]:
        lines.append(f"  填空 ref: {d['r_blank']}")
        lines.append(f"       got: {d['g_blank']}")
    if not d["cloze"]:
        lines.append(f"  完形 ref: {d['r_cloze']}")
        lines.append(f"       got: {d['g_cloze']}")
    if not d["part"]:
        lines.append(f"  part ref: {d['r_part']}")
        lines.append(f"       got: {d['g_part']}")
    if not d["section"]:
        lines.append(f"  section ref: {d['r_section']}")
        lines.append(f"       got: {d['g_section']}")
    if not d["notice"]:
        lines.append(f"  notice ref/got: {d['r_notice']}/{d['g_notice']}")
    if not d["passage"]:
        lines.append(f"  passage ref: {d['r_passage']}")
        lines.append(f"          got: {d['g_passage']}")
    if not d["cols"]:
        lines.append(f"  cols ref: {d['r_cols']}")
        lines.append(f"       got: {d['g_cols']}")
    if not d["blocks"]:
        lines.append(f"  blocks ref/got: {d['r_blocks']}/{d['g_blocks']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detail", type=int, action="append", default=[],
                    help="打印指定卷号（1-52）的详细差异，可重复")
    ap.add_argument("--show-lines", action="store_true",
                    help="配合 --detail 打印源 md 的相关行（完形/填空/注意事项）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 汇总")
    args = ap.parse_args()

    papers = load_papers()
    keys = ["q", "blank", "cloze", "part", "section", "notice",
            "passage", "cols", "blocks"]
    score = {k: 0 for k in keys}
    details = {}
    for p in papers:
        tex = (FIX / p["tex"]).read_text(encoding="utf-8")
        md = (FIX / p["md"]).read_text(encoding="utf-8")
        ref = parse_tex(tex, source=p["tex"])
        got, _ = parse_markdown(md, source=p["md"])
        d = compare(ref, got)
        for k in keys:
            score[k] += int(d[k])
        details[p["index"]] = d

    total = len(papers)
    summary = {"papers": total}
    for k in keys:
        summary[f"{k}_exact"] = score[k]
    summary["q_ref"] = sum(len(details[p["index"]]["r_q"]) for p in papers)
    summary["q_got"] = sum(len(details[p["index"]]["g_q"]) for p in papers)
    summary["blocks_ref"] = sum(details[p["index"]]["r_blocks"] for p in papers)
    summary["blocks_got"] = sum(details[p["index"]]["g_blocks"] for p in papers)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(summary)

    for idx in args.detail:
        p = next((x for x in papers if x["index"] == idx), None)
        if not p:
            print(f"[WARN] 无卷号 {idx}")
            continue
        print(detail_line(idx, p["exam"], details[idx]))
        if args.show_lines:
            md_lines = (FIX / p["md"]).read_text(encoding="utf-8").splitlines()
            for n, ln in enumerate(md_lines, 1):
                if any(tok in ln for tok in ("注意事项", "blank", "\\_", "A.", "A．")):
                    if re_short(ln):
                        print(f"  {n}: {ln.strip()[:180]}")
    return 0


def re_short(ln: str) -> bool:
    """只打印较短的关键行，避免整段正文刷屏。"""
    return len(ln.strip()) < 160


if __name__ == "__main__":
    sys.exit(main())
