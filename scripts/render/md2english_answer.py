#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""md2english_answer.py — 英语参考答案 OCR Markdown → 答案卷 IR

与 ``md2english.py``（试题卷）配对；产出同构 ``english.json`` 块流，
但使用答案专用块，交给 ``render_english.py`` 渲染成 ``\documentclass[answers]{英语试卷}``。

从真实答案 pdf（01 武汉二调 / 02 南京九调）归纳的结构::

    # 考试名                       → answer_title.title
    # 英语参考答案                  → answer_title.subject（跳过此行）
    第一部分 听力 / ## 第二部分 …     → part
    第一节 1-5 BBACC               → section + answers(groups)
    第二节 6-10 CAABB 11-15 …      → answers(groups)
    第二节：56. for 57. but/yet…   → blank_answers(items)
    第四部分 写作                    → part
    第一节 / 第二节 (满分25分)       → writing_sample(title)
    （其后的散文段落）               → writing_sample.paragraphs
    ## Text N …（听力原文）          → 可选：para 保留（--with-scripts）

共用 english_clean 清洗水印 / 垃圾串 / 实体 / 标点。

用法::

    python scripts/render/md2english_answer.py 答案.md -o daan.english.json
    python scripts/render/md2english_answer.py --schema
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from english_clean import CleaningStats, clean_markdown  # noqa: E402

# 章节
RE_H1 = re.compile(r"^#\s+(.+?)\s*$")
RE_H2 = re.compile(r"^#{2,3}\s+(.+?)\s*$")
RE_PART = re.compile(r"^(第[一二三四五六七八九十]+部分)")
RE_SECTION = re.compile(r"^(第[一二三四五六七八九十]+节)\b(.*)$")
RE_WRITING_HINT = re.compile(r"写作|书面表达")
# 选择题答案组：1-5 BBACC / 6-10ABCCB / 1-5. BCAAB / 21-23 CBD
# （允许无空格、全角标点、区间尾带点号）
RE_ANSWER_GROUP = re.compile(
    r"(\d{1,2})\s*[-—~至]\s*(\d{1,2})\s*[.．、]?\s*([A-Ga-g]{1,10})(?![A-Za-z])")
# 语法填空答案：56. for / 57. but/yet/while / 60. to host（答案可多词）
# 每个答案捕获到「下一个题号.」之前的全部文本
RE_BLANK_ANSWER = re.compile(
    r"(\d{1,2})\s*[.．、](?!\s*\d)\s*(\S+(?:\s+\S+)*?)(?=\s+\d{1,2}\s*[.．、]|\s*$)")
# 详解截断：中文（含中文标点）出现处即为详解起点
RE_CN_SPLIT = re.compile(r"[\u4e00-\u9fff，。；：？！、“”‘’（）《》]")
# 写作范文小标题
RE_SAMPLE_TITLE = re.compile(r"^第([一二三四五六七八九十]+)节\s*(?:[（(].*?[）)])?\s*[：:]?\s*$")
# 听力原文区标记
RE_SCRIPT_MARK = re.compile(
    r"^(?:#{1,3}\s*)?(?:Text\s*\d+|听第.*材料|听力原文|听力材料|听力.*录音稿)", re.I)
RE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


class ParseReport:
    def __init__(self):
        self.warnings = []
        self.cleaning = CleaningStats()

    def warn(self, msg):
        self.warnings.append(msg)


def tex_escape(s: str) -> str:
    """普通正文 → TeX-ready（答案串单独处理，不走这里）。

    保留 ``$...$`` 数学段（听力原文里的 ``$N$`` 说话人标记、``$2\\mathrm{~B}$``），
    并保护已转义的特殊字符不被后续“孤立反斜杠”修复误伤。
    """
    if not s:
        return ""
    s = RE_IMAGE.sub("", s)
    holders = []

    def hold(text):
        holders.append(text)
        return f"\x00{len(holders) - 1}\x00"

    # 1) 数学段整段保护（含其中的 \mathrm 等命令）。
    #    起止 $ 前不能是反斜杠（\$A … \$B 中间段会被误当数学段），非贪婪配对。
    #    段内裸 % 是 LaTeX 注释符、裸 & 是对齐符（OCR 伪数学段如 $20%$、
    #    两个货币 $ 误配对会把正文圈进来），统一转义保编译
    def hold_math(m):
        # 只转义裸 % 和 &（已转义的 \% / \& 不再二次转义，否则 \\\% 变成
        # 换行 + 注释，吞掉行尾的收尾 $）
        inner = re.sub(r"(?<!\\)%", r"\\%", m.group(0))
        inner = re.sub(r"(?<!\\)&", r"\\&", inner)
        return hold(inner)

    s = re.sub(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", hold_math, s)
    # 2) OCR 已输出的转义序列 \$ \% \# \& \_ 整体占位，避免其中的 \ 被
    #    步骤 4 的孤立反斜杠清理误伤成 ／
    s = re.sub(r"\\[&%#_$]", lambda m: hold(m.group(0)), s)
    # 2) 转义特殊字符并立刻占位，避免后面的反斜杠清理误伤 \& → ／&
    s = re.sub(r"[&%#_$]", lambda m: hold(
        {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$"}[m.group(0)]), s)
    # 3) 孤立反斜杠（OCR 把 / 识成 \）还原为全角斜杠
    s = re.sub(r"\\(?![a-zA-Z\\\{}\[\]])", "／", s)
    # 4) 恢复占位
    for k, v in enumerate(holders):
        s = s.replace(f"\x00{k}\x00", v)
    return s.strip()


def _strip_heading(text: str) -> str:
    """去掉小节标题里的括号说明（满分 XX 分），保留「第X节」主干。"""
    return re.sub(r"\s*[（(].*?[）)]\s*", "", text).strip()


def _parse_table_answers(line: str) -> list:
    """从 HTML 表格行提取 [(题号, 答案), ...]。

    兼容两种真实格式：
    - 单元格内直书「21 A」「22 D」（2504佛山二模）
    - 「序号」行 + 「答案」行成对出现（2502南昌一模）
    """
    if "<table" not in line:
        return []
    out = []
    # 模式 A：<td>21 A</td>
    for m in re.finditer(r"<td>\s*(\d{1,2})\s+([A-Ga-g]{1,4})\s*</td>", line):
        n = int(m.group(1))
        if 1 <= n <= 75:
            out.append((n, m.group(2).upper()))
    if out:
        return out
    # 模式 B：<tr><td>序号</td><td>1</td>…</tr><tr><td>答案</td><td>C</td>…</tr>
    rows = re.findall(r"<tr>(.*?)</tr>", line)

    def cells(r):
        return [c.strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r)]

    pending = None
    for r in rows:
        cs = cells(r)
        if not cs:
            continue
        if cs[0] in ("序号", "题号", "题序"):
            pending = [c for c in cs[1:] if c]
        elif cs[0] == "答案" and pending:
            for n, a in zip(pending, [c for c in cs[1:] if c]):
                a = (a or "").strip()
                # 语法填空答案可为多词（is found / To boost）
                if n.isdigit() and re.fullmatch(r"[A-Za-z][A-Za-z\s/'-]{0,29}", a):
                    out.append((int(n), a))
            pending = None
    return out


def _parse_answer_groups(line: str) -> list:
    """从行里抽出 [(起, 止, 答案串), ...]。

    只认 `1-5 BBACC` 这种区间组；不认 `57. a` 单选——后者是语法填空答案
    （答案为字母 a 时会与单选冲突），交给 `_parse_blank_answers` 处理。
    """
    out = []
    for m in RE_ANSWER_GROUP.finditer(line):
        a, b, ans = int(m.group(1)), int(m.group(2)), m.group(3).upper()
        if a <= b and 1 <= a <= 65 and 1 <= b <= 65:
            out.append((a, b, ans))
    return out


def _parse_blank_answers(line: str) -> list:
    """从行里抽出 [(题号, 答案), ...]（语法填空 / 逐题详解）。

    兼容逐题详解行（如「56. which 考查非限制性定语从句。此处……」）：
    截取第一个中文之前的答案本体。若本体为空或仍是详解残段则丢弃。
    单字母答案（详解里的选择题/七选五答案）同样保留——是否与紧凑
    答案组重复由调用方的题号去重（seen_blanks）裁决。
    """
    out = []
    # 「41. 选 A。【解题思路】…」详解式选择题（2410惠州二模完形）。
    # 该行 RE_BLANK_ANSWER 的捕获会以中文「选」开头而被丢弃，不冲突
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[.．、]\s*选\s*([A-Ga-g])(?![A-Za-z])", line):
        n = int(m.group(1))
        if 1 <= n <= 65:
            out.append((n, tex_escape(m.group(2).upper())))
    for m in RE_BLANK_ANSWER.finditer(line):
        n, ans = int(m.group(1)), m.group(2)
        if not (1 <= n <= 65):  # 覆盖听力详解 1-20 与语法填空 56-65
            continue
        # 截掉详解部分：答案本体 = 第一个中文（含中文标点）之前的文本
        cut = RE_CN_SPLIT.split(ans, 1)[0].strip().rstrip(".．")
        if not cut:
            continue
        if len(cut) > 30 or re.search(r"[\u4e00-\u9fff]", cut):
            continue
        # 答案本体必须是英文词（单词/短语/斜杠备选/选项字母），
        # 排除纯数字等叙述性残段
        if not re.fullmatch(r"[A-Za-z][A-Za-z\s/'-]*", cut):
            continue
        out.append((n, tex_escape(cut)))
    return out


def parse_answer_markdown(text: str, source: str = "",
                          with_scripts: bool = True) -> tuple:
    """答案 OCR Markdown → (IR, report)。"""
    report = ParseReport()
    # 答案卷不能截断小节标题后的答案组（如「第二节（共5小题）36-40 CDABF」）
    cleaned = clean_markdown(text, report.cleaning, cut_section=False)
    lines = cleaned.splitlines()
    blocks = []

    title = ""
    subject = "英语"
    part = ""          # 当前部分（判断是否写作区）
    in_writing = False
    writing = None     # 当前 writing_sample 块
    script_mode = False
    script_para = []
    i = 0

    def flush_script():
        if script_para:
            joined = " ".join(x.strip() for x in script_para if x.strip())
            script_para.clear()
            if joined:
                blocks.append({"type": "para", "text": tex_escape(joined), "blanks": []})

    seen_blanks = set()  # 已入块的填空题号（紧凑答案行与详解行会重复产出）

    def collect_blanks(line):
        items = []
        for n, ans in _parse_blank_answers(line):
            if n not in seen_blanks:
                seen_blanks.add(n)
                items.append((n, ans))
        return items

    def emit_answers(groups):
        # 答案组覆盖的题号不再接受详解行的单字母填空，避免重复
        for a, b, _ in groups:
            seen_blanks.update(range(a, b + 1))
        return {"type": "answers", "groups": groups}

    def collect_blanks_table(line):
        ta = []
        for n, a in _parse_table_answers(line):
            if n not in seen_blanks:
                seen_blanks.add(n)
                ta.append((n, a))
        return ta

    while i < len(lines):
        ln = lines[i].strip()
        # OCR 对答案区间分隔符的转义（如 `1\~5 BACAA`、`07:38\-08:25`）：
        # 只还原 `~` 和 `-`；`\&`、`\%`、`\$` 等保留原样，交给 tex_escape
        # 的已转义序列保护（还原 `\%`/`\$` 会造成数学段误判，见巴蜀卷教训）
        ln = re.sub(r"\\([~-])", r"\1", ln)
        # 「51 A 52 D 53 A」/「56 offers 57 which …」无点号逐题式（2504佛山二模）
        # → 归一为「51. A」。仅当行内 ≥3 处「数字 空格 字母词」、行内无答案组
        # 区间（避免破坏 `21\~25 BADDA`）且非表格行（避免破坏 `<td>21 A</td>`）
        # 才改写，防止误伤普通文本
        if (len(re.findall(r"(?<!\d)\d{1,2}\s+[A-Za-z]", ln)) >= 3
                and not _parse_answer_groups(ln)
                and "<table" not in ln):
            ln = re.sub(r"(?<!\d)(\d{1,2})\s+(?=[A-Za-z])", r"\1. ", ln)
        if not ln:
            if writing:
                # 空行不结束范文，继续累积（段落间靠空行分隔）
                pass
            i += 1
            continue
        if RE_IMAGE.search(ln):
            report.warn("答案 md 含图片引用，已丢弃")
            i += 1
            continue
        # HTML 表格答案（2502南昌/2504佛山/2411南开）：单元格直书、
        # 序号-答案配对表、或单元格内区间组/填空（剥标签后复用解析器）
        if "<table" in ln:
            tg = _parse_answer_groups(re.sub(r"<[^>]+>", " ", ln))
            tg = [g for g in tg
                  if not any(n in seen_blanks for n in range(g[0], g[1] + 1))]
            if tg:
                blocks.append(emit_answers(tg))
            ta = collect_blanks_table(ln)
            if ta:
                blocks.append({"type": "blank_answers", "items": ta})
            i += 1
            continue

        # 听力原文区（## Text N 或“听第…材料”）——保留为 para
        if RE_SCRIPT_MARK.match(ln):
            if not script_mode:
                if writing:
                    blocks.append(writing)
                    writing = None
                script_mode = True
                flush_script()
            # 去掉 markdown 标题符号，避免 tex_escape 把 # 转义成 ／#／#
            script_para.append(re.sub(r"^#{1,3}\s*", "", ln))
            i += 1
            continue
        if script_mode:
            # 听力原文区结束标志：答案区标题（参考答案/第X部分/小节标题等）
            if (RE_H2.match(ln) or RE_PART.match(ln)
                    or "参考答案" in ln or "评分" in ln):
                script_mode = False
                flush_script()
            else:
                script_para.append(re.sub(r"^#{1,3}\s*", "", ln))
                i += 1
                continue

        m = RE_H1.match(ln)
        if m:
            value = m.group(1).strip()
            # 「考试名 英语参考答案」合并成一个 H1：剥掉答案后缀，余下作考试名
            stripped = re.sub(r"\s*英语?参考答案\s*$", "", value).strip()
            if stripped and stripped != value:
                if not title:
                    title = stripped
            elif "参考答案" in value or "答案" == value:
                subject = value
            elif not title:
                title = value
            else:
                # 第二个#标题往往是完整学年描述，作为补充 para
                blocks.append({"type": "para", "text": tex_escape(value), "blanks": []})
            i += 1
            continue

        m = RE_H2.match(ln)
        if m:
            value = m.group(1).strip()
            if writing:
                blocks.append(writing)
                writing = None
            # H2 也可能是 part/section/writing title，交给下面统一逻辑
            ln = value

        # part（第X部分）：标题行可能尾部直接跟答案组，如
        #   “第一部分 听力（共两节）1-5 CAACB 6-10 ABCCB …”
        mp = RE_PART.match(ln)
        if mp:
            if writing:
                blocks.append(writing)
                writing = None
            part = ln
            in_writing = bool(RE_WRITING_HINT.search(ln))
            # 拆出标题主干（到第一个右括号为止）与尾部答案组
            hm = re.match(r"^(第[一二三四五六七八九十]+部分[^（(]*[）)]?)", ln)
            head = hm.group(1).strip() if hm else ln
            tail = ln[len(head):].strip()
            blocks.append({"type": "part", "text": tex_escape(head)})
            groups = _parse_answer_groups(tail)
            if groups:
                blocks.append(emit_answers(groups))
            i += 1
            continue

        # 写作区范文标题：在 writing part 内，「第一节/第二节 (满分25分)」
        # 要优先于 section 判定，否则会被误当普通 section。
        if in_writing and RE_SAMPLE_TITLE.match(ln):
            if writing:
                blocks.append(writing)
            writing = {"type": "writing_sample",
                       "title": _strip_heading(ln), "paragraphs": []}
            i += 1
            continue

        # section（第X节）：可能同行带答案组 / 语法填空答案
        ms = RE_SECTION.match(ln)
        if ms:
            if writing:
                blocks.append(writing)
                writing = None
            sec_name = ms.group(1)
            rest = ms.group(2).strip()
            # section 标题只保留「第X节（说明）」，不含尾部答案组。
            # 取第一个右括号（若有）之前的片段作为标题主干。
            head = ln
            rb = ln.find("）")
            if rb == -1:
                rb = ln.find(")")
            if rb != -1 and rb + 1 < len(ln):
                head = ln[:rb + 1]
            elif not re.search(r"[（(]", ln):
                head = sec_name
            blocks.append({"type": "section", "text": tex_escape(head)})
            if rest:
                groups = _parse_answer_groups(rest)
                if groups:
                    blocks.append(emit_answers(groups))
                else:
                    blanks = collect_blanks(rest)
                    if blanks:
                        blocks.append({"type": "blank_answers", "items": blanks})
            i += 1
            continue

        # 正文里出现的写作标题（无 H2 前缀）
        if RE_WRITING_HINT.search(ln) and not writing:
            if writing:
                blocks.append(writing)
                writing = None
            part = ln
            in_writing = True
            blocks.append({"type": "part", "text": tex_escape(ln)})
            i += 1
            continue

        # 答案组行（1-5 BBACC 6-10 CAABB …）
        groups = _parse_answer_groups(ln)
        if groups:
            if writing:
                blocks.append(writing)
                writing = None
            blocks.append(emit_answers(groups))
            i += 1
            continue

        # 语法填空答案行（56. for 57. but/yet …）
        blanks = collect_blanks(ln)
        if blanks:
            if writing:
                blocks.append(writing)
                writing = None
            blocks.append({"type": "blank_answers", "items": blanks})
            i += 1
            continue

        # 剩余文本：写作区归入范文段落，否则普通 para。
        # 范文段落同样要 tex_escape（Dad & Mum 的 & 不转义会报
        # Misplaced alignment tab character &）。
        if writing:
            writing["paragraphs"].append(tex_escape(ln))
        else:
            blocks.append({"type": "para", "text": tex_escape(ln), "blanks": []})
        i += 1

    if writing:
        blocks.append(writing)
    if with_scripts:
        flush_script()
    else:
        script_para.clear()

    # 卷头：answer_title 必须是第一块（扫描时先收集 title，此处统一插入）
    if title:
        blocks.insert(0, {"type": "answer_title", "title": title, "subject": "英语"})

    # 统计
    n_answers = sum(len(b.get("groups", [])) for b in blocks if b["type"] == "answers")
    n_blanks = sum(len(b.get("items", [])) for b in blocks if b["type"] == "blank_answers")
    n_samples = sum(1 for b in blocks if b["type"] == "writing_sample")
    meta = {
        "subject": "english",
        "kind": "daan",
        "source": source,
        "title": title,
        "exam_subject": "英语",
        "answer_groups": n_answers,
        "blank_answers": n_blanks,
        "writing_samples": n_samples,
        "with_scripts": with_scripts,
        "block_count": len(blocks),
        "cleaning": report.cleaning.as_dict(),
        "warnings": report.warnings,
    }
    if not title:
        report.warn("未识别到考试名（answer_title.title 为空）")
    if n_answers == 0:
        report.warn("未识别到选择题答案组")
    return {"meta": meta, "blocks": blocks}, report


SCHEMA_EXAMPLE = {
    "meta": {
        "subject": "english", "kind": "daan", "source": "答案.md",
        "title": "武汉市2024届高中毕业生二月调研考试", "exam_subject": "英语",
        "answer_groups": 8, "blank_answers": 10, "writing_samples": 2,
    },
    "blocks": [
        {"type": "answer_title", "title": "武汉市2024届高中毕业生二月调研考试", "subject": "英语"},
        {"type": "part", "text": "第一部分 听力"},
        {"type": "section", "text": "第一节"},
        {"type": "answers", "groups": [[1, 5, "BBACC"], [6, 10, "CAABB"]]},
        {"type": "section", "text": "第二节"},
        {"type": "blank_answers", "items": [["56", "for"], ["57", "but/yet/while"]]},
        {"type": "part", "text": "第四部分 写作"},
        {"type": "writing_sample", "title": "第一节",
         "paragraphs": ["I hope this message finds you well.", "Yours,\nLi Hua"]},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?", help="答案 OCR Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 english.json")
    ap.add_argument("--stdout", action="store_true", help="打印 JSON 到 stdout")
    ap.add_argument("--schema", action="store_true", help="打印 IR schema 示例")
    ap.add_argument("--no-scripts", action="store_true", help="不保留听力原文")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not args.md:
        ap.error("需要提供 md 路径，或使用 --schema")

    src = Path(args.md)
    ir, report = parse_answer_markdown(
        src.read_text(encoding="utf-8"), source=src.name,
        with_scripts=not args.no_scripts)
    payload = json.dumps(ir, ensure_ascii=False, indent=2) + "\n"
    m = ir["meta"]
    print(f"[INFO] 清洗：{m['cleaning']}")
    for w in report.warnings[:10]:
        print(f"[WARN] {w}")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"[OK] {out}：{m['block_count']} 块 / "
              f"{m['answer_groups']} 答案组 / {m['blank_answers']} 语法填空 / "
              f"{m['writing_samples']} 范文")
    else:
        print(payload if args.stdout else
              f"[OK] {src.name}：{m['block_count']} 块（用 -o 写入或用 --stdout 打印）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
