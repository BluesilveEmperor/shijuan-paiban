#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""english_clean.py — 英语 OCR Markdown 清洗层

从 52 套样本沉淀的 EC-010 / EC-011 / EC-016 出发，在 Markdown → IR 之前清洗：

- 公众号水印（``IAI English`` / ``微信公众号…``）渗入标题
- OCR 垃圾串 ``ladnepen``（如 ``1.5ladnepen分``）
- 小节标题里混入整段正文（``\\sectitle`` 只应保留「第X节（…）」）
- HTML 实体 ``&amp;`` / ``&#39;`` 等
- 英文语境里的中文引号 ``“”`` → 直引号
- 中文标点紧挨英文时归一为英文标点（``，；：（）！？、``）

只做无损/低风险清洗；OCR  text 本身的拼写错误（如 ``t.llling``）保留，交人工核对。
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

# 水印整串优先：微信公众号后的英文品牌名（IAI English）要一并去掉，
# 否则旧顺序会先吃掉「微信公众号IAI」而残留「 English」。
WATERMARK_RE = re.compile(
    r"(?:微信公众号\s*(?:IAI\s*English|IAIEnglish|[^\s，,。]*)"
    r"|IAI\s*English|IAIEnglish)", re.I)
GARBAGE_RE = re.compile(r"ladnepen")
SECTION_RE = re.compile(r"^(?:#{1,3}\s*)?第[一二三四五六七八九十]+节[（(].*?[）)]")
# 小节标题后紧跟正文：在第一个右括号之后截断（标题里不再含正文）
SECTION_CUT_RE = re.compile(r"^(第[一二三四五六七八九十]+节[（(][^）)]*[）)]).+$")
CN_PUNCT = {"，": ", ", "；": "; ", "：": ": ", "（": "(", "）": ")",
            "！": "!", "？": "?", "、": ", "}
ASCII_WORD = re.compile(r"[A-Za-z0-9]")


@dataclass
class CleaningStats:
    watermark: int = 0
    garbage: int = 0
    section_leak: int = 0
    entities: int = 0
    quotes: int = 0
    punctuation: int = 0

    def as_dict(self) -> dict:
        return {"watermark": self.watermark, "garbage": self.garbage,
                "section_leak": self.section_leak, "entities": self.entities,
                "quotes": self.quotes, "punctuation": self.punctuation}


def _is_english_context(s: str, idx: int) -> bool:
    """引号/标点左右是否出现西文字符（有中文字符时保留原标点）。"""
    left = s[max(0, idx - 1):idx]
    right = s[idx + 1:idx + 2]
    if re.search(r"[\u4e00-\u9fff]", left + right):
        return False
    return bool(ASCII_WORD.search(left + right))


def normalize_punctuation(line: str, stats: CleaningStats) -> str:
    out = []
    for i, ch in enumerate(line):
        if ch in "“”":
            if _is_english_context(line, i):
                stats.quotes += 1
                out.append('"')
            else:
                out.append(ch)
        elif ch in CN_PUNCT and _is_english_context(line, i):
            stats.punctuation += 1
            out.append(CN_PUNCT[ch])
        else:
            out.append(ch)
    return "".join(out)


def clean_line(line: str, stats: CleaningStats, cut_section: bool = True) -> str:
    if WATERMARK_RE.search(line):
        stats.watermark += 1
        line = WATERMARK_RE.sub("", line)
    if GARBAGE_RE.search(line):
        stats.garbage += 1
        line = GARBAGE_RE.sub("", line)
    if "&" in line and re.search(r"&(?:amp|lt|gt|quot|#\d+);", line):
        stats.entities += 1
        line = html.unescape(line)
    # 试题卷：小节标题里混入正文属异常，截断到第一个右括号。
    # 答案卷：小节标题后紧跟的就是答案组（如「第二节（共5小题）36-40 CDABF」），
    # 不能截断，故 cut_section=False。
    if cut_section and SECTION_RE.match(line.strip()):
        m = SECTION_CUT_RE.match(line.strip())
        if m:
            stats.section_leak += 1
            line = line.replace(line.strip(), m.group(1))
    return normalize_punctuation(line.rstrip(), stats)


def clean_markdown(text: str, stats: CleaningStats | None = None,
                   cut_section: bool = True) -> str:
    """清洗整篇 Markdown；返回清洗后文本。

    ``cut_section`` 默认 True（试题卷：截断小节标题泄漏的正文）；
    答案卷须传 False，保留小节标题后紧跟的答案组。
    """
    st = stats if stats is not None else CleaningStats()
    lines = [clean_line(ln, st, cut_section=cut_section) for ln in text.splitlines()]
    # 清洗后产生的连续空格收一次，但保留缩进（选项缩进等由解析器处理）
    lines = [re.sub(r"[ \t]{3,}", "  ", ln) for ln in lines]
    return "\n".join(lines)
