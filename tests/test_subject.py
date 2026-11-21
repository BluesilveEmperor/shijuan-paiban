#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_subject.py — 学科配置层回归

覆盖：默认学科、环境变量切换、答题卡命名（数学历史行为 + 语文 / 英语）、
未知学科报错、必备宏包清单。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import subject  # noqa: E402

FAILS = []


def eq(actual, expected, label):
    if actual != expected:
        FAILS.append(f"FAIL {label}: expected {expected!r}, actual {actual!r}")


def main():
    # 1. 默认学科取 shijuan.config.yaml（分支语义：math 分支 math，chinese 分支 chinese）
    subject.reset_cache()
    os.environ.pop("SHIJUAN_SUBJECT", None)
    configured = subject.resolve_subject()
    eq(configured in subject.PROFILES, True, "默认学科合法")
    eq(subject.get("paper_title"), subject.PROFILES[configured]["paper_title"],
       "默认卷名随学科")

    # 2. 环境变量覆盖
    os.environ["SHIJUAN_SUBJECT"] = "chinese"
    subject.reset_cache()
    eq(subject.resolve_subject(), "chinese", "环境变量切学科")
    eq(subject.get("name"), "语文", "学科中文名")
    eq(subject.get("md_output_dir"), "chinese-output", "语文 MD 输出目录")
    eq(subject.get("log_branch"), "log_runtime_chinese", "语文日志分支")

    # 3. 语文答题卡命名
    eq(subject.sheet_stem("2611语文卷-嘉兴一模", "a4"),
       "2611语文答题卡（A4）-嘉兴一模", "语文 A4 命名")
    eq(subject.sheet_stem("2026届高三语文试题", "a3"),
       "2026届高三语文试题-答题卡-A3", "语文无前缀回退")

    # 3-B. 英语学科档案（english 分支）
    os.environ["SHIJUAN_SUBJECT"] = "english"
    subject.reset_cache()
    eq(subject.resolve_subject(), "english", "环境变量切英语")
    eq(subject.get("name"), "英语", "英语学科中文名")
    eq(subject.get("md_output_dir"), "english-output", "英语 MD 输出目录")
    eq(subject.get("log_branch"), "log_runtime_english", "英语日志分支")
    eq(subject.get_profile("english")["long_answer_env"], None,
       "英语不强制长答题环境")
    eq(subject.sheet_stem("2611英语卷-嘉兴一模", "a4"),
       "2611英语答题卡（A4）-嘉兴一模", "英语 A4 命名")
    eq(subject.sheet_stem("2026届高三英语试题", "a3"),
       "2026届高三英语试题-答题卡-A3", "英语无前缀回退")

    # 4. 数学命名保持历史行为（分支回归）
    eq(subject.sheet_stem("2611数学卷-嘉兴一模", "a4", subject="math"),
       "2611数学答题卡（A4）-嘉兴一模", "数学 A4 命名")
    eq(subject.sheet_stem("2611数学试卷-绍兴二模", "a3", subject="math"),
       "2611数学答题卡（A3）-绍兴二模", "数学试卷 A3 命名")
    eq(subject.sheet_stem("2025届高三数学试题", "a4", subject="math"),
       "2025届高三数学试题-答题卡-A4", "数学无前缀回退")

    # 5. 必备宏包按学科分派
    eq("tasks" in subject.get_profile("math")["required_packages"], True,
       "数学需要 tasks")
    eq("ctex" in subject.get_profile("chinese")["required_packages"], True,
       "语文需要 ctex")

    # 6. 未知学科必须报错，不静默退回数学
    try:
        subject.get_profile("physics")
        FAILS.append("FAIL 未知学科未报错")
    except ValueError:
        pass

    os.environ.pop("SHIJUAN_SUBJECT", None)
    subject.reset_cache()

    if FAILS:
        for f in FAILS:
            print(f)
        return 1
    print("test_subject: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
