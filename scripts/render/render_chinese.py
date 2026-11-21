#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_chinese.py — 语文试卷 IR（块流）→ LaTeX 确定性渲染器

与数学 `render_tex.py` 的区别：

    数学  层级结构（sections → questions）+ 排版决策（编号 / tasks 列数 / 答题空间）
    语文  线性块流（materials 与 questions 交错）+ 结构保真（题号手写、选项纵排、留白固定）

因此本渲染器**不做排版决策**，只把 block 直译成 ywexam 宏包命令；
唯一带判断的是校验（题号是否连续、选择题是否恰好 4 项），发现问题只告警不擅改。

输出模板契约见 `templates/chinese/ywexam.sty`。

用法::

    python scripts/render/render_chinese.py chinese.json -o chinese-shiti.tex
    python scripts/render/render_chinese.py chinese.json --stdout
    python scripts/render/render_chinese.py --schema          # 打印 IR 示例与字段说明
    python scripts/render/render_chinese.py chinese.json -o out.tex --copy-sty
                                                     # 顺带把 ywexam.sty 拷到输出目录
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # ACCESS-001：技能目录只读，不生成 __pycache__

ROOT = Path(__file__).resolve().parents[2]
STY_DIR = ROOT / "templates" / "chinese"
STY_NAME = "ywexam.sty"

DEFAULT_SPACE = "2.2em"      # 主观题答题留白（6 套成品卷统一值）
CHOICE_COUNT = 4             # 语文选择题恒为四选一
INLINE_MAXLEN = 8            # choices_layout=auto：四选项可见长度都 ≤8 才横排
DEFAULT_FIG_WIDTH = "0.5"    # 语文配图默认宽度（相对 \linewidth）
# 「题干后紧跟这些块」时，题干后的留白会把题干与内容隔开（见 docs/chinese-branch.md）
CONTENT_BLOCKS = {"para", "duanju", "material", "note", "poem", "heading",
                  "figure", "raw"}

PREAMBLE = r"""% !TEX program = xelatex
\documentclass[11pt,a4paper]{{ctexart}}
\usepackage{{{sty}}}
\usepackage{{graphicx}}% ywexam 未加载 graphicx；语文卷偶有配图（如对照图）
\usepackage{{amssymb}}% OCR 偶尔输出 \leqslant 等符号（ywexam 只加载 amsmath）
{pkgs}% IR meta.extra_packages 带来的额外宏包（multirow 等）
% \textcircled 在部分环境下会回落到西文字体（缺带圈数字字形），强制用中文宋体
\RenewDocumentCommand{{\xq}}{{m}}{{{{\CJKfamily{{rm}}\textcircled{{#1}}}}}}
{extra}
\begin{{document}}
"""


class RenderReport:
    """收集渲染过程中的告警（题号不连续、选项数异常等）。

    warnings  会让回归测试失败的问题（结构/内容级）
    hints     建议级：不改也能编译，但排版很可能不对（如题干留白隔断内容）
    """

    def __init__(self):
        self.warnings = []
        self.hints = []

    def warn(self, msg):
        self.warnings.append(msg)

    def hint(self, msg):
        self.hints.append(msg)


# ────────────────────────── 块渲染 ──────────────────────────

CIRCLED_RE = re.compile(r"[\u2460-\u2473]")   # ①-⑳


def _circled_sub(s):
    return CIRCLED_RE.sub(
        lambda m: "\\xq{%d}" % (ord(m.group(0)) - 0x2460 + 1), s)


def _esc(v):
    """IR 里的文本已是 LaTeX 片段（不做转义），只补一件安全替换：

    裸圈号 ①-⑳ → \\xq{n}。西文字体与部分楷体没有该码位，字会**静默消失**
    （日志只报 Missing character），而 \\xq 用 textcircled 绘制，永远有字形。
    md2chinese 已做同样转换；这里兜住手工写的 IR。
    """
    if v is None:
        return ""
    return _circled_sub(str(v))


def _raw(v):
    """逃生舱文本：原样输出，不做任何替换。"""
    return "" if v is None else str(v)


def _material_block(b):
    lines = []
    label = b.get("label")
    if label:
        lines.append(f"\\material{{{label}}}")
    paras = b.get("text") or []
    if isinstance(paras, str):
        paras = [paras]
    if paras:
        lines.append("\\begin{materialtext}")
        lines.append("\n\n".join(_esc(p) for p in paras))
        lines.append("\\end{materialtext}")
    src = b.get("source")
    if src:
        lines.append(f"\\begin{{flushright}}{src}\\end{{flushright}}")
    return "\n".join(lines)


def _heading_block(b):
    """篇名 + 作者：center 块，篇名加粗，作者换行。"""
    lines = ["\\begin{center}"]
    lines.append(f"{{\\bfseries {b.get('text','')}}}\\par")
    if b.get("byline"):
        lines.append("\\vspace{0.15em}" + _esc(b["byline"]))
    lines.append("\\end{center}")
    return "\n".join(lines)


def _poem_block(b):
    body = "\\\\\n".join(_esc(x) for x in (b.get("lines") or []))
    return "\\begin{poem}\n" + body + "\n\\end{poem}"


def _visible_len(text):
    """选项的「可见字符数」：忽略 $…$、\\cmd、花括号与空白。"""
    t = re.sub(r"\$[^$]*\$", "X", str(text))
    t = re.sub(r"\\[a-zA-Z]+\*?", "X", t)
    return len(re.sub(r"[\s{}\\$~^_]", "", t))


def _choices_layout(b):
    """选项排版：stack（纵排，默认）/ inline（tasks 横排）/ auto。

    inline 的判据来自 TASKS-COL-001：简短选项（1~3 字）在原卷里是一行四列，
    纵排会白占 4 行、整卷可能多出一页。
    """
    lay = str(b.get("choices_layout") or "").strip().lower()
    if lay in ("inline", "row", "tasks", "horizontal"):
        return "inline"
    if lay in ("stack", "vertical", "choices"):
        return "stack"
    if lay == "auto":
        opts = b.get("options") or []
        longest = max((_visible_len(o) for o in opts), default=999)
        return "inline" if longest <= INLINE_MAXLEN else "stack"
    return "stack"


def _choices_block(options, report, qno, layout="stack", cols=None):
    opts = options or []
    if len(opts) != CHOICE_COUNT:
        report.warn(f"第 {qno} 题选择题有 {len(opts)} 个选项（应为 {CHOICE_COUNT}）")
    if layout == "inline":
        head = "\\begin{choicesinline}" + (f"[{cols}]" if cols else "")
        # tasks 环境的条目命令是 \task，不是 \item
        lines = [head]
        lines.extend(f"\\task {_esc(o)}" for o in opts)
        lines.append("\\end{choicesinline}")
        return "\n".join(lines)
    lines = ["\\begin{choices}"]
    lines.extend(f"\\item {_esc(o)}" for o in opts)
    lines.append("\\end{choices}")
    return "\n".join(lines)


def _fig_width(val):
    """图片宽度：0.44 / "0.44" / "0.44\\linewidth" / "8cm" 都接受。"""
    if val is None or val == "":
        val = DEFAULT_FIG_WIDTH
    if isinstance(val, (int, float)):
        return f"{val}\\linewidth"
    s = str(val).strip()
    if re.fullmatch(r"\d*\.?\d+", s):
        return f"{s}\\linewidth"
    return s


def _figure_block(b):
    """配图块（语文卷的地图、示意图、对照图）。

    图片是行内浮动对象，宽高放不下时整体被推到下一页，会与题干/选项分页隔开；
    处理办法是**缩小 width**（0.72 → 0.52 → 0.44 逐档试），而不是加 \\newpage。
    keep=true 时在图片前加 \\nopagebreak，尽量与上一段落同页。
    """
    path = b.get("path") or b.get("src") or ""
    lines = []
    if b.get("keep"):
        lines.append("\\nopagebreak[4]")
    lines.append("\\begin{center}")
    lines.append(f"\\includegraphics[width={_fig_width(b.get('width'))}]{{{path}}}")
    if b.get("caption"):
        lines.append("\\\\[0.2em]" + "{\\small " + _esc(b["caption"]) + "}")
    lines.append("\\end{center}")
    return "\n".join(lines)


def _space_cmd(val):
    """留白量：True → 默认 2.2em；字符串 → 原样用；其他 → 默认。"""
    if isinstance(val, str) and val.strip():
        return val.strip()
    return DEFAULT_SPACE


def _question_block(b, report):
    no = b.get("no")
    stem = _esc(b.get("stem", ""))
    if no is None:
        report.warn(f"题目缺少 no：{stem[:24]}…")
        no = ""
    lines = [f"\\question{{{no}}}{{{stem}}}"]
    options = b.get("options") or []
    subs = b.get("subs") or []

    if options:
        lines.append(_choices_block(options, report, no,
                                    layout=_choices_layout(b),
                                    cols=b.get("choices_cols")))

    for sub in subs:
        lines.append(_esc(sub))
        if b.get("sub_space", True):
            lines.append(f"\\par\\vspace{{{_space_cmd(b.get('space'))}}}")

    # 无选项、无小问的主观题：题后留白
    if not options and not subs and b.get("space"):
        lines.append(f"\\par\\vspace{{{_space_cmd(b.get('space'))}}}")
    return "\n".join(lines)


def _subans_block(b):
    """子项答案。text 为字符串时单行；为列表时**拆成多个 \\subans**。

    \\subans 的两参数是 m 型（不能含 \\par / \\\\ / 空行），想在一条答案里
    分行（如「示例一：…」「示例二：…」）只能拆块 —— 第一块带 label，
    其余 label 传空串，不重复题号/前缀。
    """
    text = b.get("text")
    label = b.get("label")
    if not isinstance(text, list):
        return f"\\subans{{{_esc(label)}}}{{{_esc(text)}}}"
    if isinstance(label, list):
        labels = list(label)
    else:
        labels = [_esc(label)] + [""] * (len(text) - 1)
    return "\n".join(f"\\subans{{{_esc(lab)}}}{{{_esc(part)}}}"
                     for lab, part in zip(labels, text))


def render_block(b, report):
    t = b.get("type")
    if t == "sechead":
        return f"\\sechead{{{_esc(b.get('text'))}}}"
    if t == "subsechead":
        return f"\\subsechead{{{_esc(b.get('text'))}}}"
    if t in ("lead", "para"):
        return _esc(b.get("text"))
    if t == "material":
        return _material_block(b)
    if t == "heading":
        return _heading_block(b)
    if t == "poem":
        return _poem_block(b)
    if t == "figure":
        return _figure_block(b)
    if t == "duanju":
        return f"\\duanju{{{_esc(b.get('text'))}}}"
    if t == "note":
        return _esc(b.get("text"))
    if t == "question":
        return _question_block(b, report)
    if t == "ans":
        return f"\\ans{{{b.get('no','')}}}{{{_esc(b.get('text'))}}}"
    if t == "subans":
        return _subans_block(b)
    if t == "scorenote":
        return f"\\scorenote{{{_esc(b.get('text'))}}}"
    if t == "translation":
        return ("\\translabel{%s}\n\\begin{translation}\n%s\n\\end{translation}"
                % (_esc(b.get("label", "")), _esc(b.get("text"))))
    if t == "raw":
        return _raw(b.get("tex")).rstrip()
    report.warn(f"未知 block 类型 {t!r}，已按 raw 处理")
    return _raw(b.get("tex")).rstrip()


# ────────────────────────── 组装 ──────────────────────────

def check_numbering(blocks, report):
    """题号完整性：语文题号跨节连续，手写最容易错。

    按**排序后**比较——答案卷常把选择题答案汇总在开头（1、2、6、7…），
    正文再按主观题顺序排，原顺序本就不连续，只要集合完整即可。
    """
    nos = [b.get("no") for b in blocks if b.get("type") in ("question", "ans")]
    nos = [n for n in nos if isinstance(n, int)]
    if not nos:
        return
    ordered = sorted(nos)
    expect = list(range(ordered[0], ordered[0] + len(ordered)))
    if ordered != expect:
        dup = sorted({n for n in nos if nos.count(n) > 1})
        gap = [n for n in expect if n not in nos]
        report.warn(f"题号不连续：重复 {dup} / 缺失 {gap}")


def check_space_flow(blocks, report):
    """题干后紧跟内容块却仍带 space → 留白把题干和材料/断句隔开（常见踩坑）。

    只提示不擅改：`space` 是 IR 的显式意图，自动删除会破坏往返一致性。
    要保留留白请显式写 `keep_space: true`。
    """
    for i, b in enumerate(blocks):
        if b.get("type") != "question":
            continue
        if not b.get("space") or b.get("options") or b.get("subs"):
            continue
        if b.get("keep_space"):
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if nxt and nxt.get("type") in CONTENT_BLOCKS:
            report.hint(
                f"第 {b.get('no')} 题 space=true，但下一块是 {nxt.get('type')}："
                f"留白会把题干与其材料/断句隔开，建议删掉 space（确需留白写 keep_space=true）")


def check_poem_like(blocks, report):
    """整段材料里塞了诗题+诗句（MinerU 常把诗歌压成一个 para）→ 提示拆 poem 块。"""
    for b in blocks:
        if b.get("type") != "para":
            continue
        lines = [x.strip() for x in str(b.get("text") or "").splitlines() if x.strip()]
        if len(lines) < 4:
            continue
        short = [x for x in lines if _visible_len(x) <= 20]
        if len(short) >= 4 and all(re.search(r"[，。？！]$", x) for x in short[:4]):
            report.hint(f"疑似诗歌被压成一段（{len(lines)} 行）："
                        f"建议拆成 heading/lead + poem（每两句一行）+ note 块")


def render_paper(ir):
    meta = ir.get("meta") or {}
    blocks = ir.get("blocks") or []
    report = RenderReport()

    kind = meta.get("kind", "shiti")
    is_answer = kind in ("daan", "answer")
    sty = meta.get("sty", STY_NAME).replace(".sty", "")

    extra = ""
    if meta.get("footer"):
        extra += f"\\examfooter{{{meta['footer']}}}\n"

    pkgs = "".join(f"\\usepackage{{{p}}}\n"
                   for p in (meta.get("extra_packages") or []))

    out = [PREAMBLE.format(sty=sty, extra=extra, pkgs=pkgs)]
    # 行距：默认用 ywexam 的 1.5；压页时写 meta.linespread（1.35 / 1.30）
    if meta.get("linespread"):
        out.append(f"\\ywlinespread{{{meta['linespread']}}}\n")
    if meta.get("images_dir"):
        out.append(f"\\graphicspath{{{{{meta['images_dir']}/}}}}\n")

    title = meta.get("title", "")
    subtitle = meta.get("subtitle", "语文参考答案" if is_answer else "语文试题卷")
    out.append(f"\\{'answertitle' if is_answer else 'examtitle'}{{{title}}}{{{subtitle}}}\n")
    if meta.get("exam_note"):
        out.append(f"\\examnote{{{meta['exam_note']}}}\n")

    check_numbering(blocks, report)
    if not meta.get("no_hints"):
        check_space_flow(blocks, report)
        check_poem_like(blocks, report)

    for b in blocks:
        body = render_block(b, report)
        if body is None or body == "":
            continue
        # 顶部块（sechead 等）需要显式空行，避免与上一段粘连
        out.append(body + "\n")

    out.append("\\end{document}\n")
    return "\n".join(out), report


# ────────────────────────── CLI ──────────────────────────

SCHEMA_EXAMPLE = {
    "meta": {
        "title": "浙江省嘉兴市2026学年第一学期高三教学质量检测",
        "subtitle": "语文试题卷",
        "kind": "shiti",
        "footer": "语文试题卷",
        "images_dir": "Images-2611嘉兴一模",
        "linespread": 1.35,
    },
    "blocks": [
        {"type": "sechead", "text": "一、阅读（74分）"},
        {"type": "subsechead", "text": "（一）阅读I（本题共5小题，19分）"},
        {"type": "lead", "text": "阅读下面的文字，完成1～5题。"},
        {
            "type": "material",
            "label": "材料一：",
            "text": ["第一段……", "第二段……"],
            "source": "（摘编自《……》）",
        },
        {
            "type": "question",
            "no": 1,
            "stem": "下列对材料相关内容的理解和分析，不正确的一项是（3分）",
            "options": ["选项A", "选项B", "选项C", "选项D"],
        },
        {
            "type": "question",
            "no": 3,
            "stem": "……（3分）",
            "space": True,
        },
        # 题干后紧跟内容块时不要留白（否则题干与材料被隔开）
        {"type": "question", "no": 9, "stem": "请为文中画线处补写语句（4分）"},
        {"type": "para", "text": "语句①：……"},
        # 短选项（1~3 字）横排一行四列
        {
            "type": "question",
            "no": 18,
            "stem": "下列词语中字形和读音全都正确的一项是（3分）",
            "options": ["究竟", "判官", "郑重", "忧郁"],
            "choices_layout": "inline",
        },
        {"type": "duanju", "text": "西戎部将欲A以横山之众降B公C极论其D不可纳E后必为边患F已而果然"},
        {"type": "poem", "lines": ["茶。", "香叶，嫩芽。"]},
        {"type": "figure", "path": "map.png", "width": "0.44", "caption": "（第1题图）"},
        {"type": "note", "text": "[注]\\xq{1}迩英：即迩英阁。"},
        {"type": "ans", "no": 1, "text": "B（“共同激发”错误）"},
        {"type": "scorenote", "text": "（每点2分，共4分）"},
        {"type": "subans", "label": "（2）", "text": "示例：……"},
        # 一条答案要分行：text 给列表，渲染器拆成多个 \subans
        {"type": "subans", "label": "", "text": ["示例一：……", "示例二：……"]},
        {"type": "raw", "tex": "\\begin{center}...\\end{center}"},
    ],
}

FIELD_DOC = """
IR 字段说明
───────────
meta.title      卷首第一行（考试名称）
meta.subtitle   卷首第二行（语文试题卷 / 语文参考答案）；答案卷传 "" 则只显示一行大标题
meta.kind       shiti（试题，默认）| daan（答案）
meta.footer     页脚前缀，默认「语文试题卷」/「语文参考答案」
meta.exam_note  可选，卷首说明（\\examnote）
meta.images_dir 可选，图片目录（生成 \\graphicspath）
meta.linespread 可选，行距（默认 ywexam 的 1.5；压页用 1.35 / 1.30）
meta.sty        可选，宏包名（默认 ywexam）
meta.no_hints   可选，true 关闭 [HINT] 级检查（不影响 [WARN]）

blocks 是**有序块流**，渲染顺序 = 数组顺序。块类型：

  sechead      {text}                      一级大题标题
  subsechead   {text}                      二级小题标题
  lead         {text}                      「阅读下面的文字，完成1～5题。」
  material     {label, text[], source}     材料：标签 + 楷体正文（多段）+ 右对齐出处
  heading      {text, byline}              篇名 + 作者（center 块）
  poem         {lines[]}                   诗歌，每句居中
  duanju       {text}                      断句题整行居中
  figure       {path, width, caption, keep}
                                           配图；width 可写 0.44（自动补 \\linewidth）
                                           或 8cm；放不下被推页时先缩 width
  note         {text}                      注释（[注]…）
  para         {text}                      自由段落（写作题材料段等）
  question     {no, stem, options[4], subs[], space, keep_space,
                choices_layout, choices_cols}
                                           题目；options 存在则输出选项环境；
                                           choices_layout: stack（默认纵排）|
                                           inline（tasks 横排）| auto（可见长度 ≤8 才横排）；
                                           subs 为小问裸段落（（1）（2）…）；
                                           space=true 时题后留 DEFAULT_SPACE 白，
                                           但**下一块是内容块时会被提示**（题干会被隔开）
  ans          {no, text}                  参考答案（\\ans）
  subans       {label, text}               子项答案（\\subans）；text 为列表时拆成多行
  scorenote    {text}                      评分说明（\\scorenote）
  translation  {label, text}               参考译文（translabel + translation）
  raw          {tex}                       逃生舱：表格材料 / 特殊排版，原样输出
"""


def main():
    ap = argparse.ArgumentParser(description="语文试卷 IR（块流）→ LaTeX 渲染器")
    ap.add_argument("ir", nargs="?", help="chinese.json 路径")
    ap.add_argument("-o", "--output", help="输出 .tex 路径")
    ap.add_argument("--stdout", action="store_true", help="输出到标准输出")
    ap.add_argument("--schema", action="store_true", help="打印 IR 示例与字段说明")
    ap.add_argument("--copy-sty", action="store_true",
                    help="把 templates/chinese/ywexam.sty 拷到输出目录（不存在时）")
    args = ap.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=2))
        print(FIELD_DOC)
        return 0

    if not args.ir:
        ap.error("需要 chinese.json，或用 --schema 查看格式")

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    tex, report = render_paper(ir)

    if args.stdout or not args.output:
        print(tex)
    else:
        out = Path(args.output)
        out.write_text(tex, encoding="utf-8")
        print(f"[OK] {args.output}")
        if args.copy_sty:
            dst = out.parent / STY_NAME
            if not dst.exists():
                shutil.copy2(STY_DIR / STY_NAME, dst)
                print(f"[OK] 已复制 {STY_NAME} → {out.parent}")

    for w in report.warnings:
        print(f"[WARN] {w}", file=sys.stderr)
    for h in report.hints:
        print(f"[HINT] {h}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
