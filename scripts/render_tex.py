#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_tex.py - Question IR → LaTeX 确定性渲染器

设计原则：LLM 只负责「理解」（题目切分、公式、表格、图片归属），
排版决策（编号、环境嵌套、tasks 列数、图片场景、答题空间、itemsep）
全部由本脚本按 rules/layout.yaml 的规则确定性地做出。

同一份 IR 渲染两次结果逐字节一致，因此可以单测、可以 diff、可以 eval。

用法:
  python scripts/render_tex.py paper.json -o 学生版.tex
  python scripts/render_tex.py paper.json -o out.tex --template answer
  python scripts/render_tex.py paper.json --stdout
  python scripts/render_tex.py --schema              # 打印 IR schema 示例

IR 结构见 --schema 输出或 docs/ir-schema.md。
极特殊的题目可用 "raw_tex" 字段直接给 LaTeX，跳过渲染（逃生舱）。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

TEMPLATE_FILES = {
    "gaokao": "gaokao-template.tex",
    "answer": "gaokao-answer-template.tex",
}

# ── 规则常量（与 rules/layout.yaml 一一对应，改动须同步 RULE 注释）──
SECTION_ITEMSEP = {            # TASKS-COL-001 邻近的结构默认值
    "choice_single": "0.3em",
    "choice_multi": "0.5em",
    "fill_blank": "0.8em",
}
SAQ_ITEMSEP_TABLE = {3: 2.25, 4: 2.0, 5: 1.75, 6: 1.35}   # PAGE-003
ANSWER_SPACE_CMD = {"compact": r"\answerc", "normal": r"\answern", "exam": r"\answere"}  # ANS-001
IMAGE_OPTION_WIDTH = "0.12"     # IMG-W-004
SINGLE_IMAGE_WIDTH = "0.30"     # IMG-W-002
MULTI_IMAGE_SPEC = {2: ("0.42", "3cm"), 3: ("0.28", "2.5cm")}  # IMG-W-003
SIDE_MINIPAGE = ("0.62", "0.30")  # IMG-SCENE-001 场景3

FRONT_MATTER = r"""\begin{{center}}
    \LARGE{{\textbf{{{title}}}}}
\end{{center}}

\vspace{{0.5em}}

\noindent\textbf{{注意事项}}：

1．答卷前，考生务必将自己的姓名、准考证号填写在答题卡上。

2．回答选择题时，选出每小题答案后，用铅笔把答题卡上对应题目的答案标号涂黑。

3．考试结束后，将本试卷和答题卡一并交回。

\vspace{{1em}}
"""


# ────────────────────────── 模板 ──────────────────────────

def load_preamble(template_key="gaokao"):
    path = TEMPLATES / TEMPLATE_FILES[template_key]
    text = path.read_text(encoding="utf-8")
    idx = text.find("\\begin{document}")
    if idx < 0:
        raise SystemExit(f"[FATAL] {path.name} 缺少 \\begin{{document}}")
    return text[:idx].rstrip() + "\n"


# ────────────────────────── 排版决策（纯函数，可单测）──────────────────────────

def _visible_len(text):
    """估算选项可见长度：剥掉 \\cmd{...} 形式的命令与其参数。"""
    import re
    return len(re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", "", text or ""))


def auto_tasks_cols(options):
    """TASKS-COL-001：按可见长度决定列数（不是「有 $ 就 2 列」）。"""
    if not options:
        return 4
    texts = [o.get("text", "") for o in options]
    has_image = any("\\includegraphics" in t or o.get("image") for t, o in zip(texts, options))
    avg_len = sum(_visible_len(t) for t in texts) / len(texts)

    if has_image:
        return 4 if avg_len < 80 else 2
    if avg_len > 25:
        return 2
    return 4


def auto_itemsep(saq_count, total_pages=4):
    """PAGE-003：解答题 itemsep 经验值（编译后由 auto_adjust.py 精调）。"""
    base = SAQ_ITEMSEP_TABLE.get(saq_count)
    if base is None:
        base = max(1.2, min(2.5, 10.0 / max(saq_count, 1)))
    if total_pages and total_pages != 4:
        base *= (total_pages / 4.0) ** 0.5
    return f"{max(1.2, min(2.5, base)):.2f}cm"


def decide_image_layout(question):
    """IMG-SCENE-001：返回场景名。

    multi      ≥2 图      → figure[H] + minipage 并排限高
    side       列表内单图  → minipage 左右并排（题干/子问 + 图）
    wrap       显式声明   → wrapfigure，必须置于 \\item 之前（仅限列表外场景）
    inline     显式声明   → 行内小图
    none       无图

    ⚠️ 实测（evals/fixtures/ir_geometry）：wrapfigure 放在 examenum 列表内
    会静默丢图——图片完全不渲染且不报错。因此「列表内单图」一律走 side，
    只有调用方明确声明 wrap（即图片确实位于 \\begin{examenum} 之前）时才用环绕。
    """
    layout = question.get("image_layout", "auto")
    images = question.get("images") or []
    if not images:
        return "none"
    if layout in ("inline", "wrap", "side", "multi"):
        return layout
    if len(images) >= 2:
        return "multi"
    return "side"


# ────────────────────────── 渲染片段 ──────────────────────────

def render_options(question, indent="    "):
    """渲染 tasks 选项块；选项本身是图片时按 IMG-W-004 给宽度。"""
    options = question.get("options") or []
    if not options:
        return ""

    cols = question.get("tasks_cols") or auto_tasks_cols(options)
    lines = [f"{indent}\\begin{{tasks}}({cols})"]
    for opt in options:
        body = opt.get("text", "").strip()
        if opt.get("image"):
            body = (f"\\includegraphics[width={IMAGE_OPTION_WIDTH}\\textwidth]"
                    f"{{{opt['image']}}}")
        lines.append(f"{indent}    \\task {body}")
    lines.append(f"{indent}\\end{{tasks}}")
    return "\n".join(lines)


def _figure_block(images, caption_prefix="", indent="    "):
    """IMG-W-003：并排图片，按张数分配宽度并强制限高。"""
    n = len(images)
    width, height = MULTI_IMAGE_SPEC.get(n, ("0.28", "2.5cm"))
    lines = [f"{indent}\\begin{{figure}}[H]", f"{indent}\\centering"]
    for idx, img in enumerate(images):
        if idx:
            lines.append(f"{indent}\\hfill")
        lines.append(f"{indent}\\begin{{minipage}}[t]{{{width}\\textwidth}}")
        lines.append(f"{indent}\\centering")
        lines.append(
            f"{indent}\\includegraphics[width=\\linewidth,height={height},"
            f"keepaspectratio]{{{img['file']}}}"
        )
        cap = img.get("caption") or f"{caption_prefix}{'①②③④⑤⑥'[idx] if idx < 6 else ''}"
        lines.append(f"{indent}\\caption*{{{cap}}}")
        lines.append(f"{indent}\\end{{minipage}}")
    lines.append(f"{indent}\\end{{figure}}")
    return "\n".join(lines)


def render_question(question, section, ctx, is_last_in_saq=False):
    """返回 (prefix, body)。prefix 必须在 \\item 之前（仅 wrap 场景使用）。"""
    if question.get("raw_tex"):
        return "", question["raw_tex"].rstrip()

    indent = "    "
    stem = question.get("stem", "").strip()
    points = question.get("points")
    head = f"（{points}分）{stem}" if points else stem

    if section["type"] == "fill_blank" and r"\blank" not in head:
        head = head.rstrip() + r" \blank."

    scene = decide_image_layout(question)
    images = question.get("images") or []
    prefix = ""

    if scene == "inline" and images:
        head += " " + " ".join(
            f"\\includegraphics[height=0.6em]{{{i['file']}}}" for i in images)
    elif scene == "wrap" and images:
        img = images[0]
        prefix = "\n".join([
            f"\\begin{{wrapfigure}}{{r}}{{{SINGLE_IMAGE_WIDTH}\\textwidth}}",
            r"\centering",
            f"\\includegraphics[width=\\linewidth]{{{img['file']}}}",
            f"\\caption*{{{img.get('caption', '')}}}",
            r"\end{wrapfigure}",
        ])

    lines = []

    if scene == "side" and images:
        img = images[0]
        left, right = SIDE_MINIPAGE
        sub = question.get("subquestions") or []
        if sub:
            left_body = [f"{indent}    \\begin{{examenum}}"]
            left_body += [f"{indent}        \\item {s}" for s in sub]
            left_body.append(f"{indent}    \\end{{examenum}}")
            lines.append(f"{indent}\\item {head}")
        else:
            left_body = [f"{indent}    {head}"]
            lines.append(f"{indent}\\item")
        lines.append(f"{indent}\\begin{{minipage}}[t]{{{left}\\textwidth}}")
        lines.extend(left_body)
        lines.append(f"{indent}\\end{{minipage}}")
        lines.append(f"{indent}\\hfill")
        lines.append(f"{indent}\\begin{{minipage}}[t]{{{right}\\textwidth}}")
        lines.append(f"{indent}\\vspace{{0pt}}")
        lines.append(f"{indent}\\centering")
        lines.append(f"{indent}\\includegraphics[width=\\linewidth]{{{img['file']}}}")
        lines.append(f"{indent}\\captionof{{figure}}{{{img.get('caption', '')}}}")
        lines.append(f"{indent}\\end{{minipage}}")
    else:
        lines.append(f"{indent}\\item {head}")
        if question.get("subquestions"):
            lines.append(f"{indent}\\begin{{examenum}}")
            lines.extend(f"{indent}    \\item {s}" for s in question["subquestions"])
            lines.append(f"{indent}\\end{{examenum}}")
        opt_block = render_options(question, indent)
        if opt_block:
            lines.append(opt_block)
        if scene == "multi":
            lines.append(_figure_block(images))

    if (section["type"] == "long_answer"
            and ctx["mode"] == "student"
            and not is_last_in_saq):
        lines.append(f"{indent}{ANSWER_SPACE_CMD[ctx['answer_space']]}")

    return prefix, "\n".join(lines)


def render_answer_block(question, indent="    "):
    """答案文档：\\daan → \\jieti → \\xijie / \\xiaoI.. 结构。"""
    lines = []
    if question.get("answer"):
        lines.append(f"{indent}\\daan{{{question['answer']}}}")
    if question.get("analysis"):
        lines.append(f"{indent}\\jieti {question['analysis']}")
    for i, detail in enumerate(question.get("sub_details") or [], 1):
        cmd = {1: r"\xiaoI", 2: r"\xiaoII", 3: r"\xiaoIII"}.get(i, r"\xiaoI")
        lines.append(f"{indent}{cmd} {detail}")
    if question.get("detail"):
        lines.append(f"{indent}\\xijie {question['detail']}")
    return "\n".join(lines)


def render_answer_options(question, indent="    "):
    options = question.get("options") or []
    if not options:
        return ""
    parts = []
    for opt in options:
        body = opt.get("text", "")
        if opt.get("image"):
            body = f"\\eqimg[0.15]{{{opt['image']}}}"
        parts.append(f"{opt.get('label', '')}.\\ {body}")
    return (f"{indent}\\begin{{flushleft}}\n{indent}    " + r"\quad ".join(parts)
            + f"\n{indent}\\end{{flushleft}}")


def render_section(section, ctx):
    stype = section["type"]
    is_long = stype == "long_answer"

    if ctx["is_answer"]:
        env, opts = "enumerate", []
        if ctx["first_list"]:
            ctx["first_list"] = False
        else:
            opts.append("resume")
    else:
        env = "examenum" if is_long else "enumerate"
        opts = []
        if section["_start"] != 1:
            opts.append(f"start={section['_start']}")
        itemsep = section.get("itemsep")
        if itemsep is None and is_long:
            itemsep = auto_itemsep(len(section["questions"]),
                                   ctx.get("total_pages") or 4)
        elif itemsep is None:
            itemsep = SECTION_ITEMSEP.get(stype)
        if itemsep:
            opts.append(f"itemsep={itemsep}")

    opt_str = f"[{', '.join(opts)}]" if opts else ""

    parts = []
    if section.get("heading"):
        parts.append(f"\\noindent\\textbf{{{section['heading']}}}\n" if not ctx["is_answer"]
                     else f"\\section*{{{section['heading']}}}")

    parts.append(f"\\begin{{{env}}}{opt_str}")

    questions = section["questions"]
    for idx, q in enumerate(questions):
        last_saq = is_long and idx == len(questions) - 1
        if ctx["is_answer"]:
            prefix = ""
            body = f"    \\item {q.get('stem', '').strip()}"
            if q.get("subquestions"):
                body += "\n    \\begin{enumerate}\n" + "\n".join(
                    f"        \\item {s}" for s in q["subquestions"]) + "\n    \\end{enumerate}"
            opt_block = render_answer_options(q)
            ans_block = render_answer_block(q)
            chunk = "\n".join(x for x in (body, opt_block, ans_block) if x)
        else:
            prefix, body = render_question(q, section, ctx, is_last_in_saq=last_saq)
            chunk = (prefix + "\n" if prefix else "") + body
        parts.append(chunk)

    parts.append(f"\\end{{{env}}}")
    return "\n\n".join(parts)


# ────────────────────────── 组装 ──────────────────────────

def assign_numbers(ir):
    """ENUM-START-001：按累计题量推导每个大题段的 start。"""
    counter = 0
    for sec in ir["sections"]:
        explicit = sec.get("start")
        sec["_start"] = explicit if explicit is not None else counter + 1
        counter = sec["_start"] - 1
        for q in sec["questions"]:
            counter += 1
            if not q.get("no"):
                q["no"] = counter
    return ir


def render_paper(ir):
    meta = ir.get("meta", {})
    template = meta.get("template", "gaokao")
    is_answer = template == "answer" or meta.get("is_answer", False)

    ir = assign_numbers(ir)

    ctx = {
        "is_answer": is_answer,
        "mode": "student",
        "answer_space": meta.get("answer_space", "normal"),
        "total_pages": meta.get("total_pages"),
        "first_list": True,
    }
    if ctx["answer_space"] not in ANSWER_SPACE_CMD:
        raise SystemExit(f"[FATAL] answer_space 非法: {ctx['answer_space']}"
                         f"（应为 {'/'.join(ANSWER_SPACE_CMD)}）")

    out = [load_preamble(template)]

    # graphicspath：图片目录名由 EXTRACT-001 决定
    images_dir = meta.get("images_dir")
    if images_dir and not is_answer:
        out.append(f"\\graphicspath{{{{{images_dir}/}}}}\n")

    out.append("\\begin{document}\n")

    if is_answer:
        out.append(f"\\begin{{center}}\n    {{\\Large\\textbf{{{meta.get('title', '参考答案')}}}}}"
                   f"\n    \\vspace{{0.5em}}\n    {{\\large\\textbf{{参考答案}}}}"
                   f"\n    \\vspace{{0.5em}}\n    \\hrule\n\\end{{center}}\n")
    elif meta.get("front_matter"):
        out.append(meta["front_matter"].rstrip() + "\n")
    else:
        out.append(FRONT_MATTER.format(title=meta.get("title", "数学试卷")) + "\n")

    for sec in ir["sections"]:
        out.append(render_section(sec, ctx) + "\n")

    out.append("\\end{document}\n")
    return "\n".join(out)


# ────────────────────────── CLI ──────────────────────────

SCHEMA_EXAMPLE = {
    "meta": {
        "title": "2026 年普通高等学校招生全国统一考试（模拟）",
        "template": "gaokao",
        "total_pages": 4,
        "images_dir": "media",
        "answer_space": "normal",
    },
    "sections": [
        {
            "heading": "一、选择题：本题共2小题，每小题5分，共10分。",
            "type": "choice_single",
            "questions": [
                {
                    "stem": "已知集合 $A=\\{x \\mid x^2-3x+2=0\\}$，则 $A \\cup B =$",
                    "options": [
                        {"label": "A", "text": "$\\{0\\}$"},
                        {"label": "B", "text": "$\\{0,1,2\\}$"},
                        {"label": "C", "text": "$\\{1,2\\}$"},
                        {"label": "D", "text": "$\\{0,1\\}$"},
                    ],
                }
            ],
        },
        {
            "heading": "四、解答题：本题共1小题，共12分。",
            "type": "long_answer",
            "questions": [
                {
                    "stem": "已知数列 $\\{a_n\\}$ 中，$a_1=3$，$a_{n+1}=2a_n+1$.",
                    "points": 12,
                    "subquestions": ["证明：数列 $\\{a_n+1\\}$ 是等比数列；",
                                     "求 $\\{a_n\\}$ 的前 $n$ 项和 $S_n$."],
                }
            ],
        },
    ],
}

FIELD_DOC = """
IR 字段说明
───────────
meta.title          试卷标题
meta.template       gaokao（学生版，默认）| answer（答案版）
meta.total_pages    试卷标注页数，用于推导 itemsep（PAGE-003）
meta.images_dir     图片目录名（EXTRACT-001：试题 media / 答案 Images-<文件名>）
meta.answer_space   compact | normal（默认）| exam（ANS-001）
meta.front_matter   可选，自定义标题区原始 LaTeX

section.heading     大题标题（含题量与分值）
section.type        choice_single | choice_multi | fill_blank | long_answer
section.start       可选，显式指定起始编号；省略则按累计题量自动推导
section.itemsep     可选，显式指定；省略则按 type 或 PAGE-003 推导

question.no         可选，题号（渲染时自动补全）
question.stem       题干（LaTeX）
question.points     分值，会渲染成 （N分）
question.options    [{label, text, image}]，text 含图片时用 image 字段
question.subquestions 子问列表（自动包 examenum）
question.images     [{file, caption}]，布局由 IMG-SCENE-001 自动决定
question.image_layout  auto（默认）| wrap | side | multi | inline
question.raw_tex    逃生舱：非空时直接输出该 LaTeX，跳过所有渲染

答案版额外字段（template=answer）
question.answer     → \\daan{...}
question.analysis   → \\jieti ...
question.detail     → \\xijie ...
question.sub_details → \\xiaoI / \\xiaoII / \\xiaoIII
"""


def main():
    ap = argparse.ArgumentParser(description="Question IR → LaTeX 渲染器")
    ap.add_argument("ir", nargs="?", help="paper.json 路径")
    ap.add_argument("-o", "--output", help="输出 .tex 路径")
    ap.add_argument("--template", choices=list(TEMPLATE_FILES), help="覆盖 meta.template")
    ap.add_argument("--stdout", action="store_true", help="输出到标准输出")
    ap.add_argument("--schema", action="store_true", help="打印 IR schema 示例")
    ap.add_argument("--validate", action="store_true", help="渲染后立即跑 validate_tex")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        print(FIELD_DOC)
        return 0

    if not args.ir:
        ap.error("需要 paper.json，或用 --schema 查看格式")

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    if args.template:
        ir.setdefault("meta", {})["template"] = args.template

    tex = render_paper(ir)

    if args.stdout or not args.output:
        print(tex)
    else:
        Path(args.output).write_text(tex, encoding="utf-8")
        print(f"[OK] {args.output}")

    if args.validate and args.output:
        sys.path.insert(0, str(ROOT / "scripts"))
        from validate_tex import TexValidator
        is_answer = ir.get("meta", {}).get("template") == "answer"
        report = TexValidator(args.output, is_answer=is_answer).validate()
        print(f"[{'PASS' if report['passed'] else 'FAIL'}] "
              f"{report['error_count']} error / {report['warning_count']} warning")
        for e in report["errors"]:
            print(f"  [{e['rule_id']}] {e['message']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
