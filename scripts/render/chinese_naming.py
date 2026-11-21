#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chinese_naming.py — 语文卷/答案的产物命名

规则（用户 2026-11 定）：

    试题：`语文卷-<考试名>.tex`
    答案：`语文答案-<考试名>.tex`

`<考试名>` 优先从源 PDF 文件名截取；文件名过长（含年份/学段/考试类型等冗词）
或过短（如「试题」「答案」）时，回退用文件夹名（去掉开头 4 位年月号）。

同一目录下试题与答案必须共用同一个考试名。
"""

import re

PREFIX = "语文"
KIND_STEM = {"shiti": "语文卷", "daan": "语文答案"}

# 收尾词：从文件名尾部剥掉的体裁词（顺序敏感：长的在前）
TAIL_WORDS = ("参考答案及评分标准", "参考答案", "答案及评分标准", "评分参考",
              "答案", "试题卷", "试题", "试卷", "练习卷", "高三年级", "语文", "高三", "卷")

# 开头噪声：序号、学段、学科
HEAD_WORDS = ("答案", "试题", "试卷", "语文", "高三", "高二", "高一", "高中")

MIN_LEN = 3          # 短于此长度视为无效名（「试题」「答案」；「湖丽衢」「Z20」可通过）
MAX_LEN = 14         # 长于此长度视为冗长，优先用文件夹名

# 少数目录的源文件名与文件夹名都不可用（过长/互相矛盾），人工指定简称
OVERRIDES = {
    "2504南京师范大学附属中学杭二长郡三校联考": "三校联考",
}


def strip_tail(s: str) -> str:
    s = s.strip()
    changed = True
    while changed:
        changed = False
        # 导出序号 / 尾部括号备注可能藏在体裁词之后（「…测试(一)答案」）
        for pat in (r"[_\-\s]*_?\d{1,3}$", r"[（(][^（()）]{0,12}[)）]$"):
            new = re.sub(pat, "", s)
            if new != s:
                s, changed = new, True
        for w in TAIL_WORDS:
            if s.endswith(w) and len(s) > len(w):
                s = s[: -len(w)].rstrip(" -_—·")
                changed = True
    return s.strip(" -_—·")


def strip_head(s: str) -> str:
    s = s.strip()
    changed = True
    while changed:
        changed = False
        # 年份/届/月，允许中文与数字之间有空格（OCR 常见「2025 年 3月」）
        for pat in (r"^\d{4}\s*年\s*\d{0,2}\s*月?\s*",
                    r"^\d{4}\s*届\s*",
                    r"^\d{2}\s*年\s*\d{1,2}\s*月\s*",
                    r"^\d{2}\s*届\s*",
                    r"^\d{4,6}\s*"):
            new = re.sub(pat, "", s)
            if new != s:
                s, changed = new.lstrip(" -_—·"), True
        for w in HEAD_WORDS:
            if s.startswith(w) and len(s) > len(w):
                s = s[len(w):].lstrip(" -_—·")
                changed = True
    return s


def normalize(s: str) -> str:
    """去掉首尾噪声、尾部导出序号、括号内容，压缩空白，得到候选考试名。"""
    s = re.sub(r"\.pdf$", "", s, flags=re.I)
    s = s.replace("\u3000", " ").strip()
    for junk in ("（修订版）", "(修订版)", "（原卷版）", "(原卷版)", "（解析版）", "(解析版)"):
        s = s.replace(junk, "")
    s = strip_head(s)
    s = strip_tail(s)
    s = re.sub(r"\s+", "", s)
    return s.strip(" -_—·")


def usable(name: str) -> bool:
    """长度落在 [MIN_LEN, MAX_LEN] 且不是纯数字/纯符号，才认为可当考试名。"""
    if not (MIN_LEN <= len(name) <= MAX_LEN):
        return False
    # 「届高三模拟考试」这种残名说明前缀剥离出错，宁可回退文件夹名
    if name[0] in "届年月、，。：:":
        return False
    return bool(re.search(r"[\u4e00-\u9fa5A-Za-z]", name))


def folder_name(folder: str) -> str:
    """文件夹名 → 考试名：去掉开头 4 位年月号（2504 / 2605），压缩空白。"""
    s = folder.strip()
    s = re.sub(r"^\d{4}\s*", "", s)
    s = re.sub(r"\s+", "", s)
    return s or folder.strip()


def folder_name(folder: str) -> str:
    """文件夹名 → 考试名：去掉开头 4 位年月号（2504 / 2605），压缩空白。"""
    s = folder.strip()
    s = re.sub(r"^\d{4}\s*", "", s)
    s = re.sub(r"\s+", "", s)
    return s or folder.strip()


def exam_name(folder: str, shiti_pdf: str = "", daan_pdf: str = "",
              prefer: str = "folder") -> str:
    """确定考试名。

    prefer="folder"（默认）  文件夹名合法（4~14 字）就直接用，否则退回文件名
    prefer="file"            文件名清洗后合法就用，否则退回文件夹名

    实测题库里源 PDF 文件名普遍带「2025年」「26届」「语文试题」等冗余，
    清洗后仍不如文件夹名简洁，故默认以文件夹名为准。
    """
    fname = folder_name(folder)
    if folder in OVERRIDES:
        return OVERRIDES[folder]
    if prefer == "folder" and usable(fname):
        return fname

    for stem in (shiti_pdf, daan_pdf):
        if not stem:
            continue
        cand = normalize(stem)
        if usable(cand):
            return cand
    return fname


def output_stem(kind: str, exam: str) -> str:
    """kind ∈ {shiti, daan} → 「语文卷-XXX」/「语文答案-XXX」。"""
    return f"{KIND_STEM[kind]}-{exam}"
