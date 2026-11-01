#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_answer_sheet.py — 从试卷 .tex 自动生成答题卡（A4 / A3）

设计目标
--------
* 只读试卷 .tex，不改动任何既有文件；
* 自动识别「单选题数 / 多选题数 / 填空题数 / 解答题题号与分值」；
* 自动推算版面数 pages 与每题密度 block（复刻 answersheet.sty 的分页算法）；
* 一键生成 .tex 并（默认）用 xelatex 连编两次出 PDF。

用法
----
    python gen_answer_sheet.py <试卷.tex>                    # A4 答题卡
    python gen_answer_sheet.py <试卷.tex> --layout both      # A4 + A3
    python gen_answer_sheet.py <试卷.tex> --print-spec       # 只打印解析结果
    python gen_answer_sheet.py <试卷.tex> --pages 4 --block 2 --percol 4
    python gen_answer_sheet.py <试卷.tex> --no-compile       # 只出 tex

输出（与试卷同目录）
--------------------
    <卷名>-答题卡.tex / .pdf        （layout=a4）
    <卷名>-答题卡-A3.tex / .pdf     （layout=a3）
    answersheet.sty                 （宏包副本，供日后单独重编）

解析失败的兜底
--------------
    可用 --single / --multi / --blanks / --solves 手动覆盖。
    --solves 形如 "15/13,16/15,17/15,18/17,19/17"。
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Windows 控制台 UTF-8 安全 ────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
STY_SRC = SKILL_DIR / "templates" / "answer-sheet" / "answersheet.sty"

# =========================================================================
#  answersheet.sty 中的版式常量（cm）——必须与宏包保持一致
# =========================================================================
CHOICE_TOP = 16.2        # 选择题区上边纵坐标
CHOICE_ROW = 0.55        # 选择题行距
CHOICE_PAD = 0.5         # 选择题框额外高度
BLANK_ROW = 1.2          # 填空题行距
BLANK_PAD = 0.2          # 填空题框额外高度
PLAIN_H = 25.7           # 非首面可用答题高度
MIN_CM_PER_POINT = 1.05  # 每分至少占用的答题高度（cm），低于此值视为过挤
FIT_RATIO = 0.85         # 附图最多占答题框高度的比例，超过就自动降密度

CN_NUM = "一二三四五六七八九十"

# 生成标记：用于判断同名文件是否由本脚本产出（决定能否覆盖）
GEN_MARK = "由 scripts/gen_answer_sheet.py 自动生成"

SECTION_RE = re.compile(
    r"(?:\\section\*\{|\\subsection\*\{"
    r"|\\noindent\s*\{?\s*\\textbf\{"          # \noindent\textbf{ 与 \noindent{\textbf{
    r"|\\textbf\{)"
    r"\s*([一二三四五六七八九十])\s*[、.．]\s*([^}]{0,160})\}",
    re.S,
)
ENV_TOKEN_RE = re.compile(r"\\(begin|end)\{(enumerate|examenum)\}|\\item\b")
LIST_BEGIN_RE = re.compile(r"\\begin\{(enumerate|examenum)\}(\s*\[[^\]]*\])?")
SCORE_RE = re.compile(r"[（(]\s*(?:[^（）()]{0,10}?满分)?\s*(\d{1,3})\s*分\s*[）)]")
TEXTBF_RE = re.compile(r"\\textbf\{((?:[^{}]|\{[^{}]*\})*)\}")   # 容许一层嵌套
# 纯格式包装命令：保留参数内容，只去掉外壳
WRAP_RE = re.compile(
    r"\\(?:LARGE|Large|large|huge|Huge|textbf|textmd|textup|bfseries"
    r"|mdseries|itshape|upshape|centering|zihao)\s*\{([^{}]*)\}"
)
CENTER_RE = re.compile(r"\\begin\{center\}(.*?)\\end\{center\}", re.S)
# 自定义卷头命令（2025.6 用 \subtitle / \subjecttitle，没有 \textbf）
TITLE_CMD_RE = re.compile(r"\\(subtitle|subjecttitle|examtitle|title)\s*\{([^{}]*)\}")
# 卷头里必须剔除的"密级 / 考试说明 / 小节标题 / 页脚"一类文字
BAD_TITLE_RE = re.compile(
    r"绝密|机密|秘密|启用前|试卷类型|注意事项|本试卷共|考试用时|考生须知"
    r"|答题卡|扫描|二维码|页\(?共|第\s*\d+\s*页"
    r"|^[一二三四五六七八九十]、|本题共|每小题|在每小题|符合题目要求|选出"
)
# 像"考试名称"的强特征词，用于在多个候选里挑标题
TITLE_HINT_RE = re.compile(
    r"考试|高考|联考|统考|测评|测试|期末|期中|月考|调研|学业水平|质量检测|模拟|适应性"
)
DOC_BODY_RE = re.compile(r"\\begin\{document\}(.*?)\\end\{document\}", re.S)


# =========================================================================
#  数据结构
# =========================================================================
@dataclass
class Section:
    kind: str                    # single | multi | fill | solve | other
    head: str                    # 小节标题原文
    start: int | None            # 环境 start= 值
    count: int                   # 顶层 \item 数
    scores: list[int] = field(default_factory=list)


@dataclass
class ExamSpec:
    source: Path
    title: str
    subject: str
    single: int = 0
    multi: int = 0
    blanks: int = 0
    solve_start: int = 0
    solve_scores: list[int] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # 解答题附图/表：题号 -> [(mode, latex, est_height_cm)]，mode ∈ {fig, block}
    aux: dict[int, list[tuple[str, str, float]]] = field(default_factory=dict)
    graphicspath: str = ""            # 原卷的 \graphicspath，原样带过来
    deps: list[str] = field(default_factory=list)     # 原卷用到且安全的宏包
    tikzlibs: list[str] = field(default_factory=list)  # 原卷用到的 tikz 库

    @property
    def choices(self) -> int:
        return self.single + self.multi

    @property
    def solves(self) -> list[tuple[int, int]]:
        """[(题号, 分值), ...]"""
        return [
            (self.solve_start + i, s)
            for i, s in enumerate(self.solve_scores)
        ]

    @property
    def fig_heights(self) -> dict[int, float]:
        """{题号: 该题附图总高 cm}，供分页时预留空间。"""
        return {
            q: sum(h for _, _, h in blocks)
            for q, blocks in self.aux.items() if blocks
        }


# =========================================================================
#  解析
# =========================================================================
def _classify(head: str) -> str:
    h = head.replace(" ", "")
    if any(k in h for k in ("多选", "多项选择", "不定项", "多项符合", "多个选项")):
        return "multi"
    if "单选" in h or "选择" in h:
        return "single"
    if "填空" in h:
        return "fill"
    if any(k in h for k in ("解答", "计算", "证明", "综合")):
        return "solve"
    return "other"


def _scan_top_items(seg: str) -> tuple[int | None, list[str]]:
    """在片段中找第一个 enumerate/examenum，返回 (start, 顶层各 item 正文)。"""
    m = LIST_BEGIN_RE.search(seg)
    if not m:
        return None, []

    opts = m.group(2) or ""
    sm = re.search(r"start\s*=\s*(\d+)", opts)
    start = int(sm.group(1)) if sm else None

    depth = 0
    item_starts: list[int] = []
    env_end = len(seg)
    pos = m.start()
    while True:
        t = ENV_TOKEN_RE.search(seg, pos)
        if not t:
            break
        if t.group(1) == "begin":
            depth += 1
        elif t.group(1) == "end":
            depth -= 1
            if depth <= 0:
                env_end = t.start()
                break
        elif depth == 1:                       # 顶层 \item
            item_starts.append(t.end())
        pos = t.end()

    texts = []
    for i, p in enumerate(item_starts):
        q = item_starts[i + 1] if i + 1 < len(item_starts) else env_end
        texts.append(seg[p:q])
    return start, texts


def _clean_title(t: str) -> str:
    # \\ 换行 → 全角空格：ctex 会吞掉中英文之间的普通空格，必须用全角才能留住分隔
    t = t.replace("\\\\", "\u3000")
    for _ in range(3):                                    # 反复剥格式外壳
        new = WRAP_RE.sub(r"\1", t)
        if new == t:
            break
        t = new
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", t)   # 去命令+参数
    t = t.replace("{", "").replace("}", "").replace("~", " ")
    t = re.sub(r"[ \t\r\n\f\v]+", " ", t).strip()          # 只压缩 ASCII 空白
    # 只剥「学科 + 试题卷/试卷/试题」这类纯后缀，避免误伤「调研测试卷」
    m = re.search(r"\s*(?:数学|语文|英语|物理|化学|生物|政治|历史|地理)\s*"
                  r"(?:试题卷|试卷|试题)\s*$", t)
    if m:
        t = t[:m.start()]
    else:
        t = re.sub(r"\s*(?:试题卷|答题卡)\s*$", "", t)
    t = re.sub(r"[\s·、]*[高初][一二三]\s*$", "", t)      # 去掉尾部年级
    return t.strip(" ，,。.：:")


def _title_candidates(region: str) -> list[str]:
    """从一段 tex 里收集所有可能的卷头文字（已清洗）。"""
    raw = [m.group(1) for m in TEXTBF_RE.finditer(region)]
    raw += [m.group(2) for m in TITLE_CMD_RE.finditer(region)]
    return [_clean_title(x) for x in raw]


def _pick_title(cands: list[str], fallback: str) -> str:
    good = [c for c in cands if len(c) >= 4 and not BAD_TITLE_RE.search(c)]
    if not good:
        return _clean_title(fallback) or "考试"

    def score(c: str) -> int:
        s = min(len(c), 60)
        if TITLE_HINT_RE.search(c):
            s += 100
        if re.search(r"20\d{2}", c):
            s += 20
        return s

    return max(good, key=score)


def _extract_title(body: str, fallback: str) -> tuple[str, str]:
    head = body[:2500]
    cands = _title_candidates(head)
    if not any(len(c) >= 4 and not BAD_TITLE_RE.search(c) for c in cands):
        # 头部没找到像样的标题，退回到第一个 center 环境里找
        m = CENTER_RE.search(body)
        if m:
            cands += _title_candidates(m.group(1))

    title = _pick_title(cands, fallback)
    subject = "数学"
    for c in cands:
        mm = re.search(r"(数学|语文|英语|物理|化学|生物|政治|历史|地理)", c)
        if mm:
            subject = mm.group(1)
            break
    return title, subject


# =========================================================================
#  解答题附图 / 三线表 提取
# =========================================================================
AUX_HINT_RE = re.compile(r"\\begin\{tikzpicture\}|\\includegraphics|\\begin\{tabular")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(\s*\[[^\]]*\])?\s*\{[^{}]*\}")
INCLUDEGRAPHICS_PATH_RE = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")
_MISSING_IMAGES: list[str] = []   # 提取过程中发现的不存在图片，供上层汇总告警

GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
PKG_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^{}]+)\}")
TIKZLIB_RE = re.compile(r"\\usetikzlibrary\{([^{}]+)\}")

# 允许从原卷导言区搬过来的宏包（只搬图表内容真正会用到的，
# geometry / fancyhdr / hyperref / ctex 这类版式宏包绝不能搬）
SAFE_PKGS = {
    "amsmath", "amssymb", "amsfonts", "amsthm", "bm", "mathtools", "mathrsfs",
    "graphicx", "xcolor", "color", "tikz", "pgfplots", "pgf",
    "array", "tabularx", "longtable", "booktabs", "multirow", "makecell",
    "diagbox", "colortbl", "dcolumn", "siunitx", "bigdelim",
    "caption", "subcaption", "adjustbox", "rotating", "float",
    "enumitem", "tasks", "multicol", "wrapfig", "listings",
}


def extract_deps(text: str) -> tuple[list[str], list[str]]:
    """从原卷导言区提取安全的宏包名与 tikz 库名。"""
    pkgs: list[str] = []
    for m in PKG_RE.finditer(text):
        for p in m.group(1).split(","):
            p = p.strip()
            if p in SAFE_PKGS and p not in pkgs:
                pkgs.append(p)
    libs: list[str] = []
    for m in TIKZLIB_RE.finditer(text):
        for l in m.group(1).split(","):
            l = l.strip()
            if l and l not in libs:
                libs.append(l)
    return pkgs, libs


def _env_spans(text: str, name: str) -> list[tuple[int, int]]:
    """返回 text 中所有 \\begin{name}…\\end{name} 的 (起, 止)，支持同名嵌套。"""
    pat = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for m in pat.finditer(text):
        if m.group(1) == "begin":
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth > 0:
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
    return spans


def _graphics_dirs(spec_gp: str, base: Path) -> list[Path]:
    """把 \\graphicspath{{a/}{b/}} 拆成目录列表。"""
    out = [base]
    for inner in re.findall(r"\{([^{}]*)\}", spec_gp or ""):
        inner = inner.strip()
        if inner:
            out.append(base / inner)
    return out


def _images_ok(block: str, dirs: list[Path]) -> tuple[bool, list[str]]:
    """块里引用的图片是否都存在。返回 (是否全部存在, 缺失清单)。

    原卷里常有 \\includegraphics{D:/Desktop/xxx.jpg} 这种指向作者本机的绝对路径，
    或者题库搬迁后丢图的相对路径——原卷自己就编不过，答题卡更不可能。
    """
    missing = []
    for m in INCLUDEGRAPHICS_PATH_RE.finditer(block):
        name = m.group(1).strip()
        if not name or name.startswith("#"):
            continue
        p = Path(name)
        if p.is_absolute():
            if not p.exists():
                missing.append(name)
        elif not any((d / name).exists() for d in dirs):
            missing.append(name)
    return (not missing), missing


def _strip_aux_noise(s: str) -> str:
    """去掉在答题卡上会报错/无意义的命令（\\caption 不能在浮动环境外使用）。"""
    s = re.sub(r"\\caption\s*\{[^{}]*\}", "", s)
    s = re.sub(r"\\label\s*\{[^{}]*\}", "", s)
    return s.strip()


def _est_aux_height(mode: str, latex: str) -> float:
    """估算附图占用高度（cm）。只用于分页预留，宁可略大。

    tabular 的标定来自实测（2601强基联盟 第 15 题两张表，pdftotext -bbox 量得）：
      2 数据行的表实际占 1.3cm、3 数据行的表实际占 2.0cm，
      而 `\\` 计数比数据行多 1（末行末尾也有 `\\`），故 rows = `\\` 数 + 1。
    旧公式 1.8 + 0.72*rows 把两张表估成 8.6cm（实际 4.0cm），
    误触发「降密度」，把 4 版面撑成 5 版面。
    """
    if mode == "block":
        if "tabular" in latex:
            rows = len(re.findall(r"\\\\", latex)) + 1
            return min(0.45 + 0.55 * rows, 9.0)
        if latex.count("tikzpicture") >= 2 or "minipage" in latex:
            return 5.5
        return 4.8
    return 4.5


def extract_aux(item: str, dirs: list[Path] | None = None
               ) -> list[tuple[str, str, float]]:
    """从一道解答题的正文里抽出附图/表，返回 [(mode, latex, est_h_cm)]。

    优先整块取 center 环境（保留「两图并排」「图 + 图注」等原有版式），
    其余散落的 tikzpicture / includegraphics / tabular 单独取。
    """
    found: list[tuple[int, str, str]] = []      # (位置, mode, latex)
    consumed: list[tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return not any(s < ce and e > cs for cs, ce in consumed)

    # 1) center 整块（最常见的图组写法）
    for s, e in _env_spans(item, "center"):
        blk = item[s:e]
        if AUX_HINT_RE.search(blk) and free(s, e):
            consumed.append((s, e))
            wide = ("minipage" in blk) or ("tabular" in blk)
            found.append((s, "block" if wide else "fig", blk))

    # 2) 散落的 tikzpicture
    for s, e in _env_spans(item, "tikzpicture"):
        if free(s, e):
            consumed.append((s, e))
            found.append((s, "fig", item[s:e]))

    # 3) 散落的 \includegraphics
    for m in INCLUDEGRAPHICS_RE.finditer(item):
        if free(m.start(), m.end()):
            consumed.append((m.start(), m.end()))
            found.append((m.start(), "fig", m.group(0)))

    # 4) 表格（三线表也是 tabular）
    for env in ("tabular", "tabularx", "longtable"):
        for s, e in _env_spans(item, env):
            if free(s, e):
                consumed.append((s, e))
                found.append((s, "block", item[s:e]))

    found.sort(key=lambda t: t[0])

    out = []
    for _, mode, latex in found:
        if dirs is not None:
            ok, missing = _images_ok(latex, dirs)
            if not ok:
                # 整块丢弃：半张图比没有图更容易误导学生
                _MISSING_IMAGES.extend(missing)
                continue
        out.append((mode, _strip_aux_noise(latex), _est_aux_height(mode, latex)))
    return out


def parse_exam_tex(path: Path) -> ExamSpec:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = DOC_BODY_RE.search(text)
    body = m.group(1) if m else text

    title, subject = _extract_title(body, path.stem)
    spec = ExamSpec(source=path, title=title, subject=subject)

    # ── 分节 ──
    marks = list(SECTION_RE.finditer(body))
    solve_texts: list[str] = []
    for i, mk in enumerate(marks):
        kind = _classify(mk.group(2))
        if kind == "other":
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        seg = body[mk.end():end]
        start, texts = _scan_top_items(seg)
        sec = Section(kind=kind, head=mk.group(2).strip(), start=start, count=len(texts))
        if kind == "solve":
            solve_texts = texts
            for t in texts:
                sm = SCORE_RE.search(t[:160])
                sc = int(sm.group(1)) if sm else 0
                if not (1 <= sc <= 30):
                    sc = 0
                sec.scores.append(sc)
        spec.sections.append(sec)

    # 原卷的 \graphicspath 原样带过来，否则附图里的图片路径会失效
    gm = GRAPHICSPATH_RE.search(text)
    if gm:
        spec.graphicspath = gm.group(0)
    # 附图/表可能依赖原卷导言区的宏包（如 \diagbox）和 tikz 库，一并带上
    spec.deps, spec.tikzlibs = extract_deps(text)

    # ── 汇总 ──
    # 兜底：若出现两个「选择题」小节（第二个其实是多选题但标题未写"多选"），
    # 把第二个改判为多选题。
    seen_single = 0
    for sec in spec.sections:
        if sec.kind == "single":
            seen_single += 1
            if seen_single >= 2:
                sec.kind = "multi"

    single = next((s for s in spec.sections if s.kind == "single"), None)
    multi = next((s for s in spec.sections if s.kind == "multi"), None)
    fill = next((s for s in spec.sections if s.kind == "fill"), None)
    solve = next((s for s in spec.sections if s.kind == "solve"), None)

    spec.single = single.count if single else 0
    spec.multi = multi.count if multi else 0
    spec.blanks = fill.count if fill else 0

    # 题号连续性核对（仅提示，不阻断）
    expect = 1
    if single:
        if single.start not in (None, 1):
            spec.warnings.append(f"单选题 start={single.start}，预期 1")
        expect += single.count
    if multi:
        if multi.start not in (None, expect):
            spec.warnings.append(f"多选题 start={multi.start}，预期 {expect}")
        expect += multi.count
    if fill:
        if fill.start not in (None, expect):
            spec.warnings.append(f"填空题 start={fill.start}，预期 {expect}")
        expect += fill.count
    if solve:
        if solve.start not in (None, expect):
            spec.warnings.append(f"解答题 start={solve.start}，预期 {expect}")
        spec.solve_start = solve.start or expect
        scores = [s if s else 12 for s in solve.scores]
        missing = sum(1 for s in solve.scores if not s)
        if missing:
            spec.warnings.append(f"{missing} 道解答题未标注分值，按 12 分计入版面规划")
        spec.solve_scores = scores

        # 逐题抽附图 / 三线表（题号 = start + 序号）
        _MISSING_IMAGES.clear()
        gdirs = _graphics_dirs(spec.graphicspath, path.parent)
        for i, t in enumerate(solve_texts):
            blocks = extract_aux(t, gdirs)
            if blocks:
                spec.aux[spec.solve_start + i] = blocks
    else:
        spec.warnings.append("未找到解答题小节")

    if _MISSING_IMAGES:
        uniq = sorted(set(_MISSING_IMAGES))
        spec.warnings.append(
            f"{len(uniq)} 张图片在原卷目录下找不到，已跳过对应附图："
            + "、".join(uniq[:3]) + ("…" if len(uniq) > 3 else ""))
    if spec.choices == 0:
        spec.warnings.append("未识别到选择题")
    if spec.blanks == 0:
        spec.warnings.append("未识别到填空题")
    return spec


# =========================================================================
#  版面规划（复刻 answersheet.sty 的 \gk@plan）
# =========================================================================
def h_zero(choices: int, percol: int, blanks: int) -> float:
    """首面可用于解答题的高度（cm）。"""
    choice_h = min(choices, percol) * CHOICE_ROW + CHOICE_PAD
    blank_top = CHOICE_TOP - choice_h - 0.7
    blank_h = math.ceil(blanks / 3) * BLANK_ROW + BLANK_PAD
    answer_top = blank_top - blank_h - 1.2
    return answer_top - 1.2


def simulate_panels(npanels: int, rules: list[tuple[int, int]], block: int,
                    choices: int, percol: int, blanks: int) -> list[tuple[int, int]]:
    """返回每个版面分到的 (起始序号, 结束序号)，序号 1-based 且闭区间。"""
    n = len(rules)
    if n == 0:
        return [(1, 0)] * npanels
    scores = [s for _, s in rules]
    prefix = [0]
    for s in scores:
        prefix.append(prefix[-1] + s)
    total = prefix[-1]

    h0 = h_zero(choices, percol, blanks)
    htot = h0 + (npanels - 1) * PLAIN_H

    panels: list[tuple[int, int]] = []
    qi = 0
    for i in range(npanels):
        ht = h0 if i == 0 else PLAIN_H
        if i == npanels - 1:
            e = n
        else:
            tgt = ht / htot * total
            psv = prefix[qi]
            e, cnt, go = qi, 0, True
            for k in range(1, n + 1):
                if not go:
                    break
                if k <= qi:
                    continue
                if cnt < block:
                    if cnt == 0:
                        e, cnt = k, 1
                    else:
                        mid = prefix[k - 1] - psv + scores[k - 1] / 2
                        if mid < tgt:
                            e, cnt = k, cnt + 1
                        else:
                            go = False
                else:
                    go = False
        panels.append((qi + 1, e))
        qi = e
    return panels


def choose_layout_params(spec: ExamSpec, block: int, percol: int = 4,
                         min_cm_per_point: float = MIN_CM_PER_POINT,
                         lookahead: int = 3) -> tuple[int, int]:
    """返回 (pages, block)。

    先取「可行」的最小版面数 p_min，再在 p_min ~ p_min+lookahead 中挑第一个
    「每分答题高度 ≥ min_cm_per_point」的版面数；都不达标就用 p_min。

    可行 = 1) 没有空版面（否则末尾会多出一整片空白答题框）
           2) 每面解答题数 ≤ block
    注意：版面数并非越大越好——超过 greedy 装填能力后，多出来的版面必然是空的，
    所以不做无脑递增。
    """
    n = len(spec.solve_scores)
    if n == 0:
        return 1, block

    total = sum(spec.solve_scores)
    h0 = h_zero(spec.choices, percol, spec.blanks)

    def panels_of(p: int) -> list[tuple[int, int]]:
        return simulate_panels(p, spec.solves, block, spec.choices, percol, spec.blanks)

    def feasible(p: int) -> bool:
        panels = panels_of(p)
        if any(e < s for s, e in panels):              # 空版面
            return False
        if any(e - s + 1 > block for s, e in panels):  # 超出 block
            return False
        return True

    p_min = next((p for p in range(1, 13) if feasible(p)), None)
    if p_min is None:
        return max(1, math.ceil(n / block)), block

    for p in range(p_min, min(p_min + lookahead, 12) + 1):
        if feasible(p) and h0 + (p - 1) * PLAIN_H >= total * min_cm_per_point:
            return p, block
    return p_min, block


def estimate_box_heights(spec: ExamSpec, pages: int, block: int,
                         percol: int = 4) -> dict[int, float]:
    """估算每道解答题分到的答题框高度（cm），用于判断附图会不会把书写区挤没。"""
    rules = spec.solves
    if not rules:
        return {}
    panels = simulate_panels(pages, rules, block, spec.choices, percol, spec.blanks)
    h0 = h_zero(spec.choices, percol, spec.blanks)
    out: dict[int, float] = {}
    for pi, (s, e) in enumerate(panels):
        if e < s:
            continue
        avail = (h0 if pi == 0 else PLAIN_H) - 1.2
        span = sum(sc for _, sc in rules[s - 1:e])
        if span <= 0:
            continue
        for idx in range(s - 1, e):
            q, sc = rules[idx]
            out[q] = avail * sc / span
    return out


def fit_layout_for_aux(spec: ExamSpec, block: int, percol: int = 4
                       ) -> tuple[int, int, list[str]]:
    """选一个「附图放得下」的版面方案。

    附图是硬内容：放不下就会压过题间分隔线、盖住下一题的作答区。
    所以一旦某题的图超过答题框的 FIT_RATIO，就把密度降到「每题独占一面」
    （block=1）——单面 24.5cm 的答题区足够容纳绝大多数立体几何图与统计表。
    不在 TeX 里现场缩放：量高度容易出错，缩出来的字号也不可控。
    """
    pages, blk = choose_layout_params(spec, block, percol)
    if not spec.aux:
        return pages, blk, []

    notes: list[str] = []
    b = block
    for _ in range(3):
        pages, blk = choose_layout_params(spec, b, percol)
        boxes = estimate_box_heights(spec, pages, blk, percol)
        worst_q, worst_r, worst_h, worst_b = None, 0.0, 0.0, 0.0
        for q, blocks in spec.aux.items():
            fh = sum(h for _, _, h in blocks)
            bh = boxes.get(q) or 0.0
            if bh and fh / bh > worst_r:
                worst_q, worst_r, worst_h, worst_b = q, fh / bh, fh, bh
        if worst_r <= FIT_RATIO:
            if b != block:
                notes.append(f"第 {worst_q} 题附图较高，已改为每题独占一面"
                             f"（{pages} 版面，单面答题区 {worst_b:.1f}cm）")
            return pages, blk, notes
        if b > 1:
            b = 1
            continue
        notes.append(f"[WARN] 第 {worst_q} 题附图约 {worst_h:.1f}cm，"
                     f"仍超过单面答题区 {worst_b:.1f}cm，请手工删减该题图表")
        return pages, blk, notes
    return pages, blk, notes


# =========================================================================
#  渲染
# =========================================================================
PAPER = {
    "a4": dict(cls="a4paper", w=210, h=297, dv="a4"),
    "a3": dict(cls="a3paper", w=420, h=297, dv="a3"),
}


_ESC_MAP = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#",
            "_": r"\_", "$": r"\$", "{": r"\{", "}": r"\}",
            "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def _esc(s: str) -> str:
    """LaTeX 特殊字符转义（title/subject 用）。

    必须单趟正则替换：若先转义反斜杠再转义花括号，会把刚插入的
    ``\\textbackslash{}`` 再破坏成 ``\\textbackslash\\{\\}``。
    """
    return re.sub(r"[\\&%#_${}~^]", lambda m: _ESC_MAP[m.group()], s)


def render_tex(spec: ExamSpec, *, layout: str, pages: int, block: int,
               percol: int, title: str, subject: str,
               color: str = "GKpink", bw: bool = False,
               with_aux: bool = True) -> str:
    p = PAPER[layout]
    rules = ",".join(f"{q}/{s}" for q, s in spec.solves)
    note_pages = "张" if layout == "a3" else "个版面"
    src = spec.source.name

    aux = spec.aux if with_aux else {}

    # 附图/表正文（放在 \gkMake 之前）
    # 同一题可能有多个图/表：\gkFig/\gkBlock 按题号 \gdef 存储，重复调用会互相覆盖，
    # 所以必须先把同题同类型的块拼成一个再发。
    aux_body = []
    for q, blocks in sorted(aux.items()):
        figs = [l for m, l, _ in blocks if m == "fig"]
        blks = [l for m, l, _ in blocks if m == "block"]
        if figs:
            aux_body.append(f"\\gkFig{{{q}}}{{%\n" + "\n\n".join(figs) + "\n}")
        if blks:
            aux_body.append(f"\\gkBlock{{{q}}}{{%\n"
                            + "\n\\par\\medskip\n".join(blks) + "\n}")
    aux_tex = ("\n".join(aux_body) + "\n\n") if aux_body else ""

    gp = (spec.graphicspath + "\n") if (aux and spec.graphicspath) else ""
    dep_lines = ""
    lib_lines = ""
    if aux:
        extra = [p for p in spec.deps
                 if p not in ("amsmath", "amssymb", "graphicx", "tikz")]
        if extra:
            dep_lines = "\\usepackage{" + ", ".join(extra) + "}\n"
        # \usetikzlibrary 必须在 tikz（由 answersheet 加载）之后
        if spec.tikzlibs:
            lib_lines = "\\usetikzlibrary{" + ", ".join(spec.tikzlibs) + "}\n"
    aux_note = ""
    if aux:
        aux_note = f"%  附图/表：{len(aux)} 题（" + "、".join(str(q) for q in sorted(aux)) + "）\n"

    return f"""% !TEX program = xelatex
% ============================================================================
%  答题卡（{'A4 · 每面一个版面' if layout == 'a4' else 'A3 横向 · 每张并排两个 A4 版面'}）
%  {GEN_MARK}，请勿手工修改。
%  源试卷：{src}
%  版面：layout={layout}  pages={pages} {note_pages}  block={block}
%  选择题 {spec.choices} 题（单选 {spec.single} + 多选 {spec.multi}）｜填空 {spec.blanks} 题
%  解答题：{rules or '（无）'}
{aux_note}%  编译：xelatex 连编两次（remember picture 定位）
% ============================================================================
\\documentclass[UTF8,11pt,{p['cls']}]{{ctexart}}

\\usepackage{{geometry}}
\\geometry{{paperwidth={p['w']}mm, paperheight={p['h']}mm, hmargin=6mm, vmargin=6mm}}
\\pagestyle{{empty}}

\\usepackage{{amsmath, amssymb}}
{dep_lines}\\usepackage{{answersheet}}
{lib_lines}{gp}
\\gkSetup{{
  layout  = {p['dv']},
  pages   = {pages},
  block   = {block},
  choices = {spec.choices}, percol = {percol}, blanks = {spec.blanks},
  rules   = {{{rules}}},
  title   = {_esc(title)},
  subject = {_esc(subject)},
  color   = {color},
  bw      = {'true' if bw else 'false'}
}}

\\begin{{document}}
{aux_tex}\\gkMake
\\end{{document}}
"""


# =========================================================================
#  编译
# =========================================================================
def find_xelatex() -> str | None:
    exe = shutil.which("xelatex") or shutil.which("xelatex.exe")
    if exe:
        return exe
    cands = []
    for drive in ("C:", "D:", "E:", "F:"):
        cands.append(Path(f"{drive}/texlive"))
    for root in cands:
        if root.is_dir():
            for y in sorted(root.glob("*"), reverse=True):
                for sub in ("bin/windows/xelatex.exe", "bin/xelatex"):
                    f = y / sub
                    if f.exists():
                        return str(f)
    return None


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """执行外部命令，返回 (returncode, 文本输出)。输出编码在 Windows 上不可靠，
    统一按 utf-8 → gbk → latin-1 逐级降级解码，绝不抛异常。"""
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True)
    raw = (r.stdout or b"") + (r.stderr or b"")
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return r.returncode, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return r.returncode, raw.decode("utf-8", errors="replace")


def compile_tex(tex: Path, xelatex: str) -> tuple[bool, str]:
    ok = True
    out = ""
    for _ in range(2):
        rc, out = _run([xelatex, "-interaction=nonstopmode", "-halt-on-error", tex.name],
                       cwd=tex.parent)
        if rc != 0:
            ok = False
            break
    errs = [ln for ln in out.splitlines() if ln.startswith("!")]
    if errs:
        ok = False
        out = "\n".join(errs[:8])
    return ok, out


def pdf_pages(pdf: Path) -> int | None:
    info = shutil.which("pdfinfo")
    if info:
        _, out = _run([info, str(pdf)])
        m = re.search(r"Pages:\s*(\d+)", out)
        if m:
            return int(m.group(1))
    try:                                        # 兜底：数 /Type /Page 或 /Count
        data = pdf.read_bytes()
        m = re.search(rb"/Count\s+(\d+)", data)
        if m:
            return int(m.group(1))
        n = len(re.findall(rb"/Type\s*/Page[^s]", data))
        return n or None
    except Exception:
        return None


# =========================================================================
#  CLI
# =========================================================================
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="从试卷 .tex 自动生成答题卡（A4/A3）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("tex", help="试卷 .tex 路径")
    ap.add_argument("--layout", choices=["a4", "a3", "both"], default="a4",
                    help="版面：a4（默认）/ a3 / both")
    ap.add_argument("--pages", type=int, default=None,
                    help="强制版面数（a4=页数，a3=张数）；默认自动推算")
    ap.add_argument("--block", type=int, default=2, help="每面最多几道解答题（默认 2）")
    ap.add_argument("--percol", type=int, default=4, help="选择题每列题数（默认 4）")
    ap.add_argument("--title", default=None, help="覆盖考试名称")
    ap.add_argument("--subject", default=None, help="覆盖科目（默认 数学）")
    ap.add_argument("--color", default="GKpink", help="主色（默认 GKpink）")
    ap.add_argument("--bw", action="store_true", help="黑白版")
    ap.add_argument("--no-compile", action="store_true", help="只生成 .tex，不编译")
    ap.add_argument("--keep-aux", action="store_true", help="保留 .aux/.log 等编译中间文件")
    ap.add_argument("--no-figs", action="store_true",
                    help="不附带解答题的图/三线表（只出纯答题区）")
    ap.add_argument("--print-spec", action="store_true", help="只打印解析结果，不生成文件")
    ap.add_argument("--out-dir", default=None, help="输出目录（默认与试卷同目录）")
    ap.add_argument("--suffix", default="答题卡", help="输出文件名后缀（默认 答题卡）")
    ap.add_argument("--force", action="store_true",
                    help="允许覆盖非本脚本生成的文件（如手工答题卡）")
    # 手工兜底
    ap.add_argument("--single", type=int, default=None, help="单选题数（覆盖解析）")
    ap.add_argument("--multi", type=int, default=None, help="多选题数（覆盖解析）")
    ap.add_argument("--blanks", type=int, default=None, help="填空题数（覆盖解析）")
    ap.add_argument("--solves", default=None,
                    help='解答题 "题号/分值" 串，如 "15/13,16/15,17/15"')
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    src = Path(args.tex).expanduser().resolve()
    if not src.exists():
        print(f"[ERROR] 找不到文件：{src}", file=sys.stderr)
        return 2

    # 答题卡要从「学生版试题」解析；答案/教师版/答题卡本身都不适用
    if re.search(r"答案|教师版|答题卡|解析|详解|分析|细目表", src.stem):
        print(f"[ERROR] 「{src.name}」不是学生版试题（含 答案/教师版/答题卡 字样），"
              f"请改用同目录的学生版 .tex。", file=sys.stderr)
        return 4

    spec = parse_exam_tex(src)
    if args.no_figs:
        spec.aux = {}

    # ── 手工覆盖 ──
    if args.single is not None:
        spec.single = args.single
    if args.multi is not None:
        spec.multi = args.multi
    if args.blanks is not None:
        spec.blanks = args.blanks
    if args.solves:
        pairs = []
        for chunk in args.solves.replace("，", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            q, _, s = chunk.partition("/")
            pairs.append((int(q), int(s)))
        spec.solve_start = pairs[0][0] if pairs else 0
        spec.solve_scores = [s for _, s in pairs]
    if args.title:
        spec.title = args.title
    if args.subject:
        spec.subject = args.subject

    if args.print_spec:
        print(f"源文件    : {spec.source}")
        print(f"标题      : {spec.title}")
        print(f"科目      : {spec.subject}")
        print(f"单选题    : {spec.single}")
        print(f"多选题    : {spec.multi}")
        print(f"填空题    : {spec.blanks}")
        print(f"解答题    : {spec.solves}")
        print(f"解答题分值: {sum(spec.solve_scores)}")
        if spec.aux:
            print(f"附图/表   : {len(spec.aux)} 题")
            for q in sorted(spec.aux):
                desc = "、".join(
                    f"{'通栏' if m == 'block' else '角图'}≈{h:.1f}cm"
                    for m, _, h in spec.aux[q])
                print(f"            {q}：{desc}")
        else:
            print("附图/表   : 无")
        for w in spec.warnings:
            print(f"[WARN] {w}")
        return 0

    if spec.choices == 0 and spec.blanks == 0:
        hint = ""
        raw = src.read_text(encoding="utf-8", errors="replace")
        if "\\item" not in raw:
            hint = ("\n        该文件里没有任何 \\item，像是未转换的 Markdown 或非学生版试题，"
                    "请先把它排成 LaTeX 试卷。")
        print("[ERROR] 未解析出任何题量，请用 --single/--multi/--blanks 手动指定。" + hint,
              file=sys.stderr)
        return 3

    for w in spec.warnings:
        print(f"[WARN] {w}")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    layouts = ["a4", "a3"] if args.layout == "both" else [args.layout]
    xelatex = None if args.no_compile else find_xelatex()
    if not args.no_compile and not xelatex:
        print("[WARN] 未找到 xelatex，跳过编译（仅生成 .tex）")

    # ── 先决定要写哪些文件（含覆盖保护），再动手 ──
    rc = 0
    targets: list[tuple[str, Path, int, int]] = []
    a4_panels, block, layout_notes = fit_layout_for_aux(spec, args.block, args.percol)
    for note in layout_notes:
        print(note if note.startswith("[WARN]") else f"[INFO] {note}")
    for layout in layouts:
        if layout == "a3":
            pages = args.pages if args.pages is not None else math.ceil(a4_panels / 2)
        else:
            pages = args.pages if args.pages is not None else a4_panels

        name = f"{src.stem}-{args.suffix}" + ("" if layout == "a4" else "-A3")
        tex = out_dir / f"{name}.tex"

        # 不覆盖别人的手工文件：只认本脚本写的（带生成标记）
        if tex.exists() and not args.force:
            old = tex.read_text(encoding="utf-8", errors="replace")[:400]
            if GEN_MARK not in old:
                print(f"[SKIP] {tex.name} 已存在且不是本脚本生成的（疑似手工版），"
                      f"未覆盖。确认要替换请加 --force，或换 --suffix。", file=sys.stderr)
                rc = 5
                continue

        targets.append((layout, tex, pages, block))

    if not targets:
        return rc

    # 宏包副本：保证日后可单独重编
    if STY_SRC.exists():
        dst = out_dir / "answersheet.sty"
        if not dst.exists() or dst.read_bytes() != STY_SRC.read_bytes():
            shutil.copy2(STY_SRC, dst)

    for layout, tex, pages, block in targets:
        tex.write_text(
            render_tex(spec, layout=layout, pages=pages, block=block,
                       percol=args.percol, title=spec.title,
                       subject=spec.subject, color=args.color, bw=args.bw),
            encoding="utf-8",
        )
        unit = "张" if layout == "a3" else "版面"
        print(f"[OK] {tex.name}  （{layout.upper()} · {pages} {unit} · 每面 ≤{block} 题）")

        if not xelatex:
            continue
        ok, log = compile_tex(tex, xelatex)

        # 附图/表来自原卷，可能引用了答题卡里没有的宏或图片。
        # 编译失败时自动退回「不带图」的版本，保证答题卡本身能出来。
        if not ok and spec.aux:
            print(f"[WARN] 带图编译失败，退回纯答题区重试。错误摘要：\n{log}",
                  file=sys.stderr)
            spec.aux = {}
            a4p, blk2 = choose_layout_params(spec, args.block, args.percol)
            pages = args.pages if args.pages is not None else (
                math.ceil(a4p / 2) if layout == "a3" else a4p)
            tex.write_text(
                render_tex(spec, layout=layout, pages=pages, block=blk2,
                           percol=args.percol, title=spec.title,
                           subject=spec.subject, color=args.color, bw=args.bw),
                encoding="utf-8",
            )
            block = blk2
            print(f"[OK] {tex.name}  （已退回无图版 · {pages} 版面）")
            ok, log = compile_tex(tex, xelatex)

        pdf = tex.with_suffix(".pdf")
        if ok and pdf.exists():
            n = pdf_pages(pdf)
            print(f"[OK] {pdf.name}  （{n} 页）")
        else:
            print(f"[ERROR] 编译失败：{tex.name}\n{log}", file=sys.stderr)
            rc = 1

        if not args.keep_aux:
            for ext in (".aux", ".log", ".out", ".toc"):
                f = tex.with_suffix(ext)
                if f.exists():
                    f.unlink()

    return rc


if __name__ == "__main__":
    sys.exit(main())
