#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_md2chinese.py — OCR Markdown → 语文 IR 转换回归

用内联样本覆盖真实 OCR 中出现过的写法：水印、圈号、图片、注意事项编号、
题号与选项、材料标签与出处、答案汇总行与同行两题。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))
sys.path.insert(0, str(ROOT / "scripts"))

import md2chinese  # noqa: E402

FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}\n  expected={expected!r}\n  actual  ={actual!r}")


def main():
    # 1. 清洗
    raw = ("注意事项：微信公众号朝文道CwD\n"
           "自书契 $^{①}$ 之作，① ② ③ ④ 均见于《书》。\n"
           "![](images/a.jpg)\n"
           "The image contains only three horizontal lines.\n")
    cleaned = md2chinese.clean_markdown(raw)
    eq("微信公众号" in cleaned, False, "去水印")
    eq("The image contains" in cleaned, False, "去 VLM 幻觉")
    eq(r"\xq{1}" in cleaned and r"\xq{4}" in cleaned, True, "圈号转 xq")
    eq("includegraphics" in cleaned, True, "图片转 LaTeX")
    eq("$^{" in cleaned, False, "脚注标记展开")

    # 2. 试题结构（含卷首注意事项里的 1./2.，不能算题目）
    md = """# 2025 学年第一学期杭州市高三年级教学质量检测

注意事项：
1. 答题前，填写姓名。
2. 考试结束后交卷。

## 一、阅读 (72 分)

## (一) 阅读 I (本题共 5 小题, 19 分)

阅读下面的文字，完成 1~5 题。

材料正文第一段。

材料正文第二段。

(摘编自《某某》)

1. 下列对原文相关内容的理解和分析，正确的一项是 ( ) (3 分)
A. 选项一
B. 选项二
C. 选项三
D. 选项四

2. 根据原文内容，下列说法不正确的一项是 ( ) (3 分)
A. 甲
B. 乙
C. 丙
D. 丁

【注】①迩英：阁名。
"""
    ir = md2chinese.convert(md, "shiti")
    types = [b["type"] for b in ir["blocks"]]
    eq(types.count("sechead"), 1, "一个大题")
    eq(types.count("subsechead"), 1, "一个小题标题")
    eq(types.count("lead"), 1, "导语")
    eq(types.count("question"), 2, "注意事项不算题目")
    eq([b["no"] for b in ir["blocks"] if b["type"] == "question"], [1, 2],
       "题号连续")
    eq(types.count("note"), 1, "注释块")
    eq(any(b.get("source") and "摘编自" in b["source"] for b in ir["blocks"]),
       True, "材料出处归位")
    qs = [b for b in ir["blocks"] if b["type"] == "question"]
    eq(len(qs[0].get("options", [])), 4, "选项恰好四项")

    # 3. 一行四选项 + 空行分隔选项（OCR 最常见的两种形态）
    md2 = """## 二、语言文字运用 (18 分)

18. 填入括号内词语，合适的一项是（）(3 分)
A. 五光十色    B. 琳琅满目    C. 光怪陆离    D. 丰富多彩
"""
    ir2 = md2chinese.convert(md2, "shiti")
    q = [b for b in ir2["blocks"] if b["type"] == "question"][0]
    eq(len(q.get("options", [])), 4, "同行四选项可拆分")

    # 空行分隔的选项（曾因 take_options 遇空行提前退出而整组丢失）
    md3 = """## 一、阅读 (20 分)

1. 下列对材料相关内容的理解，正确的一项是 (3 分)

A. 选项甲

B. 选项乙

C. 选项丙

D. 选项丁

2. 下一题（3 分）
"""
    ir4 = md2chinese.convert(md3, "shiti")
    qs4 = [b for b in ir4["blocks"] if b["type"] == "question"]
    eq(len(qs4), 2, "空行不吞掉下一题")
    eq(qs4[0].get("options"), ["选项甲", "选项乙", "选项丙", "选项丁"],
       "空行分隔的四项选项完整")

    # 4. 答案：汇总行 + 同行两题 + 评分说明
    ans_md = """# 2025 学年第一学期杭州市高三年级教学质量检测

# 语文参考答案

选择题：1.C 2.D 6.C

## 一、阅读（72分）

3.（1）参与式观察与访谈；（2）社会文明和文化心理。（3分。每空1分）

4. 引用罗萨的观点，提出问题困境。（2分）5. ①借助人工智能快速获取资料。（6分。每点2分）

（4分。每点2分，写出任意两点即可）
"""
    ir3 = md2chinese.convert(ans_md, "daan")
    ans = [b for b in ir3["blocks"] if b["type"] == "ans"]
    eq(sorted(b["no"] for b in ans), [1, 2, 3, 4, 5, 6], "答案题号 1-6 完整")
    eq(any(b["type"] == "scorenote" for b in ir3["blocks"]), True, "评分说明块")
    eq(next(b for b in ans if b["no"] == 1)["text"], "C", "汇总答案文本")

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_md2chinese: all passed")
    return 0


    # 5. MinerU VLM 的规则说明文字不应进正文（曾整段出现在杭州一模末页）
    md5 = """## 三、写作 (60 分)

The Ground Truth image displays a single, continuous horizontal line, which is a
stylistic or background element. According to Rule 2, such lines must be ignored
by the OCR result. Therefore, the OCR result is inconsistent with the Ground Truth.

23. 阅读下面的材料，根据要求写作。(60 分)
"""
    ir5 = md2chinese.convert(md5, "shiti")
    body = " ".join(str(b.get("text", "")) + " ".join(b.get("options", []))
                    for b in ir5["blocks"])
    eq("Ground Truth" not in body, True, "VLM 规则说明文字被过滤")
    eq(any(b.get("no") == 23 for b in ir5["blocks"]), True, "过滤后题目仍保留")

if __name__ == "__main__":
    sys.exit(main())
