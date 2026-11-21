#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chinese_ir_fixes.py — 2026-11 无锡卷复盘补丁的回归

覆盖四组：
  1. render_chinese：choices_layout=inline / figure 块 / subans 多行 /
     meta.linespread / 题干后内容块的 [HINT]
  2. md2chinese：HTML 标签、罗马数字、23（60分）、EF 11. 挤行、
     短选项 inline、题干后 space 自动删、卷首重复行
  3. ywexam.sty：字体回退链 / choicesinline / \\answertitle 空副标题 / \\fullglyph
  4. scan_log：缺字形 / 溢出 / 报错解析

全部为静态断言，不需要 xelatex。
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))
sys.path.insert(0, str(ROOT / "scripts" / "quality"))

import md2chinese          # noqa: E402
import render_chinese      # noqa: E402
import scan_log            # noqa: E402

STY = ROOT / "templates" / "chinese" / "ywexam.sty"

FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}\n  expected={expected!r}\n  actual  ={actual!r}")


def has(haystack, needle, label):
    if needle not in haystack:
        FAILS.append(f"FAIL {label}: 缺少 {needle!r}")


# ── 1. render_chinese ────────────────────────────────────────

def test_inline_choices():
    r = render_chinese.RenderReport()
    q = {"type": "question", "no": 18, "stem": "（3分）",
         "options": ["究竟", "判官", "郑重", "忧郁"],
         "choices_layout": "inline"}
    tex = render_chinese.render_block(q, r)
    has(tex, "\\begin{choicesinline}", "inline 选项环境")
    has(tex, "\\task 究竟", "inline 用 \\task")
    has(tex, "\\end{choicesinline}", "inline 环境闭合")
    if "\\item" in tex:
        FAILS.append("FAIL inline 选项不应使用 \\item（tasks 只认 \\task）")

    # 默认仍走纵排（回归基准 6 套成品不能变）
    q2 = dict(q)
    q2.pop("choices_layout")
    tex2 = render_chinese.render_block(q2, r)
    has(tex2, "\\begin{choices}", "默认纵排")
    has(tex2, "\\item 究竟", "纵排用 \\item")

    # auto：短选项横排、长句纵排
    q3 = dict(q, choices_layout="auto")
    has(render_chinese.render_block(q3, r), "choicesinline", "auto 短选项横排")
    q4 = dict(q, choices_layout="auto",
              options=["第一项非常长的选项文本内容", "第二项非常长的选项文本",
                       "第三项非常长的选项文本", "第四项非常长的选项文本"])
    has(render_chinese.render_block(q4, r), "\\begin{choices}", "auto 长选项纵排")


def test_figure_block():
    b = {"type": "figure", "path": "map.png", "width": "0.44",
         "caption": "（第1题图）", "keep": True}
    tex = render_chinese.render_block(b, render_chinese.RenderReport())
    has(tex, "\\includegraphics[width=0.44\\linewidth]{map.png}", "figure 宽度补 linewidth")
    has(tex, "\\nopagebreak[4]", "figure keep")
    has(tex, "（第1题图）", "figure 图注")

    b2 = {"type": "figure", "path": "a.png"}            # 默认 0.5
    has(render_chinese.render_block(b2, render_chinese.RenderReport()),
        "width=0.5\\linewidth", "figure 默认宽度")
    b3 = {"type": "figure", "path": "a.png", "width": "8cm"}
    has(render_chinese.render_block(b3, render_chinese.RenderReport()),
        "width=8cm", "figure 显式尺寸")


def test_subans_multiline():
    b = {"type": "subans", "label": "", "text": ["示例一：风急天高", "示例二：月落乌啼"]}
    tex = render_chinese.render_block(b, render_chinese.RenderReport())
    eq(tex.count("\\subans{"), 2, "subans 列表拆两行")
    has(tex, "示例二：月落乌啼", "subans 第二行内容")

    # 字符串仍是单条
    b2 = {"type": "subans", "label": "（2）", "text": "示例：……"}
    eq(render_chinese.render_block(b2, render_chinese.RenderReport()),
       "\\subans{（2）}{示例：……}", "subans 单条不拆")


def test_linespread_and_hint():
    ir = {"meta": {"title": "T", "kind": "shiti", "linespread": 1.35},
          "blocks": [{"type": "question", "no": 1, "stem": "题干", "space": True},
                     {"type": "para", "text": "作文材料"}]}
    tex, rep = render_chinese.render_paper(ir)
    has(tex, "\\ywlinespread{1.35}", "meta.linespread")
    if not any("第 1 题" in h and "space" in h for h in rep.hints):
        FAILS.append(f"FAIL 题干后内容块未给 HINT，hints={rep.hints}")

    # keep_space=true 时不提示
    ir["blocks"][0]["keep_space"] = True
    _tex, rep2 = render_chinese.render_paper(ir)
    if any("第 1 题" in h for h in rep2.hints):
        FAILS.append("FAIL keep_space=true 仍给 HINT")


# ── 2. md2chinese ────────────────────────────────────────────

OCR_MD = """# 无锡2026-2027学年上学期高三期中考试语文试卷

语 文

2026.11

## 一、现代文阅读（35分）

1. 下列对材料相关内容的理解和分析，不正确的一项是（3分）

A. 材料一认为二者并非简单的替代关系

B. 材料二强调技术演进的连续性

C. 两则材料都否定了“共同激发”的说法

D. 材料一侧重于概念辨析

18. 依次填入横线处的词语，最恰当的一项是（3分）

A. 究竟

B. 判官

C. 郑重

D. 忧郁

9. 请在横线处补写恰当的语句（4分）

语句<sup>①</sup>：Ⅰ级响应是什么意思？

11. 材料中说"…EF 12. 下列对加点词语的解释，不正确的一项是（3分）

A. 甲

B. 乙

C. 丙

D. 丁

23（60分）
"""


def test_md2chinese():
    ir = md2chinese.convert(OCR_MD, "shiti")
    blocks = ir["blocks"]
    kinds = [b["type"] for b in blocks]

    # 卷首「语 文 / 2026.11」去重
    eq(kinds[0], "sechead", "卷首栏目行已去重")

    by_no = {b["no"]: b for b in blocks if b["type"] == "question"}

    # 短选项（1~3 字）→ inline；长选项（4 字以上）→ 未标记
    eq(by_no[18].get("choices_layout"), "inline", "短选项内联")
    eq("choices_layout" in by_no[1], False, "长选项不内联")

    # <sup> 标签 → \xq{}；罗马数字 → ASCII
    joined = json.dumps(blocks, ensure_ascii=False)
    if "<sup>" in joined:
        FAILS.append("FAIL HTML <sup> 未清除")
    has(joined, "\\xq{1}", "sup ① 转 \\xq")
    has(joined, "I级响应", "罗马数字 Ⅰ → I")

    # EF 11. 挤行 → 拆出第 12 题
    if 12 not in by_no:
        FAILS.append(f"FAIL 断句串后题号未拆开，题号={sorted(by_no)}")

    # 23（60分）无点号题号
    if 23 not in by_no:
        FAILS.append(f"FAIL 23（60分）未识别，题号={sorted(by_no)}")

    # 题干后紧跟 para 的主观题不留空白
    q9 = by_no.get(9)
    if q9 is None or q9.get("space"):
        FAILS.append(f"FAIL 第 9 题 space 未删除：{q9}")

    # 无选项、无小问但**后面没有内容块**的题仍保留 space
    if not by_no[23].get("space"):
        FAILS.append("FAIL 第 23 题（末题）space 不应删除")


def test_md2chinese_answer():
    md = "23（60分）\n\n参考例文：……\n"
    ir = md2chinese.convert(md, "daan")
    nos = [b["no"] for b in ir["blocks"] if b["type"] == "ans"]
    if 23 not in nos:
        FAILS.append(f"FAIL 答案卷 23（60分）未识别，nos={nos}")


# 真实语料（Z20 / 佛山二模）暴露的三个解析缺口
OCR_REAL = """## 二、古代诗文阅读（35分）

【注】①支道林：东晋高僧。②啗：同“啖”。15.下列对这首诗的理解和赏析，不正确的一项是（3分）

A．首联以“两无心”三字点出诗人无意奔走尘世。

B．颈联以“悠悠”对“冉冉”状写时光流逝。

C．尾联“天闲”指天子马厩。

D．全诗以“出游归隐”为题。

## 6.下列对本文相关内容和艺术特色的分析鉴赏，正确的一项是（3分）

A. 甲项的说法成立。

B. 乙项的说法成立。

C. 丙项的说法成立。

D. 丁项的说法成立。

22. 根据文本内容，完成表格。（4分）

<table><tr><td rowspan="2">语言“磨损”的后遗症</td><td>1</td></tr><tr><td>2</td></tr><tr><td>文化记忆缺失</td><td>3</td></tr></table>
"""


def test_real_corpus_gaps():
    blocks = md2chinese.convert(OCR_REAL, "shiti")["blocks"]
    qs = {b["no"]: b for b in blocks if b["type"] == "question"}

    # 1) 题号黏在注释句末（【注】…炊具。15.下列…）→ 必须拆出第 15 题
    if 15 not in qs:
        FAILS.append(f"FAIL 注释句末黏连的题号未拆开，题号={sorted(qs)}")
    # 2) 题干被排成标题行（## 6.下列…）→ 必须识别为题目
    if 6 not in qs:
        FAILS.append(f"FAIL 标题行题干未识别，题号={sorted(qs)}")
    # 3) HTML 表格 → raw tabular 块，不能把单元格挤成一行
    raws = [b for b in blocks if b["type"] == "raw" and "tabular" in b.get("tex", "")]
    if not raws:
        FAILS.append("FAIL HTML 表格未转成 tabular")
    else:
        has(raws[0]["tex"], "& 1", "表格首行单元格")
        if "<td" in raws[0]["tex"] or "<table" in raws[0]["tex"]:
            FAILS.append("FAIL 表格里仍残留 HTML 标签")
    # 4) 表格里的圈号也要转 \xq（否则缺字形丢字）
    t = md2chinese.table_html_to_latex(
        "<table><tr><td>①甲</td><td>②乙</td></tr></table>")
    has(t, "\\xq{1}", "表格圈号转 \\xq")

    # 5) --keep-roman 保留 Ⅰ；默认转 ASCII
    eq("I" in md2chinese.clean_markdown("阅读Ⅰ"), True, "默认罗马数字转 ASCII")
    eq("Ⅰ" in md2chinese.clean_markdown("阅读Ⅰ", keep_roman=True), True,
       "keep_roman 保留原字")

    # 6) 长单元格表格用 \dimexpr 列宽（扣掉 \tabcolsep，否则 6 列必 Overfull）
    wide = md2chinese.table_html_to_latex(
        "<table><tr><td>对比维度</td><td>唐代兵制</td><td>宋代兵制</td>"
        "<td>第四列内容确实非常长需要换行显示</td><td>第五列</td><td>第六列</td></tr></table>")
    has(wide, "\\dimexpr", "长单元格表格用 dimexpr 列宽")
    has(wide, "2\\tabcolsep", "列宽扣掉 tabcolsep")


def test_daan_heading_question():
    """答案卷题号被排成标题行 `## 15. (3分)C…`：要成 ans 块，且不能把 `##` 印进 PDF。"""
    md = ("## 14. (3分)①周朝以德治国；②秦朝用严刑峻法。\n\n"
          "## 15. (3分)C(“勤劳”“劳动精神”错误)\n\n"
          "## 23.(60分) 参考高考作文评分标准\n")
    blocks = md2chinese.convert(md, "daan")["blocks"]
    nos = [b["no"] for b in blocks if b["type"] == "ans"]
    for want in (14, 15, 23):
        if want not in nos:
            FAILS.append(f"FAIL 答案卷标题行题号 {want} 未识别，nos={nos}")
    joined = json.dumps(blocks, ensure_ascii=False)
    if "#" in joined:
        FAILS.append("FAIL 答案块里残留 markdown # 号")


# ── 3. ywexam.sty ────────────────────────────────────────────

def test_sty():
    s = STY.read_text(encoding="utf-8")
    has(s, "\\IfFontExistsTF{SimSun}", "字体回退入口")
    has(s, "Noto Serif CJK SC", "Linux 中文字体回退")
    has(s, "AR PL UKai CN", "Linux 楷体回退")
    has(s, "choicesinline", "横排选项环境")
    has(s, "\\RequirePackage{tasks}", "tasks 宏包")
    has(s, "\\task", "tasks 条目命令")
    has(s, "\\ywlinespread", "行距命令")
    has(s, "\\fullglyph", "生僻字兜底")
    has(s, "\\detokenize{#2}", "answertitle 空副标题跳过")
    # 硬编码字体必须包在探测分支里
    has(s, "\\IfFontExistsTF{SimSun}{\\setCJKmainfont{SimSun}", "SimSun 走探测分支")


# ── 4. scan_log ──────────────────────────────────────────────

def test_scan_log():
    log = ("! Undefined control sequence.\n"
           "Missing character: There is no 郤 (U+90E5) in font SimSun/OT:script=hani;\n"
           "Missing character: There is no 郤 (U+90E5) in font SimSun/OT:script=hani;\n"
           "Overfull \\hbox (12.3pt too wide) in paragraph at lines 210--212\n"
           "LaTeX Warning: Reference `LastPage' on page 1 undefined on input line 29.\n")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.log"
        p.write_text(log, encoding="utf-8")
        res = scan_log.scan_one(p)
        eq(res["missing"].get("郤"), 2, "缺字形计数")
        eq(len(res["errors"]), 1, "错误条数")
        eq(res["overfull"][0]["pt"], 12.3, "溢出宽度")
        eq(res["undefined_refs"][0]["ref"], "LastPage", "未解析引用")


def main():
    for fn in (test_inline_choices, test_figure_block, test_subans_multiline,
               test_linespread_and_hint, test_md2chinese, test_md2chinese_answer,
               test_real_corpus_gaps, test_daan_heading_question, test_sty,
               test_scan_log):
        before = len(FAILS)
        fn()
        print(f"{'[PASS]' if len(FAILS) == before else '[FAIL]'} {fn.__name__}")

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_chinese_ir_fixes: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
