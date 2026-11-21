#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_english_corpus_rules.py — 英语 52 套样本沉淀规则的回归门禁

复用 scripts/ops/analyze_english_corpus.py 的解析与不变量检查：
结构不变量必须全过；汇总数据与 docs/english-corpus-findings.md 的记录保持一致。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "ops"))

import analyze_english_corpus as corpus  # noqa: E402

FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}: expected {expected!r}, actual {actual!r}")


# 与 docs/english-corpus-findings.md 第 6.2 节一致的硬异常集合
HARD_FLAGS = {
    "image_loss", "watermark_leaked_into_sectitle", "garbage_token_in_sectitle",
    "body_text_leaked_into_sectitle", "notice_missing", "blanknum_missing",
    "blanknum_duplicate", "cloze_rows_short", "choices_count_drift",
    "writinglines_anomaly", "page_count_unavailable", "unknown_parttitle",
}


def main():
    papers = corpus.load_papers()
    for fail in corpus.check_invariants(papers):
        FAILS.append("FAIL 不变量: " + fail)

    data = corpus.aggregate(papers)
    s = data["summary"]
    eq(len(papers), 52, "样本数")
    eq(s["variants"], {"full": 47, "no_listening": 5}, "卷式分布")
    eq(s["blanknum_full_coverage"], 28, "填空完整覆盖卷数")
    eq(len(s["md_image_papers"]), 3, "图片丢失卷数")
    eq(s["md_images_total"], 7, "源 md 图片处数")
    eq(len(s["watermark_papers"]), 16, "水印污染卷数")
    eq(len(s["garbage_token_papers"]), 5, "垃圾串污染卷数")
    eq(len(s["report_pages_zero"]), 22, "报告页数为 0 的卷数")
    eq(len(data["rules"]), 16, "EC 规则条数")
    eq([r["id"] for r in data["rules"]],
       [f"EC-{i:03d}" for i in range(1, 17)], "EC 规则编号连续")
    eq(s["example_papers"], [2, 9, 20, 21, 24, 27], "听力例题卷")

    clean = [p["index"] for p in papers if not (set(p["flags"]) & HARD_FLAGS)]
    eq(clean, [1, 11, 13, 15, 29], "A 层干净基准卷")

    if FAILS:
        for f in FAILS:
            print(f)
        print(f"test_english_corpus_rules: {len(FAILS)} failed")
        return 1
    print("test_english_corpus_rules: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
