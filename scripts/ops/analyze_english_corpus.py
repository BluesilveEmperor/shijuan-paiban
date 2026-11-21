#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_english_corpus.py — 从 52 份英语基准样本沉淀结构与规则

只读源样本（manifest + md/tex + _报告.txt + _质检.txt），产出机器可读经验库
``evals/fixtures_english/corpus_analysis.json``：每卷特征、异常标记、汇总统计与规则清单。

用法::

    python scripts/ops/analyze_english_corpus.py            # 生成 JSON + 打印摘要
    python scripts/ops/analyze_english_corpus.py --check    # 额外跑已沉淀的不变量门禁
    python scripts/ops/analyze_english_corpus.py --stdout   # 只打印，不写文件

只依赖标准库。规则 ID 前缀 EC（English Corpus），与 rules/layout.yaml 的规则域互不冲突。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "evals" / "fixtures_english"
MANIFEST = FIX / "manifest.json"
DEFAULT_OUT = FIX / "corpus_analysis.json"

REPORT_RE = re.compile(
    r"^\s*(.+?)\s+题\s+(\d+)\s+选择\s+(\d+)\s+完形\s+(\d+)\s+"
    r"页\s+(\d+)\s*编译\s*(\S+)")
QA_RE = re.compile(
    r"^\s*(\d+)_(\S+)\s+题\s+(\d+)\s+完形\s+(\d+)\s+七选\s+(\d+)\s+"
    r"范围\s+(\d+)\s*-\s*(\d+)\s+断档:(.*)$")

WATERMARK_RE = re.compile(r"IAI English|微信公众号")
GARBAGE_RE = re.compile(r"ladnepen")


def canon_part(title: str) -> str:
    """把 parttitle 标点/空格变体归一到四大板块 key。"""
    s = title.replace("（", "(").replace("）", ")").replace(" ", "")
    if "听力" in s:
        return "listening"
    if "阅读" in s:
        return "reading"
    if "语言运用" in s or "语言知识运用" in s:
        return "language"
    if "写作" in s:
        return "writing"
    return "other:" + s


def _parse_reports() -> dict:
    out = {}
    path = FIX / "_报告.txt"
    if path.is_file():
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = REPORT_RE.match(line)
            if m:
                out[idx] = {
                    "exam": m.group(1).strip(), "questions": int(m.group(2)),
                    "choices": int(m.group(3)), "cloze": int(m.group(4)),
                    "pages": int(m.group(5)), "compile": m.group(6),
                }
    return out


def _parse_qa() -> dict:
    out = {}
    path = FIX / "_质检.txt"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = QA_RE.match(line)
            if m:
                out[int(m.group(1))] = {
                    "questions": int(m.group(3)), "cloze": int(m.group(4)),
                    "seven_of_five": int(m.group(5)),
                    "range": [int(m.group(6)), int(m.group(7))],
                    "gaps": [int(x) for x in re.findall(r"\d+", m.group(8))],
                }
    return out


def analyze_paper(meta: dict, report: dict, qa: dict) -> dict:
    """提取单卷特征与异常标记。"""
    md_path = FIX / meta["md"]
    tex_path = FIX / meta["tex"]
    md = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    tex = tex_path.read_text(encoding="utf-8") if tex_path.is_file() else ""

    questions = [int(x) for x in re.findall(r"\\question\{(\d+)\.", tex)]
    examples = len(re.findall(r"\\question\{例：", tex))   # 听力例题，无题号（EC-016）
    blanks = [int(x) for x in re.findall(r"\\blanknum\{(\d+)\}", tex)]
    choices = Counter(re.findall(r"\\begin\{choices\}(\(\d\))?", tex))
    choice_items = {}
    for m in re.finditer(r"\\begin\{choices\}(\(\d\))?\n?(.*?)\\end\{choices\}", tex, re.S):
        key = m.group(1) or ""
        n = len(re.findall(r"\\item", m.group(2)))
        choice_items.setdefault(key, Counter())[n] += 1

    parts = re.findall(r"\\parttitle\{([^}]*)\}", tex)
    sections = re.findall(r"\\sectitle\{([^}]*)\}", tex)
    writing = re.findall(r"\\writinglines\{(\d+)\}", tex)
    md_images = len(re.findall(r"!\[", md))
    tex_images = len(re.findall(r"\\includegraphics", tex))
    missing = sorted(set(range(36, 66)) - set(blanks))
    dup = sorted(n for n, c in Counter(blanks).items() if c > 1)
    start = questions[0] if questions else None
    variant = "full" if start == 1 else ("no_listening" if start == 21 else "unknown")
    part_canon = [canon_part(x) for x in parts]
    env_pairs = {
        env: (len(re.findall(r"\\begin\{" + env + r"\}", tex)),
              len(re.findall(r"\\end\{" + env + r"\}", tex)))
        for env in ("document", "choices", "cloze", "notice", "tabular")
    }

    flags = []
    if variant == "no_listening":
        flags.append("no_listening")
    elif variant == "unknown":
        flags.append("unknown_question_start")
    if examples:
        flags.append("listening_example")
    if "\\begin{notice}" not in tex:
        flags.append("notice_missing")
    if WATERMARK_RE.search(tex):
        flags.append("watermark_leaked_into_sectitle")
    if GARBAGE_RE.search(tex):
        flags.append("garbage_token_in_sectitle")
    if any("\\blanknum" in s or len(s) > 80 for s in sections):
        flags.append("body_text_leaked_into_sectitle")
    if missing:
        flags.append("blanknum_missing")
    if dup:
        flags.append("blanknum_duplicate")
    if len(re.findall(r"\\cz\{", tex)) < 15:
        flags.append("cloze_rows_short")
    if choices.get("(3)", 0) not in (0, 20) or choices.get("(2)", 0) != 15 \
            or choices.get("(1)", 0) != 1:
        flags.append("choices_count_drift")
    if writing != ["8", "8"]:
        flags.append("writinglines_anomaly")
    if md_images and not tex_images:
        flags.append("image_loss")
    if re.search(r"<table", md):
        flags.append("html_table")
    if report.get("pages") == 0:
        flags.append("page_count_unavailable")
    if any(canon_part(p).startswith("other:") for p in parts):
        flags.append("unknown_parttitle")

    return {
        "index": meta["index"], "exam": meta["exam"],
        "md": meta["md"], "tex": meta["tex"],
        "source_pdf": meta.get("source_pdf"),
        "source_answer_pdf": meta.get("source_answer_pdf"),
        "variant": variant,
        "documentclass_ok": "\\documentclass{英语试卷}" in tex,
        "env_pairs": {k: list(v) for k, v in env_pairs.items()},
        "question_numbers": questions,
        "example_count": examples,
        "blanknum_numbers": blanks,
        "blanknum_missing": missing,
        "blanknum_duplicate": dup,
        "choices": {k: v for k, v in sorted(choices.items())},
        "choice_items": {k: dict(v) for k, v in sorted(choice_items.items())},
        "cz_count": len(re.findall(r"\\cz\{", tex)),
        "passagelabel_count": len(re.findall(r"\\passagelabel", tex)),
        "tabular_count": env_pairs["tabular"][0],
        "notice_count": env_pairs["notice"][0],
        "writinglines": writing,
        "parttitles": parts,
        "parttitle_canon": part_canon,
        "sectitles": sections,
        "par_count": tex.count("\\par"),
        "md_markers": {
            "images": md_images,
            "html_tables": len(re.findall(r"<table", md)),
            "escaped_blanks": len(re.findall(r"\\_+\d+\\_+", md)),
            "watermark_hits": len(WATERMARK_RE.findall(md)),
            "garbage_tokens": len(GARBAGE_RE.findall(md)),
            "headings": dict(Counter(re.findall(r"^(#+)", md, re.M))),
        },
        "tex_images": tex_images,
        "report": report, "qa": qa,
        "flags": flags,
    }


def aggregate(papers: list) -> dict:
    """汇总统计、规则清单与异常卷索引。"""
    def dist(key):
        return dict(Counter(str(p[key]) for p in papers).most_common())

    part_variants = Counter(p for paper in papers for p in paper["parttitles"])
    sec_variants = Counter(s for paper in papers for s in paper["sectitles"])
    flag_papers = {f: [p["index"] for p in papers if f in p["flags"]]
                   for f in sorted({f for p in papers for f in p["flags"]})}
    total_par = sum(p["par_count"] for p in papers)
    full = [p for p in papers if p["variant"] == "full"]
    silent = [p for p in papers if p["variant"] == "no_listening"]
    complete_cover = sum(1 for p in papers
                         if not p["blanknum_missing"] and not p["blanknum_duplicate"])

    summary = {
        "papers": len(papers),
        "variants": {"full": len(full), "no_listening": len(silent)},
        "question_start": dist("variant"),
        "question_count": dict(Counter(len(p["question_numbers"]) for p in papers).most_common()),
        "blanknum_distinct_count": dict(Counter(len(set(p["blanknum_numbers"]))
                                                for p in papers).most_common()),
        "blanknum_full_coverage": complete_cover,
        "choices_pattern": dict(Counter(
            f"{p['choices'].get('(3)', 0)}/{p['choices'].get('(2)', 0)}/"
            f"{p['choices'].get('(1)', 0)}" for p in papers).most_common()),
        "cz_count": dict(Counter(p["cz_count"] for p in papers).most_common()),
        "writinglines": dict(Counter(str(p["writinglines"]) for p in papers).most_common()),
        "notice_count": dict(Counter(p["notice_count"] for p in papers).most_common()),
        "passagelabel_count": dict(Counter(p["passagelabel_count"] for p in papers).most_common()),
        "tabular_count": dict(Counter(p["tabular_count"] for p in papers).most_common()),
        "md_images_total": sum(p["md_markers"]["images"] for p in papers),
        "md_image_papers": flag_papers.get("image_loss", []),
        "md_html_table_papers": len(flag_papers.get("html_table", [])),
        "md_escaped_blanks_total": sum(p["md_markers"]["escaped_blanks"] for p in papers),
        "watermark_papers": flag_papers.get("watermark_leaked_into_sectitle", []),
        "garbage_token_papers": flag_papers.get("garbage_token_in_sectitle", []),
        "leaked_body_in_sectitle_papers": flag_papers.get("body_text_leaked_into_sectitle", []),
        "par_total": total_par,
        "report_pages_zero": flag_papers.get("page_count_unavailable", []),
        "example_papers": flag_papers.get("listening_example", []),
        "example_total": sum(p["example_count"] for p in papers),
        "parttitle_variants": dict(part_variants.most_common()),
        "sectitle_variants_top15": dict(sec_variants.most_common(15)),
    }

    rules = [
        {
            "id": "EC-001", "title": "卷式二分",
            "statement": "卷分两类：完整卷 4 板块 / 题号 1-35；无听力卷 3 板块 / 题号 21-35（注意事项注明「笔试不考听力」）。",
            "evidence": f"full={len(full)}, no_listening={len(silent)}",
            "implication": "IR 顶层先判定 variant；无听力卷不得凭空补 1-20 题。",
        },
        {
            "id": "EC-002", "title": "题号地图",
            "statement": "question 只覆盖 1-35（或 21-35）；36-65 全部由 \\blanknum 承载；\\cz{41..55} 承载完形选项；66/67 写作不编号。",
            "evidence": "question 起号 1/21；blanknum 取值域 36-65；cz 每卷 13-16 行",
            "implication": "渲染器按题号段分派块类型，不要用一个计数器贯穿全文。",
        },
        {
            "id": "EC-003", "title": "选项列数由小节决定",
            "statement": "choices(3)=听力（含无题号例题）、choices(2)=阅读、choices(1)=七选五；数量会漂移，不能靠数量反推题型。",
            "evidence": ("choices 模式分布 " + str(summary["choices_pattern"])
                         + f"；听力例题 {summary['example_total']} 处"),
            "implication": "md→IR 时先读 parttitle/sectitle 定 section，再按选项数分派环境。",
        },
        {
            "id": "EC-004", "title": "七选五断档是正常的",
            "statement": "36-40 嵌在短文里的 \\blanknum，不是 \\question；质检里的「断档 36-40」是正常现象。",
            "evidence": f"QA 断档 36-40 出现于 {len(papers)} 卷；blanknum 起始号均为 36",
            "implication": "校验器对 36-40 缺 \\question 不得报错；只检查 \\blanknum。",
        },
        {
            "id": "EC-005", "title": "完形题号双通道",
            "statement": "完形题号同时可出现在 \\cz{41..55} 与短文 \\blanknum{41..55}；后者缺失不代表漏题。",
            "evidence": "cz 行数分布 " + str(summary["cz_count"]),
            "implication": "以 \\cz 为完形题量来源，\\blanknum 只作补充；缺 41-55 仅告警。",
        },
        {
            "id": "EC-006", "title": "填空缺号常态化",
            "statement": "36-65 完整覆盖仅部分卷；OCR 会漏号或重复号，不得按「必须齐全」硬断言。",
            "evidence": f"完整覆盖 {complete_cover}/{len(papers)}；有缺失 {len(flag_papers.get('blanknum_missing', []))} 卷；有重复 {len(flag_papers.get('blanknum_duplicate', []))} 卷",
            "implication": "缺号/重号记 WARN 并交人工对照原卷，禁止自动补题。",
        },
        {
            "id": "EC-007", "title": "写作区形态",
            "statement": "写作两节通常是两次 \\writinglines{8}；存在缺失、单块或拆成多块的 OCR 变体。",
            "evidence": "形态分布 " + str(summary["writinglines"]),
            "implication": "IR 用 writing 块记录「节次 + 行数」，渲染时归一为两次 8 行。",
        },
        {
            "id": "EC-008", "title": "表格来自 HTML table",
            "statement": "部分卷含两列 tabular（第二列 p{} 固定宽度 + 竖线），源 markdown 是 HTML <table>；跨栏宽表需人工调列宽。",
            "evidence": f"含 tabular {sum(1 for p in papers if p['tabular_count'])} 卷；md 含 <table> {summary['md_html_table_papers']} 卷",
            "implication": "保留 raw_tex 逃生舱；表格不要强行转成 IR 普通块。",
        },
        {
            "id": "EC-009", "title": "图片在转排中丢失",
            "statement": "源 md 有图片引用，但成品 tex 完全没有 \\includegraphics；这批样本不能作为图片回归基准。",
            "evidence": f"md 图片 {summary['md_images_total']} 处 / {len(summary['md_image_papers'])} 卷；tex 图片 0",
            "implication": "补图片提取 + \\includegraphics 规则后再把图片卷纳入基准；当前须标记 image_loss。",
        },
        {
            "id": "EC-010", "title": "OCR 噪声会渗入标题",
            "statement": "公众号水印、「ladnepen」等 OCR 垃圾串以及整段正文被吸入 \\sectitle，转换时必须清洗。",
            "evidence": f"水印 {len(summary['watermark_papers'])} 卷；垃圾串 {len(summary['garbage_token_papers'])} 卷；正文泄漏 {len(summary['leaked_body_in_sectitle_papers'])} 卷",
            "implication": "在 md→IR 前加清洗层；sectitle 只允许「第X节（...）」结构，超长即判异常。",
        },
        {
            "id": "EC-011", "title": "标题标点变体需归一",
            "statement": "parttitle 存在全/半角括号、空格有无、「语言运用/语言知识运用」等写法；sectitle 混用「：」「；」。",
            "evidence": f"parttitle 变体 {len(summary['parttitle_variants'])} 种，sectitle 变体 {len(sec_variants)} 种",
            "implication": "按 canon_part() 归一后再匹配板块；不要把原始字符串当枚举值。",
        },
        {
            "id": "EC-012", "title": "\\par 洪流不是内容",
            "statement": "成品 tex 大量使用 \\par 逐行断开（源 md 每行一条），属于转换副产物。",
            "evidence": f"共 {total_par} 个 \\par，约 {total_par // max(len(papers), 1)} 个/卷",
            "implication": "IR 不保留 \\par；渲染器按段落重新生成，避免把换行写进结构化数据。",
        },
        {
            "id": "EC-013", "title": "报告页数字段部分失效",
            "statement": "_报告.txt 后 22 卷页数为 0（pdfinfo 失败），不能作为页数断言依据。",
            "evidence": f"页数为 0 的卷 {len(summary['report_pages_zero'])} 个",
            "implication": "页数门禁改用「重新编译 + pdfinfo」实时取，不读陈旧报告。",
        },
        {
            "id": "EC-014", "title": "本批样本无答案卷",
            "statement": "52 套只有试题；答案 PDF 仅在外部题库，答案模式只有模板与冒烟测试，没有 52 份答案基准。",
            "evidence": "manifest 的 source_answer_pdf 有路径，fixtures 无答案 md/tex",
            "implication": "答案卷流水线需另起一批样本，不能拿试题 tex 加 [answers] 冒充。",
        },
        {
            "id": "EC-015", "title": "md/tex 文件名不可互推",
            "statement": "md 保留考试名中的「+」和空格，tex 统一替换为「_」；映射以 manifest 为权威。",
            "evidence": "如 11_2412  3+3+3.md → 11_2412_3_3_3.tex",
            "implication": "批量脚本读 manifest，禁止字符串替换猜文件名。",
        },
        {
            "id": "EC-016", "title": "听力例题无题号",
            "statement": "部分卷听力第一节前有 `\\question{例：How much is the shirt?}` + choices(3) 的例题，不计入正式题号。",
            "evidence": f"例题 {summary['example_total']} 卷：" + str(summary["example_papers"]),
            "implication": "题号校验跳过「例：」开头的 question；题量统计可含例题，题号集合不可含。",
        },
    ]
    return {
        "subject": "english",
        "version": "1.0",
        "source": "evals/fixtures_english/manifest.json + md/tex + _报告.txt + _质检.txt",
        "generator": "scripts/ops/analyze_english_corpus.py",
        "summary": summary,
        "rules": rules,
        "flag_papers": flag_papers,
        "papers": papers,
    }


def check_invariants(papers: list) -> list:
    """返回已沉淀不变量的违背项列表（空表示全部通过）。"""
    fails = []
    if len(papers) != 52:
        fails.append(f"样本数应为 52，实际 {len(papers)}")
    for p in papers:
        tag = f"#{p['index']} {p['exam']}"
        if not p["documentclass_ok"]:
            fails.append(f"{tag} 文档类不是 英语试卷")
        for env, (b, e) in p["env_pairs"].items():
            if b != e:
                fails.append(f"{tag} {env} 环境不配对 {b}/{e}")
        start = p["question_numbers"][0] if p["question_numbers"] else None
        if start not in (1, 21):
            fails.append(f"{tag} question 起号异常 {start}")
        expected_canon = ["listening", "reading", "language", "writing"] \
            if start == 1 else ["reading", "language", "writing"]
        if p["parttitle_canon"] != expected_canon:
            fails.append(f"{tag} 板块序列异常 {p['parttitle_canon']}")
        if not (15 <= len(p["question_numbers"]) <= 35):
            fails.append(f"{tag} question 数量异常 {len(p['question_numbers'])}")
        blanks = p["blanknum_numbers"]
        if blanks and (min(blanks) < 36 or max(blanks) > 65):
            fails.append(f"{tag} blanknum 超出 36-65")
        if len(set(blanks)) < 15:
            fails.append(f"{tag} blanknum 去重后不足 15 个")
        if p["cz_count"] < 13:
            fails.append(f"{tag} cz 行数过少 {p['cz_count']}")
        if not p["choices"].get("(2)") or not p["choices"].get("(1)"):
            fails.append(f"{tag} 缺阅读/七选五选项块")
        if p["report"] and p["report"].get("compile") != "2/2":
            fails.append(f"{tag} 报告编译状态异常 {p['report'].get('compile')}")
    return fails


def load_papers() -> list:
    """读取样本并逐卷分析；供本脚本与回归测试共用。"""
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reports, qa = _parse_reports(), _parse_qa()
    return [analyze_paper(p, reports.get(p["index"], {}), qa.get(p["index"], {}))
            for p in meta["papers"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=str(DEFAULT_OUT), help="输出 JSON 路径")
    ap.add_argument("--check", action="store_true", help="跑已沉淀不变量门禁")
    ap.add_argument("--stdout", action="store_true", help="只打印摘要，不写文件")
    args = ap.parse_args()

    papers = load_papers()
    data = aggregate(papers)
    s = data["summary"]
    print(f"样本 {s['papers']} 套 | 完整卷 {s['variants']['full']} / 无听力 {s['variants']['no_listening']}")
    print(f"填空完整覆盖 {s['blanknum_full_coverage']}/{s['papers']} | "
          f"图片丢失 {len(s['md_image_papers'])} 卷 | 水印 {len(s['watermark_papers'])} 卷 | "
          f"\\par 总数 {s['par_total']}")
    print(f"规则 EC-001..EC-{len(data['rules']):03d} 共 {len(data['rules'])} 条")

    if not args.stdout:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] 已写入 {out.relative_to(ROOT)}")

    if args.check:
        fails = check_invariants(papers)
        if fails:
            print(f"[FAIL] {len(fails)} 条不变量违背：")
            for f in fails[:20]:
                print("  -", f)
            return 1
        print("[OK] 不变量门禁全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
