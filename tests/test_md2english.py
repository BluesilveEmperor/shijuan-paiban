#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_md2english.py — OCR Markdown → 英语 IR 解析门禁

三层检查：

  1. 清洗层单元测试：水印（含两种空格形态）、ladnepen、HTML 实体、小节泄漏、引号/标点
  2. 结构解析单元测试：exam_title / notice / part / section / question+choices /
     完形（同行 + 跨行 + 选项被误识为题号）/ 填空（多种下划线 + 裸数字）/ writing
  3. 52 套保真度基线：以成品 tex 的 IR 为监督，锁定核心结构指标下限，
     防止规则迭代导致回归

用法::

    python tests/test_md2english.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))

import english_clean  # noqa: E402
import eval_md2english as EV  # noqa: E402
import md2english as M  # noqa: E402
import tex2english  # noqa: E402

FIX = ROOT / "evals" / "fixtures_english"
FAILS = []


def check(cond: bool, msg: str):
    if not cond:
        FAILS.append(msg)


def test_cleaning():
    st = english_clean.CleaningStats()
    # 水印两种形态（有/无空格）都应整串去除，不留 " English"
    for src in ("微信公众号 IAI English", "微信公众号IAI English", "IAIEnglish"):
        out = english_clean.clean_line("## 第一节" + src, st)
        check("IAI" not in out and "English" not in out and "微信公众号" not in out,
              f"水印未清净: {src!r} -> {out!r}")
    check(st.watermark >= 3, "水印计数未累加")
    # ladnepen
    out = english_clean.clean_line("每小题1.5ladnepen分", st)
    check("ladnepen" not in out, f"ladnepen 未清除: {out!r}")
    # HTML 实体
    out = english_clean.clean_line("Tom &amp; Jerry", st)
    check("&" in out and "amp" not in out, f"HTML 实体未解码: {out!r}")
    # 小节标题正文泄漏
    out = english_clean.clean_line("第一节（共5小题）本题共5小题请作答", st)
    check(out.strip() == "第一节（共5小题）", f"小节泄漏未截断: {out!r}")
    print("[PASS] 清洗层单元测试")


def test_structure():
    md = """\
# 2024 届高三调研测试
# 英语
注意事项：
1. 答题前填写姓名。
2. 考试结束后交回。
第一部分 听力（共两节，满分 30 分）
第一节（共5小题：每小题1.5分，满分7.5分）
1. What are the speakers doing?
A. Discussing at work. B. Talking on phone. C. Driving.
第二部分 阅读理解（共两节，满分50分）
第一节（共15小题：每小题2.5分，满分37.5分）
阅读下列短文，从每题所给的A、B、C和D四个选项中，选出最佳答案。
A
Some passage text here.
21. What is the text about?
A. A story  B. A notice  C. A report  D. An ad
第二节（共10小题；每小题1.5分，满分15分）
阅读下面短文，在空白处填入1个适当的单词。
It happened \\_\\_36\\_\\_ long ago and \\_37\\_ he was there.
Paragraph 1: He started to run. \\_\\_\\_\\_
"""
    ir, report = M.parse_markdown(md, source="unit.md")
    types = [b["type"] for b in ir["blocks"]]

    check(types.count("exam_title") == 1, "exam_title 应为 1")
    check(types.count("notice") == 1, "notice 应为 1")
    check(types.count("part") == 2, f"part 应为 2，实际 {types.count('part')}")
    check(types.count("question") == 2, f"question 应为 2，实际 {types.count('question')}")
    check(types.count("passage_label") == 1, "passage_label 应为 1")
    check(types.count("writing_para") == 1, "writing_para 应为 1")
    check(types.count("writing_lines") == 1, "writing_lines 应为 1")

    # 完形：同行 4 选项 + 跨行选项 + 选项被误识题号
    cloze_md = """\
41.A.friend B.neighbor C.teacher D.classmate
48. A. condition
B. attack
C. impact
D. symptom
2. How did you come?
A. By bus.
3. By taxi.
C. By subway.
"""
    ir2, _ = M.parse_markdown(cloze_md)
    cl = [b for b in ir2["blocks"] if b["type"] == "cloze"]
    nums = sorted(b["number"] for b in cl)
    check(nums == [41, 48], f"完形题号应为 [41,48]，实际 {nums}")
    for b in cl:
        check(len(b["options"]) == 4 and all(b["options"]),
              f"完形第 {b['number']} 题选项不完整: {b['options']}")
    # 被误识题号 "3. By taxi." 应还原为选项，question 只剩 "2. How..."
    q2 = [b["text"] for b in ir2["blocks"] if b["type"] == "question"]
    check(any(t.startswith("2.") for t in q2), "question 2 丢失")
    check(not any("By taxi" in t for t in q2), "误识题号未还原为选项")

    # 裸数字填空（七选五/语法填空 section 上下文）
    bare_md = """\
第二节（共5小题；每小题2.5分，满分12.5分）
Sometimes it can feel cluttered. 36 From focusing to journaling.
Take a walk. 38 When you're mindful.
"""
    ir3, _ = M.parse_markdown(bare_md)
    blanks = ir3["meta"]["blank_numbers"]
    check(36 in blanks and 38 in blanks, f"裸数字填空未识别: {blanks}")
    print("[PASS] 结构解析单元测试")


def test_fidelity_baseline():
    papers = EV.load_papers()
    check(len(papers) == 52, f"样本数应为 52，实际 {len(papers)}")
    score = {}
    keys = ["q", "part", "notice", "passage", "blank", "cloze", "cols"]
    for k in keys:
        score[k] = 0
    for p in papers:
        tex = (FIX / p["tex"]).read_text(encoding="utf-8")
        md = (FIX / p["md"]).read_text(encoding="utf-8")
        d = EV.compare(tex2english.parse_tex(tex), M.parse_markdown(md)[0])
        for k in keys:
            score[k] += int(d[k])
    # 核心结构指标下限（防止规则迭代回归；当前实测值见括号内）
    floor = {"q": 45, "part": 52, "notice": 52, "passage": 50,
             "blank": 42, "cloze": 44, "cols": 30}
    for k in keys:
        check(score[k] >= floor[k],
              f"保真度回归：{k}_exact={score[k]} < 下限 {floor[k]}")
    print(f"[PASS] 52 套保真度基线 {score}")


def main():
    test_cleaning()
    test_structure()
    test_fidelity_baseline()
    if FAILS:
        for f in FAILS:
            print("FAIL", f)
        return 1
    print("md→english IR 解析门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
