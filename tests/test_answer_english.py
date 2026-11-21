#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_answer_english.py — 英语答案卷解析 + 批量流水线逻辑门禁

三层检查：

  1. 答案解析器单测：卷头 / 答案组（含 part 行内嵌）/ 语法填空（多词）/
     写作范文 / 听力原文 / 水印清洗 / 不截断小节标题
  2. 渲染器答案块单测：answer_title / answers / blank_answers / writing_sample → tex
  3. 批量流水线纯逻辑：manifest 映射、产物命名、缓存路径、--dry-run 不跑 OCR

不跑真实 OCR / 编译（那由 batch_english.py 的真实运行与 --with-tex 覆盖）。

用法::

    python tests/test_answer_english.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))

import batch_english as B  # noqa: E402
import md2english_answer as MA  # noqa: E402
import render_english as RE  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def test_answer_parser():
    md = """\
# 武汉市2024届高中毕业生二月调研考试
# 英语参考答案
第一部分 听力（共两节，满分30分）
第一节 1-5 BBACC
第二节 6-10 CAABB 11-15 CBACA 16-20 ABBCA
## 第二部分 阅读理解（共两节，满分50分）
第一节（共15小题；每小题2.5分）21-23 DBC 24-27 AABB
第二节（共5小题；每小题2.5分）36-40 BEGDA
## 第三部分 语言知识运用
第一节（共15小题；每小题1分）41-45 BAACB 46-50 DACAD 51-55 CDBCA
第二节：56. for 57. but/yet/while 58. to host
## 第四部分 写作（共两节，满分40分）
## 第一节 (满分 15 分)
Dear Li Hua,
I hope this message finds you well.
Yours,
Li Hua
## 第二节 (满分25分)
Paragraph 1: He began to worry.
Paragraph 2: They crossed the line.
"""
    ir, report = MA.parse_answer_markdown(md, source="unit.md")
    m = ir["meta"]
    check(m["kind"] == "daan", f"kind 应为 daan: {m['kind']}")
    check(m["title"] == "武汉市2024届高中毕业生二月调研考试",
          f"title 错误: {m['title']}")
    check(m["exam_subject"] == "英语", "exam_subject 应为 英语")
    check(any(b["type"] == "answer_title" for b in ir["blocks"]), "缺 answer_title 块")
    check(m["answer_groups"] == 10, f"答案组应为 10，实际 {m['answer_groups']}")
    # 3.1 解析多词答案：56 for / 57 but/yet/while / 58 to host
    blanks = {n: a for b in ir["blocks"] if b["type"] == "blank_answers"
              for n, a in b["items"]}
    check(blanks.get(58) == "to host", f"多词答案 58 错误: {blanks.get(58)}")
    check(blanks.get(57) == "but/yet/while", f"斜杠答案 57 错误: {blanks.get(57)}")
    check(set(blanks) == {56, 57, 58}, f"语法填空号错误: {set(blanks)}")
    # 3.2 写作范文 2 篇
    samples = [b for b in ir["blocks"] if b["type"] == "writing_sample"]
    check(len(samples) == 2, f"范文应为 2 篇，实际 {len(samples)}")
    check(samples and samples[0]["title"] == "第一节", "范文标题错误")
    check(samples and len(samples[0]["paragraphs"]) >= 3, "范文段落数不足")
    # 3.3 答案组覆盖听力/阅读/七选五/完形
    groups = [g for b in ir["blocks"] if b["type"] == "answers" for g in b["groups"]]
    ranges = [(g[0], g[1]) for g in groups]
    check((1, 5) in ranges and (36, 40) in ranges and (51, 55) in ranges,
          f"答案组区间不全: {ranges}")
    # 3.4 小节标题不带答案组
    secs = [b["text"] for b in ir["blocks"] if b["type"] == "section"]
    check(not any("21-23" in s for s in secs), f"section 混入答案组: {secs}")
    # 3.5 水印清洗（答案卷不能截断小节标题后的答案组）
    md2 = "第一节（共5小题）微信公众号IAI English 36-40 CDABF\n"
    ir2, _ = MA.parse_answer_markdown(md2)
    check(not any("IAI" in json.dumps(b, ensure_ascii=False) for b in ir2["blocks"]),
          "水印未清净")
    check(any(b["type"] == "answers" and [tuple(g) for g in b["groups"]] == [(36, 40, "CDABF")]
              for b in ir2["blocks"]), "cut_section=False 未保留小节后答案组")
    # 3.6 `\~` 转义波浪号分隔符（2412 3+3+3 卷实际格式）与无空格答案串
    md3 = ("# 某联考 英语参考答案\n"
           "1\\~5 BACAA 6\\~10 ABCBC\n"
           "第一节（共15小题）41\\~45BCABC 46\\~50CBDDA\n")
    ir3, _ = MA.parse_answer_markdown(md3)
    check(ir3["meta"]["title"] == "某联考", f"合并 H1 剥后缀失败: {ir3['meta']['title']}")
    groups3 = [tuple(g) for b in ir3["blocks"] if b["type"] == "answers" for g in b["groups"]]
    check((1, 5, "BACAA") in groups3 and (41, 45, "BCABC") in groups3,
          f"\\~ 分隔答案组未识别: {groups3}")
    # 3.7 逐题详解行：答案本体截取；被答案组覆盖的题号不产假填空；
    #     无答案组覆盖的详解单字母保留（2412皖南八校语义）
    md4 = ("# 测试卷 英语参考答案\n"
           "第一节 36-40 FEAGC\n"
           "第二节：56. which 考查定语从句。先行词为 the one，故填 which。\n"
           "36. F 上下文推断题。根据上文可知，本段讲的是寻求帮助。\n")
    ir4, _ = MA.parse_answer_markdown(md4)
    blanks4 = [n for b in ir4["blocks"] if b["type"] == "blank_answers" for n, _ in b["items"]]
    check(blanks4 == [56], f"答案组覆盖后详解 36 不得产假填空、56 只一次: {blanks4}")
    b56 = {n: a for b in ir4["blocks"] if b["type"] == "blank_answers" for n, a in b["items"]}
    check(b56.get(56) == "which", f"详解行答案本体截取错误: {b56.get(56)}")
    # 3.8 详解单字母在无答案组覆盖时保留为填空（皖南八校阅读答案仅有详解）
    md5 = ("# 卷五\n"
           "21. A 细节理解题。根据第二段可知，游客可以欣赏壁画。\n"
           "22. D 推理判断题。根据最后一段可知，作者持乐观态度。\n")
    ir5, _ = MA.parse_answer_markdown(md5)
    d5 = {n: a for b in ir5["blocks"] if b["type"] == "blank_answers" for n, a in b["items"]}
    check(d5.get(21) == "A" and d5.get(22) == "D",
          f"无覆盖详解单字母应保留: {d5}")
    # 3.9 听力原文区（Text N）在答案区标题处结束，不吞答案区
    md6 = ("# 卷六\n"
           "## Text 1\n"
           "M: Hello.\n"
           "W: Hi.\n"
           "## 参考答案\n"
           "第一节 1-5 BCCBB\n")
    ir6, _ = MA.parse_answer_markdown(md6)
    check(any(b["type"] == "answers" and [tuple(g) for g in b["groups"]] == [(1, 5, "BCCBB")]
              for b in ir6["blocks"]),
          f"听力原文后答案区被吞: {[b['type'] for b in ir6['blocks']]}")
    # 3.10 表格答案：序号/答案行（南昌）与「21 A」单元格（佛山）
    md7 = ("# 卷七\n"
           "<table><tr><td>序号</td><td>1</td><td>2</td></tr>"
           "<tr><td>答案</td><td>C</td><td>B</td></tr></table>\n"
           "<table><tr><td>21 A</td><td>22 D</td></tr></table>\n"
           "第二节：（共10小题）56 offers 57 which 58 visiting 59 with 60 is\n"
           "  reflected 61 entrance/entry 62 a 63 streets 64 vividly 65 To\n")
    ir7, _ = MA.parse_answer_markdown(md7)
    d7 = {n: a for b in ir7["blocks"] if b["type"] == "blank_answers" for n, a in b["items"]}
    check(d7.get(1) == "C" and d7.get(2) == "B", f"序号/答案表格未提取: {d7}")
    check(d7.get(21) == "A" and d7.get(22) == "D", f"单元格表格未提取: {d7}")
    check(d7.get(56) == "offers" and d7.get(61) == "entrance/entry",
          f"无点号多词答案未提取: {d7.get(56)}, {d7.get(61)}")
    print("[PASS] 答案解析器单测")


def test_answer_render():
    ir, _ = MA.parse_answer_markdown("""\
# 测试卷
# 英语参考答案
第一部分 听力
第一节 1-5 BBACC
第二节：56. for 57. to host
""")
    tex, report = RE.render_paper(ir)
    check("\\documentclass[answers]{英语试卷}" in tex, "未启用 [answers] 文档类")
    check("\\answerline{1-5 BBACC}" in tex, "答案行渲染缺失")
    check("\\blankanswer{57}{to host}" in tex, "多词语法填空渲染缺失")
    check(not any("question" in w for w in report.warnings),
          f"答案卷不应告警缺 question: {report.warnings}")
    print("[PASS] 答案块渲染单测")


def test_batch_logic():
    papers = B.load_papers()
    check(len(papers) == 52, f"样本数应为 52，实际 {len(papers)}")
    check(B.out_stem("shiti", "测试") == "英语卷-测试", "试题产物命名错误")
    check(B.out_stem("answer", "测试") == "英语答案-测试", "答案产物命名错误")
    # 映射完整性：51 套有答案 PDF，试题 PDF 全有
    check(all(p.get("source_pdf") for p in papers), "有卷缺 source_pdf")
    check(sum(1 for p in papers if p.get("source_answer_pdf")) == 51,
          "答案 PDF 映射卷数应为 51")
    # dry-run 不跑 OCR：用 01 卷、both
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ops" / "batch_english.py"),
         "--dry-run", "--only", papers[0]["exam"], "--kind", "both"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    check(proc.returncode == 0, f"dry-run 失败: {proc.stderr[:300]}")
    check("英语卷-" not in (proc.stdout or "") or "[shiti]" in proc.stdout,
          "dry-run 未列试题计划")
    check("[answer]" in (proc.stdout or ""), "dry-run 未列答案计划")
    print("[PASS] 批量流水线逻辑单测")


def main():
    test_answer_parser()
    test_answer_render()
    test_batch_logic()
    if FAILS:
        for f in FAILS:
            print("FAIL", f)
        return 1
    print("英语答案卷 + 批量流水线门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
