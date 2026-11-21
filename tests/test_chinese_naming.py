#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chinese_naming.py — 语文产物命名回归

规则（用户 2026-11 定）：
    试题 → 语文卷-<考试名>.tex
    答案 → 语文答案-<考试名>.tex
考试名：源 PDF 文件名截取；过长/过短时用文件夹名（去 4 位年月前缀）。

用例全部取自 D:\\Documents\\01_Study_Research\\高中语文 的真实目录与文件名。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))
sys.path.insert(0, str(ROOT / "scripts"))

from chinese_naming import exam_name, normalize, output_stem  # noqa: E402

FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}: expected {expected!r}, actual {actual!r}")


def main():
    # 1. 文件名清洗：去掉届/年份/学科/体裁词
    eq(normalize("25届温州二模语文试题.pdf"), "温州二模", "清洗 25届+语文试题")
    eq(normalize("26届金华一模语文试题.pdf"), "金华一模", "清洗 26届")
    eq(normalize("2025年广东二模答案.pdf"), "广东二模", "清洗 2025年+答案")
    eq(normalize("答案 2025重庆康德二诊语文(1).pdf"), "重庆康德二诊", "清洗 前缀答案+尾部(1)")
    eq(normalize("台州市二模语文参考答案_00.pdf"), "台州市二模", "清洗 尾部_00+参考答案+语文")
    eq(normalize("202505苏锡常镇四市语文卷评分参考.pdf"), "苏锡常镇四市", "清洗 数字前缀+评分参考")
    eq(normalize("2025 年 3月济南市高三模拟考试试题.pdf"), "济南市高三模拟考试",
       "清洗 带空格的年月")

    # 2. 文件夹名：去掉 4 位年月前缀与空格
    eq(exam_name("2504嘉兴二模", "嘉兴市2025年高三第一次教学检测试题.pdf", "",
                 prefer="folder"), "嘉兴二模", "文件夹名优先")
    eq(exam_name("2505  Z20", "试题.pdf", "答案.pdf"), "Z20", "双空格文件夹名")
    eq(exam_name("2409武汉九调", "试题.pdf", "答案.pdf"), "武汉九调", "无前缀数字")

    # 3. 文件名太短 → 文件夹名
    eq(exam_name("2511杭州一模", "试题.pdf", "答案.pdf"), "杭州一模", "名字太短回退")
    # 4. 文件名太长 → 文件夹名
    long_pdf = ("Z20+名校联盟（浙江省名校新高考研究联盟）2026届高三第三次学情诊断"
                "语文试题.pdf")
    eq(exam_name("2605 Z20", long_pdf, "答案.pdf"), "Z20", "名字太长回退")

    # 5. 三字简称可用
    eq(exam_name("2504湖丽衢", "衢州、丽水、湖州二模_00.pdf", ""), "湖丽衢", "三字简称")

    # 6. 试题与答案共用同一考试名（哪怕回退到文件夹名，也必须一致）
    src = ("2504广州一模", "2025年广州市普通高中毕业班综合测试(一)_00.pdf",
           "2025年广州市普通高中毕业班综合测试(一)答案.pdf")
    a = exam_name(src[0], src[1], "", prefer="file")
    b = exam_name(src[0], "", src[2], prefer="file")
    eq(a, b, "试题与答案考试名一致")
    eq(len(a) <= 14, True, "考试名不超长")

    # 7. 产物名
    eq(output_stem("shiti", "嘉兴二模"), "语文卷-嘉兴二模", "试题产物名")
    eq(output_stem("daan", "嘉兴二模"), "语文答案-嘉兴二模", "答案产物名")

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_chinese_naming: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
