#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2exam.py — 试题 Markdown → 试卷 LaTeX（XeLaTeX / ctexart）

用法：
    python md2exam.py <试题md> <输出tex> --img-base Images-<卷名>

设计目标：
    * 面向 48 套不同来源、排版各异的模拟卷 MD，尽量容错；
    * 无法处理的片段写入 stderr 但不中断（绝不崩溃）；
    * 统一清除文本/页眉页脚/图片 三类水印；
    * 清洗 MinerU OCR 产生的公式多余空格，保证可编译。

生成 tex 内图片用相对路径，配合 \\graphicspath{{<img-base>/}}。
"""

import argparse
import os
import re
import shutil
import struct
import sys
from collections import Counter

# --------------------------------------------------------------------------- #
#  一、全局配置
# --------------------------------------------------------------------------- #

# 水印关键字：出现在整行 → 丢弃该行；出现在 \text{...} 内 → 丢弃该片段
WATERMARK_KEYWORDS = [
    "微信公众号", "公众号", "浙考神墙", "神墙", "微信",
    "QQ：", "QQ:", "QQ号", "QQ群", "QQ ",
    "扫码关注", "扫描二维码", "关注我们", "抖音", "哔哩", "B站",
    "头条号", "百家号", "小红书", "版权所有", "侵权", "禁止转载", "未经授权",
]

# 页眉/页脚/页码整行模式（严格，避免误伤正文）
FOOTER_PATTERNS = [
    re.compile(r"^第?\s*\d+\s*页(\s*[/,，]?\s*共\s*\d+\s*页)?\s*$"),
    re.compile(r"^共\s*\d+\s*页\s*$"),
    re.compile(r"^[-—\s]*\d+\s*[-—\s]*$"),  # 形如 "— 3 —"
]

# \text{...} 一类"内容型"命令：其参数内部不做空格压缩
TEXT_CMDS = [
    "text", "textrm", "textnormal", "textup", "textit", "textbf",
    "textsf", "texttt", "mathrm", "mathbf", "mathit", "mathsf", "mathtt",
    "mathbb", "mathcal", "mathfrak", "operatorname", "mbox", "hbox",
]

# 间距命令（清洗时需原样保护）
SPACING_CMDS = [
    "\\,", "\\;", "\\:", "\\!", "\\ ", "\\quad", "\\qquad",
    "\\enspace", "\\thinspace", "\\medspace", "\\thickspace", "\\ ",
]

# 题型判定
SEC_SINGLE = "single"
SEC_MULTI = "multi"
SEC_FILL = "fill"
SEC_SOLVE = "solve"

# 输出诊断
_WARN_COUNT = {"n": 0}


def eprint(*args):
    """统一诊断输出到 stderr。"""
    print("[md2exam]", *args, file=sys.stderr)


def warn(msg):
    _WARN_COUNT["n"] += 1
    eprint("WARN:", msg)


# --------------------------------------------------------------------------- #
#  二、水印过滤（行级 + 片段级）
# --------------------------------------------------------------------------- #

def has_watermark_keyword(text):
    return any(k in text for k in WATERMARK_KEYWORDS)


def is_watermark_line(line):
    """判断整行是否为水印（推广 / 页眉 / 页脚 / 页码）。"""
    s = line.strip()
    if not s:
        return False
    for pat in FOOTER_PATTERNS:
        if pat.match(s):
            return True
    if has_watermark_keyword(s):
        cleaned = s
        for k in WATERMARK_KEYWORDS:
            cleaned = cleaned.replace(k, "")
        cleaned = re.sub(
            r"[\s\d:：,，。.、\-—/\\|()（）\[\]【】#*＋+★☆·~]+", "", cleaned
        )
        if len(cleaned) <= 3:
            return True
    return False


def strip_watermark_fragments(text):
    """
    片段级水印清洗（作用于含公式的整行）：
      * 删除内容含水印关键字的 \\text{...}；
      * 将因此变空 / 命中水印的 \\underline{...} 统一改写为 \\blank；
      * 删除孤立的 \\text{神墙} 之类残留。
    """
    if not text:
        return text

    # 1) 含关键字的 \text{...} → 空
    def _drop_text(m):
        body = m.group(1)
        if has_watermark_keyword(body):
            return ""
        # 空 body 也删（多为水印残留）
        if body.strip() == "":
            return ""
        return m.group(0)

    text = re.sub(r"\\text\s*\{([^{}]*)\}", _drop_text, text)

    # 2) 空 \underline{} / \underline{\hspace{...}} → \blank
    text = re.sub(r"\\underline\s*\{\s*\}", r"\\blank", text)
    text = re.sub(
        r"\\underline\s*\{\s*\\hspace\s*\{[^{}]*\}\s*\}", r"\\blank", text
    )
    # 3) 仍含关键字的 \underline{...} → \blank
    text = re.sub(
        r"\\underline\s*\{([^{}]*)\}",
        lambda m: r"\\blank" if has_watermark_keyword(m.group(1)) else m.group(0),
        text,
    )

    # 4) 兜底：残留的 \text{神墙} 等价物（可能带空格）
    text = re.sub(
        r"\\text\s*\{[^{}]*神墙[^{}]*\}", "", text
    )
    return text


# 行内水印 token（可能在标题/题干/选项行内出现，需就地删除）。
# MinerU 常把页眉/页脚水印文字与正文拼到同一行，整行判定（is_watermark_line）
# 无法命中，必须就地切除这些片段而保留正文。
_INLINE_WM_RES = [
    re.compile(r"微信公众号[：:]?\s*[^\s，。；;、]*"),   # 微信公众号：<名字/号码>
    re.compile(r"(?:浙考)?神墙\s*\d*"),                  # 浙考神墙750 / 神墙
    re.compile(r"QQ\s*(?:群|号)?[：:]?\s*\d+"),          # QQ：2754808740 / QQ号123
    re.compile(r"(?:扫码|扫描二维码)\s*(?:关注|查看更多)?"),
    re.compile(r"关注(?:我们|公众号)"),
]


def strip_inline_watermark(line):
    """就地删除行内残留水印 token（公众号标签 / 浙考神墙 / QQ 号 等）。

    与 ``is_watermark_line``（整行判定）互补：仅当确有删除时，才清理行尾
    遗留的分隔符，避免误伤正常正文的结尾标点。
    """
    if not line:
        return line
    new = line
    for pat in _INLINE_WM_RES:
        new = pat.sub("", new)
    if new != line:
        # 确有删除 → 清理行尾遗留的分隔符/空白
        new = re.sub(r"[\s；;，,、]+$", "", new)
    return new


def filter_lines(lines):
    """行级过滤：行内水印 + 整行水印 + 重复跑马行 + 尾部双空格。"""
    # 去 markdown 硬换行（行尾两个空格）
    lines = [re.sub(r"[ \t]+$", "", ln) for ln in lines]

    kept = []
    for ln in lines:
        was_blank = (ln.strip() == "")
        ln = strip_inline_watermark(ln)
        # 原本非空、清洗后变空 → 纯水印行，丢弃（保留源文件的空行作段落分隔）
        if not was_blank and ln.strip() == "":
            continue
        # 清洗后只剩 markdown 井号标记 → 丢弃
        if re.fullmatch(r"#{1,6}[ \t]*", ln):
            continue
        if is_watermark_line(ln):
            continue
        kept.append(ln)

    # 重复出现的短行（无公式、非标题、非数字开头）视为页眉/跑马灯
    cnt = Counter(ln.strip() for ln in kept if ln.strip())
    drop = set()
    for k, v in cnt.items():
        if v < 3:
            continue
        if len(k) < 4 or len(k) > 40:
            continue
        if "$" in k or k.startswith("#"):
            continue
        if k[0].isdigit():
            continue
        drop.add(k)
    if drop:
        warn("检测到重复跑马行并删除: %s" % "; ".join(sorted(drop)[:5]))
        kept = [ln for ln in kept if ln.strip() not in drop]

    return kept


# --------------------------------------------------------------------------- #
#  三、公式清洗（压缩 OCR 多余空格）
# --------------------------------------------------------------------------- #

def _protect_cmd_args(s):
    """把 \\text{...} 等命令的整段参数替换为占位符，避免内部被清洗。"""
    store = []
    pat = re.compile(r"\\(?:" + "|".join(TEXT_CMDS) + r")\s*\{")
    out = []
    i = 0
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        j = m.end()
        depth = 1
        while j < len(s) and depth > 0:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
            j += 1
        inner = s[m.end(): j - 1]
        cmd = re.match(r"\\[A-Za-z]+", m.group(0)).group(0)
        store.append((cmd, inner))
        out.append("\ue000%d\ue001" % (len(store) - 1))
        i = j
    return "".join(out), store


def _protect_tokens(s, items, lo, hi):
    """把一组字面量替换为带序号的占位符。"""
    store = []
    for it in items:
        while it in s:
            store.append(it)
            s = s.replace(it, "%s%d%s" % (lo, len(store) - 1, hi), 1)
    return s, store


def _restore(s, store, lo, hi):
    for k in range(len(store) - 1, -1, -1):
        s = s.replace("%s%d%s" % (lo, k, hi), store[k])
    return s


def clean_math(s):
    """清洗数学模式内容：压缩 OCR 多余空格，合并被拆散的字母/数字。"""
    if s is None:
        return ""
    s = s.strip()
    if not s:
        return s

    # 1) 保护 \text{...} 参数
    s, protected = _protect_cmd_args(s)

    # 2) 保护间距命令
    s, sp = _protect_tokens(s, SPACING_CMDS, "\ue002", "\ue003")

    # 3) 保护命令名（\alpha 等），避免 "A B" 合并时把 "\alpha x" 粘连
    def _prot_cmdname(m):
        return m.group(0)
    # 用占位符替换命令名
    cmds = []

    def _repl_cmd(m):
        cmds.append(m.group(0))
        return "\ue004%d\ue005" % (len(cmds) - 1)

    s = re.sub(r"\\[A-Za-z]+", _repl_cmd, s)

    # 4) 空格压缩
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([_^])\s*", r"\1", s)          # x _ {0} → x_{0}
    s = re.sub(r"\s*\{\s*", "{", s)                # \sqrt {2} → \sqrt{2}
    s = re.sub(r"\s*\}\s*", "}", s)
    s = re.sub(r",\s+", ", ", s)

    # 数字被拆开：1 3 5 → 135
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)

    # 字母被拆开：A B C → ABC（占位符不是字母，天然隔断命令名）
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"(?<![A-Za-z])([A-Za-z])\s+(?=[A-Za-z](?![A-Za-z]))", r"\1", s)

    s = re.sub(r"\s{2,}", " ", s).strip()

    # 5) 还原命令名
    for k in range(len(cmds) - 1, -1, -1):
        s = s.replace("\ue004%d\ue005" % k, cmds[k])
    # 6) 还原间距命令
    s = _restore(s, sp, "\ue002", "\ue003")
    # 7) 还原 \text{...}
    for k in range(len(protected) - 1, -1, -1):
        cmd, inner = protected[k]
        s = s.replace("\ue000%d\ue001" % k, cmd + "{" + inner + "}")
    return s


def clean_inline_math_line(line):
    """对整行中的 $...$ 逐段清洗；$ 不配对时告警并原样返回。"""
    if "$" not in line:
        return line
    if line.count("$") % 2 != 0:
        warn("行内 $ 不配对，跳过公式清洗: %s" % line[:60])
        return line

    def _rep(m):
        return "$" + clean_math(m.group(1)) + "$"

    return re.sub(r"\$([^$]*)\$", _rep, line)


def normalize_blanks(text, in_math=False):
    """统一空位表示并保留三角形顶点符号。

    * ▲ / △ / \\bigtriangleup / \\blacktriangle → \\blank（空位）；
    * 数学模式外的「△ABC / \\triangle ABQ」等三角形顶点 → $\\triangle ABC$；
    * in_math=True 时视 text 整体已处于数学模式（行间公式内容），
      不再包裹 $...$，仅把 Unicode △ 规范为 \\triangle。
    """
    if in_math:
        text = text.replace("△", "\\triangle ")
        text = re.sub(r"(\\triangle\s*){2,}", r"\\triangle ", text)
        return text
    # 数学模式外：先把「△ABC / \triangle ABQ」包成 $\triangle ABC$
    text = _wrap_triangle_vertices(text)
    # ▲ （也含黑色三角）总是空位
    text = text.replace("▲", "\\blank").replace("△", "\\blank")
    text = re.sub(r"\\blacktriangle", r"\\blank", text)
    text = re.sub(r"\\bigtriangleup", r"\\blank", text)
    # \triangle 仅当其后不是字母时视为空位（\triangle ABC 是三角形符号）
    text = re.sub(r"\\triangle(?!\s*[A-Za-z])", r"\\blank", text)
    # 清理重复 \blank
    text = re.sub(r"(\\blank\s*){2,}", r"\\blank", text)
    return text


_TRI_VERTEX = re.compile(r"(?:\\triangle|△)\s*([A-Za-z]{1,4})(?![A-Za-z])")


def _wrap_triangle_vertices(text):
    """把数学模式外的三角形顶点（△ABC / \\triangle ABQ）包成 $\\triangle ABC$。"""
    parts = re.split(r"(\$[^$]*\$)", text)
    for i in range(0, len(parts), 2):  # 偶数下标 = 数学模式外
        parts[i] = _TRI_VERTEX.sub(
            lambda m: r"$\triangle %s$" % m.group(1), parts[i]
        )
    return "".join(parts)


# 文本模式外出现的常见 Unicode 数学符号 → LaTeX 命令（避免 XeLaTeX 缺字）
_UNICODE_MATH = {
    "⊂": r"\subset", "⊃": r"\supset", "⊄": r"\not\subset",
    "⊆": r"\subseteq", "⊇": r"\supseteq",
    "⊥": r"\perp", "∥": r"\parallel", "∠": r"\angle",
    "∪": r"\cup", "∩": r"\cap", "∈": r"\in", "∉": r"\notin",
    "≥": r"\geq", "≤": r"\leq", "≠": r"\neq", "≈": r"\approx",
    "±": r"\pm", "×": r"\times", "÷": r"\div", "∞": r"\infty",
    "∅": r"\varnothing", "∴": r"\therefore", "∵": r"\because",
}
_RE_UNI_MATH = re.compile("[" + "".join(map(re.escape, _UNICODE_MATH)) + "]")


def wrap_unicode_math(text):
    """把数学模式外的常见 Unicode 数学符号包成 $...$，避免 XeLaTeX 缺字告警。"""
    parts = re.split(r"(\$[^$]*\$)", text)
    for i in range(0, len(parts), 2):  # 偶数下标 = 数学模式外
        parts[i] = _RE_UNI_MATH.sub(
            lambda m: "$%s$" % _UNICODE_MATH[m.group(0)], parts[i]
        )
    return "".join(parts)


# --------------------------------------------------------------------------- #
#  四、HTML 表格解析
# --------------------------------------------------------------------------- #

def parse_html_table(text):
    """把 <table>...</table> 解析为二维列表（行 × 单元格）。"""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)
        cells = [
            re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
            for c in cells
        ]
        if cells:
            rows.append(cells)
    return rows


def render_tabular(rows):
    """二维列表 → 居中带竖线 tabular（试题用）。"""
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    spec = "|" + "|".join(["c"] * ncol) + "|"
    body = []
    for r in rows:
        r = list(r) + [""] * (ncol - len(r))
        body.append(" & ".join(r) + r" \\")
    lines = [
        r"\begin{center}",
        r"\begin{tabular}{%s}" % spec,
        r"\hline",
    ]
    for i, ln in enumerate(body):
        lines.append(ln)
        lines.append(r"\hline")
    lines += [r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  五、图片
# --------------------------------------------------------------------------- #

def jpeg_size(path):
    """读取 JPEG 宽高（失败返回 None）。"""
    try:
        with open(path, "rb") as f:
            data = f.read(65536)
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = struct.unpack(">H", data[i + 5:i + 7])[0]
                w = struct.unpack(">H", data[i + 7:i + 9])[0]
                return w, h
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seglen
    except Exception:
        return None
    return None


def is_watermark_image(path):
    """宽而扁的无意义水印条（如 590x37）判定。"""
    size = jpeg_size(path)
    if not size:
        return False
    w, h = size
    if h <= 0:
        return False
    if h <= 60 and w / float(h) >= 6:
        return True
    return False


def find_image_file(md_path, rel):
    """在若干候选目录中定位被引用的图片，用于水印尺寸自检。"""
    base = os.path.basename(rel)
    md_dir = os.path.dirname(os.path.abspath(md_path))
    stem = os.path.splitext(os.path.basename(md_path))[0]
    cands = [
        os.path.join(md_dir, stem, "images", base),
        os.path.join(md_dir, "images", base),
        os.path.join(md_dir, stem, base),
        os.path.join(md_dir, base),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def render_images(images, md_path):
    """
    images: [(filename, caption), ...]

    宽度约束：所有 figure 实际渲染宽度 ≤ 0.35\\textwidth（题目铁律）。
      * 1 张 → 0.35\\textwidth 居中；
      * 2 张 → 每张 minipage 0.34\\textwidth、图 \\linewidth 并排（实际 0.34\\textwidth）；
      * ≥3 张 → 每张 minipage ≤0.30\\textwidth、图 \\linewidth 并排（高 2.5cm 限高）。
    水印条（宽扁无意义图）在归集前即被过滤。
    """
    imgs = []
    for fn, cap in images:
        p = find_image_file(md_path, fn)
        if p and is_watermark_image(p):
            warn("跳过水印条图片: %s" % fn)
            continue
        imgs.append((fn, cap))
    if not imgs:
        return []

    def _one(fn, cap, width, height=None):
        """width 为 includegraphics 的完整宽度参数，如 0.35\\textwidth 或 \\linewidth。"""
        opt = "width=%s" % width
        if height:
            opt += ",height=%scm,keepaspectratio" % height
        s = r"\includegraphics[%s]{%s}" % (opt, fn)
        if cap:
            s += r"\\[0.2em]{\small " + cap + "}"
        return s

    out = []
    if len(imgs) == 1:
        fn, cap = imgs[0]
        out.append(r"\begin{center}")
        out.append(_one(fn, cap, r"0.35\textwidth"))
        out.append(r"\end{center}")
    elif len(imgs) == 2:
        # 并排两图：每张实际宽度 0.34\textwidth（≤ 0.35 上限）
        out.append(r"\begin{center}")
        for i in range(2):
            out.append(r"\begin{minipage}[t]{0.34\textwidth}")
            out.append(r"\centering")
            out.append(_one(imgs[i][0], imgs[i][1], r"\linewidth", "3"))
            out.append(r"\end{minipage}" + (r"\hfill" if i == 0 else ""))
        out.append(r"\end{center}")
    else:
        # 三张及以上并排：每张 minipage 宽度自适应，图用 \linewidth（实际 ≤0.35）
        n = len(imgs)
        mw = min(0.30, 0.92 / n)
        out.append(r"\begin{center}")
        for i, (fn, cap) in enumerate(imgs):
            out.append(r"\begin{minipage}[t]{%.2f\textwidth}" % mw)
            out.append(r"\centering")
            out.append(_one(fn, cap, r"\linewidth", "2.5"))
            out.append(r"\end{minipage}%")
            if i != n - 1:
                out.append(r"\hfill")
        out.append(r"\end{center}")
    return out



RE_INCLUDEGRAPHICS = re.compile(r"\\includegraphics\s*\[[^\]]*\]\s*\{([^}]+)\}")


def collect_images(tex_text, out_dir, img_base, src_dirs):
    """
    把 tex 中「实际被 \\includegraphics 引用」的图片，从 src_dirs 拷贝到
    <out_dir>/<img_base>/，跳过水印条与缺失项。

    只拷贝被引用者——images 目录里 MinerU 误识别为图片的水印条（宽扁条）
    与未被正文引用的公式碎片不会被带出。
    """
    dest_dir = os.path.join(out_dir, img_base)
    refs = []
    for m in RE_INCLUDEGRAPHICS.finditer(tex_text):
        fn = os.path.basename(m.group(1).strip())
        # 跳过宏定义里的参数占位符（如 \eqimg 模板中的 #2）与空名
        if not fn or fn.startswith("#"):
            continue
        if fn not in refs:
            refs.append(fn)

    os.makedirs(dest_dir, exist_ok=True)
    copied = 0
    skipped_wm = 0
    missing = []
    for fn in refs:
        src = None
        for d in src_dirs:
            cand = os.path.join(d, fn)
            if os.path.exists(cand):
                src = cand
                break
        if src is None:
            missing.append(fn)
            continue
        if is_watermark_image(src):
            skipped_wm += 1
            warn("归集时跳过水印条图片: %s" % fn)
            continue
        dest = os.path.join(dest_dir, fn)
        if os.path.exists(dest):
            continue
        shutil.copy2(src, dest)
        copied += 1

    if missing:
        warn("以下被引用图片未找到（%d）：%s" % (len(missing), "; ".join(missing[:5])))
    eprint("图片归集：引用 %d 张，新拷贝 %d 张，跳过水印 %d 张 → %s"
           % (len(refs), copied, skipped_wm, dest_dir))
    return copied


# --------------------------------------------------------------------------- #
#  六、选项处理
# --------------------------------------------------------------------------- #

_OPTION_SPLIT = re.compile(r"(?:(?<![A-Za-z0-9])|^)([A-D])\s*[.．、]\s*")


def split_inline_options(line):
    """分离 "题干 A. xx B. xx" 这种与选项同行的写法。

    返回 (prefix, options_text)；未识别到选项时 options_text 为 None。
    """
    line = line.rstrip()
    matches = list(_OPTION_SPLIT.finditer(line))
    if len(matches) < 2 or matches[0].group(1) != "A":
        return line, None
    prefix = line[:matches[0].start()].rstrip()
    opts = line[matches[0].start():].strip()
    return prefix, opts


def split_options(text):
    """把 "A. xx B. xx ..."（一行多个或已拼接的多行）拆成选项内容列表。"""
    text = text.strip()
    if not text:
        return []
    matches = list(_OPTION_SPLIT.finditer(text))
    if not matches or matches[0].group(1) != "A":
        return []
    opts = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        opts.append(text[start:end].strip())
    return opts


def auto_tasks_cols(options):
    """自动判断 tasks 列数（见 SKILL 规则，公式按源长度折算宽度）。"""
    if not options:
        return 4
    has_image = any(r"\includegraphics" in o for o in options)
    if has_image:
        avg = sum(len(o) for o in options) / float(len(options))
        return 4 if avg < 80 else 2

    def _vis_width(o):
        def _rep(m):
            inner = m.group(0)[1:-1].strip()
            return "\u2588" * max(1, min(int(len(inner) / 2) + 1, 30))
        s = re.sub(r"\$[^$]*\$", _rep, o)
        s = re.sub(r"\\[A-Za-z]+\*?", "", s)
        s = s.replace("&", "").replace("\\", "")
        w = 0.0
        for ch in s:
            if "\u4e00" <= ch <= "\u9fff":
                w += 1.6
            elif ch == "\u2588":
                w += 1.0
            elif ch.isspace():
                continue
            else:
                w += 1.0
        return w

    w = max(_vis_width(o) for o in options)
    return 4 if w <= 15 else 2


# --------------------------------------------------------------------------- #
#  七、文本转义（非数学区）
# --------------------------------------------------------------------------- #

def escape_text(s):
    """转义非数学区的 LaTeX 特殊字符，避免编译错误。"""
    parts = re.split(r"(\$[^$]*\$)", s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<!\\)([#&%])", r"\\\1", parts[i])
        parts[i] = re.sub(r"(?<!\\)_", r"\\_", parts[i])
    return "".join(parts)


# --------------------------------------------------------------------------- #
#  八、MD 结构与区块解析
# --------------------------------------------------------------------------- #

RE_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
RE_ITEM_NUM = re.compile(r"^\s*(\d{1,2})\s*[.．、]\s*(?!\d)(.*)$")
RE_OPTION_LINE = re.compile(r"^\s*[A-D]\s*[.．、]")
RE_IMAGE = re.compile(r"^\s*!\[[^\]]*\]\(\s*([^)\s]+)\s*\)\s*$")
RE_SUB_ARABIC = re.compile(r"^\s*[（(]\s*(\d+)\s*[）)]\s*(.*)$")
RE_SUB_ROMAN = re.compile(r"^\s*[（(]\s*(i{1,3}|iv|vi{0,3})\s*[）)]\s*(.*)$", re.I)


# 说明性标题（无题型信息，仅作卷/部分划分）：不得注册为题型区块。
#   「选择题部分（共58分）」「非选择题部分（共92分）」…
_RE_SECTION_NOTE = re.compile(r"部分\s*[（(]?\s*共\s*\d+\s*分")


def _is_section_note(title):
    """是否为说明性标题（"选择题部分（共58分）""非选择题部分（共92分）"）。"""
    if "非选择题" in title:          # 「第Ⅱ卷（非选择题 共92分）」等
        return True
    return bool(_RE_SECTION_NOTE.search(title))


def section_type(title):
    """由标题文本判断题型。

    判定顺序：
      0) 说明性标题（…部分（共N分）、非选择题…）→ None；
      1) 多选：多项选择 / 多选 / 有多项符合 /（多项且符合）/ 部分分；
      2) 填空；
      3) 解答；
      4) 单选：选择题 / 单选 / 单项选择；
      5) 其余 → None。
    """
    if _is_section_note(title):
        return None
    if ("多项选择" in title or "多选" in title
            or "有多项符合" in title
            or ("多项" in title and "符合" in title)
            or "部分分" in title):
        return SEC_MULTI
    if "填空" in title:
        return SEC_FILL
    if "解答" in title:
        return SEC_SOLVE
    if "选择题" in title or "单选" in title or "单项选择" in title:
        return SEC_SINGLE
    return None


# 纯文本题型标题识别（应对 MinerU 丢掉 "##"、或把标题并进上一题题干的情况）：
#   行内须出现「中文序号 + 、/．」，且其后 40 字内含题型关键词。
_TYPE_KEYWORDS = ("选择", "填空", "解答", "单选", "多选")
_SENT_END = "。．.；;！!？? \u3000）)】」"


def _find_plain_section_head(line):
    """在（非 markdown 标题的）行内查找题型小节标题。

    返回 (prefix, title)：prefix 为标题之前的正文（可能为空串），
    title 为自标题起点至行尾的文本；找不到或非题型标题返回 None。
    """
    for m in re.finditer(r"[一二三四五六七八九十]{1,3}\s*[、.．]", line):
        # 标题须始于行首，或紧跟在句末标点/空白之后，避免误切题干
        if m.start() != 0 and line[m.start() - 1] not in _SENT_END:
            continue
        tail = line[m.start():].strip()
        if not any(k in tail[:40] for k in _TYPE_KEYWORDS):
            continue
        if not section_type(tail):
            continue
        return line[:m.start()], tail
    return None


def _heading_of(line):
    """取一行的题型标题：markdown 标题取标题文本，否则查找行内纯文本标题。"""
    m = RE_HEADING.match(line)
    if m:
        return m.group(2).strip()
    hit = _find_plain_section_head(line)
    return hit[1] if hit else None


def _split_embedded_headings(lines):
    """把「题干末尾拼接了题型标题」的行拆成 [题干行, 标题行]。

    例：``…数学期望为 △ 。四、解答题：本题共 5 小题…``
    → ``['…数学期望为 △ 。', '四、解答题：本题共 5 小题…']``
    """
    out = []
    for ln in lines:
        if RE_HEADING.match(ln):
            out.append(ln)
            continue
        hit = _find_plain_section_head(ln)
        if hit and hit[0].strip():
            out.append(hit[0].rstrip())
            out.append(hit[1])
        else:
            out.append(ln)
    return out


def collapse_dollar_blocks(text):
    """把跨行的 $$...$$ 块压成单行，方便逐行处理。"""
    def _rep(m):
        inner = clean_math(m.group(1))
        return "\n$$ " + inner + " $$\n"
    return re.sub(r"\$\$(.+?)\$\$", _rep, text, flags=re.S)


def split_paragraphs(lines):
    """按空行切段（保留段内行）。"""
    paras = []
    cur = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                paras.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append(cur)
    return paras


# --------------------------------------------------------------------------- #
#  九、试题解析
# --------------------------------------------------------------------------- #

class Question(object):
    def __init__(self, num):
        self.num = num
        self.blocks = []      # ("text", str) / ("image", fn, cap) / ("formula", str)

    def add_text(self, s):
        if s.strip():
            self.blocks.append(("text", s))

    def add_formula(self, s):
        self.blocks.append(("formula", s))

    def add_image(self, fn, cap):
        self.blocks.append(("image", fn, cap))

    # 选项单独维护
    options = None


def parse_mcq(lines, md_path, start_idx, end_idx):
    """解析选择题区块（单选/多选）。"""
    questions = []
    cur = None
    i = start_idx
    while i < end_idx:
        ln = lines[i]
        s = ln.strip()
        if s == "":
            i += 1
            continue

        # 编号标题「## 16. …」等价于「16. …」（MinerU 把题号标成了 markdown 标题）
        mh_item = RE_HEADING.match(ln)
        m = RE_ITEM_NUM.match(mh_item.group(2).strip() if mh_item else ln)
        if m:
            if cur is not None:
                questions.append(cur)
            cur = {"num": int(m.group(1)), "blocks": [], "options_raw": []}
            rest = m.group(2).strip()
            if rest:
                pre, iopt = split_inline_options(rest)
                if iopt:
                    if pre:
                        cur["blocks"].append(("text", pre))
                    cur["options_raw"].append(iopt)
                else:
                    cur["blocks"].append(("text", rest))
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        # markdown 标题行（含"选择题部分/非选择题部分"等无题型信息的说明性
        # heading）一律跳过，避免被误并入上一题题干。
        if RE_HEADING.match(ln):
            i += 1
            continue

        if RE_OPTION_LINE.match(ln):
            cur["options_raw"].append(s)
            i += 1
            continue

        mi = RE_IMAGE.match(ln)
        if mi:
            fn = os.path.basename(mi.group(1))
            cap = ""
            if i + 1 < end_idx:
                nxt = lines[i + 1].strip()
                if (nxt and not RE_IMAGE.match(nxt) and not RE_ITEM_NUM.match(nxt)
                        and not RE_OPTION_LINE.match(nxt)
                        and not RE_HEADING.match(nxt)
                        and not nxt.startswith("$") and len(nxt) <= 60):
                    cap = nxt
                    i += 1
            cur["blocks"].append(("image", fn, cap))
            i += 1
            continue

        # 其它文本（题干续行）
        cur["blocks"].append(("text", s))
        i += 1

    if cur is not None:
        questions.append(cur)
    return questions


def parse_fill(lines, start_idx, end_idx):
    """解析填空题区块。"""
    questions = []
    cur = None
    i = start_idx
    while i < end_idx:
        ln = lines[i]
        s = ln.strip()
        if s == "":
            i += 1
            continue
        # 编号标题「## 16. …」等价于「16. …」（MinerU 把题号标成了 markdown 标题）
        mh_item = RE_HEADING.match(ln)
        m = RE_ITEM_NUM.match(mh_item.group(2).strip() if mh_item else ln)
        if m:
            if cur is not None:
                questions.append(cur)
            cur = {"num": int(m.group(1)), "blocks": []}
            rest = m.group(2).strip()
            if rest:
                cur["blocks"].append(("text", rest))
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if RE_HEADING.match(ln):
            i += 1
            continue
        mi = RE_IMAGE.match(ln)
        if mi:
            fn = os.path.basename(mi.group(1))
            cur["blocks"].append(("image", fn, ""))
            i += 1
            continue
        cur["blocks"].append(("text", s))
        i += 1
    if cur is not None:
        questions.append(cur)
    return questions


def parse_solve(lines, start_idx, end_idx, md_path):
    """解析解答题区块（含多级小问）。"""
    questions = []
    cur = None  # {"num", "stem":[], "subs":[{"num","blocks":[],"subsubs":[...]}]}
    cur1 = None
    cur2 = None
    i = start_idx
    last_num = 0

    def flush():
        if cur is not None:
            questions.append(cur)

    while i < end_idx:
        ln = lines[i]
        s = ln.strip()
        if s == "":
            i += 1
            continue

        # 编号标题「## 16. …」等价于「16. …」（MinerU 把题号标成了 markdown 标题）
        mh_item = RE_HEADING.match(ln)
        m = RE_ITEM_NUM.match(mh_item.group(2).strip() if mh_item else ln)
        if m:
            flush()
            num = int(m.group(1))
            last_num = num
            cur = {"num": num, "stem": [], "subs": []}
            cur1 = None
            cur2 = None
            rest = m.group(2).strip()
            if rest:
                cur["stem"].append(("text", rest))
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        # 标题行跳过（防止 "## 三、填空题" 等被并入上一题题干）
        if RE_HEADING.match(ln):
            i += 1
            continue

        # 图片
        mi = RE_IMAGE.match(ln)
        if mi:
            fn = os.path.basename(mi.group(1))
            cap = ""
            if i + 1 < end_idx:
                nxt = lines[i + 1].strip()
                if (nxt and not RE_IMAGE.match(nxt) and not RE_ITEM_NUM.match(nxt)
                        and not RE_HEADING.match(nxt) and not nxt.startswith("$")
                        and len(nxt) <= 60):
                    cap = nxt
                    i += 1
            blk = ("image", fn, cap)
            (cur2["blocks"] if cur2 else (cur1["blocks"] if cur1 else cur["stem"])).append(blk)
            i += 1
            continue

        # 行间公式（$$ 已压成单行）
        mf = re.match(r"^\$\$(.*)\$\$$", s, flags=re.S)
        if mf:
            blk = ("formula", mf.group(1).strip())
            (cur2["blocks"] if cur2 else (cur1["blocks"] if cur1 else cur["stem"])).append(blk)
            i += 1
            continue

        # 小问（罗马优先，避免与阿拉伯混淆）
        mr = RE_SUB_ROMAN.match(s)
        if mr and cur1 is not None:
            cur2 = {"num": mr.group(1), "blocks": []}
            cur1["subsubs"].append(cur2)
            rest = mr.group(2).strip()
            if rest:
                cur2["blocks"].append(("text", rest))
            i += 1
            continue

        ma = RE_SUB_ARABIC.match(s)
        if ma:
            cur2 = None
            cur1 = {"num": int(ma.group(1)), "blocks": [], "subsubs": []}
            cur["subs"].append(cur1)
            rest = ma.group(2).strip()
            if rest:
                cur1["blocks"].append(("text", rest))
            i += 1
            continue

        blk = ("text", s)
        (cur2["blocks"] if cur2 else (cur1["blocks"] if cur1 else cur["stem"])).append(blk)
        i += 1

    flush()
    return questions


# --------------------------------------------------------------------------- #
#  十、渲染
# --------------------------------------------------------------------------- #

def render_blocks(blocks, md_path, out):
    """把区块序列渲染为 LaTeX 行，追加到 out。"""
    for blk in blocks:
        if blk[0] == "text":
            txt = blk[1]
            txt = strip_watermark_fragments(txt)
            txt = clean_inline_math_line(txt)
            txt = normalize_blanks(txt)
            txt = wrap_unicode_math(txt)
            out.append(escape_text(txt))
        elif blk[0] == "formula":
            fx = strip_watermark_fragments(blk[1])
            fx = normalize_blanks(clean_math(fx), in_math=True)
            out.append(r"\[%s\]" % fx)
        elif blk[0] == "image":
            imgs = render_images([(blk[1], blk[2])], md_path)
            out.extend(imgs)


def render_image_group(blocks, md_path, out):
    """把 blocks 中连续的 image 合并渲染（支持多图并排）。"""
    i = 0
    while i < len(blocks):
        if blocks[i][0] == "image":
            group = []
            j = i
            while j < len(blocks) and blocks[j][0] == "image":
                group.append((blocks[j][1], blocks[j][2]))
                j += 1
            out.extend(render_images(group, md_path))
            i = j
        else:
            render_blocks([blocks[i]], md_path, out)
            i += 1


def render_mcq(questions, section, md_path, start=None):
    out = []
    opt = "itemsep=0.3em" if section == SEC_SINGLE else "itemsep=0.5em"
    if start is not None and start != 1:
        head = r"\begin{enumerate}[start=%d, %s]" % (start, opt)
    else:
        head = r"\begin{enumerate}[%s]" % opt
    out.append(head)
    for q in questions:
        # 题干预排版：先渲染 blocks（文本/公式/图片），再渲染选项
        body = []
        render_image_group(q["blocks"], md_path, body)
        first = body[0] if body else ""
        rest = body[1:]
        out.append(r"    \item " + first)
        out.extend("    " + r for r in rest if r)

        opt_text = " ".join(q["options_raw"])
        opts = split_options(opt_text)
        if opts:
            cols = auto_tasks_cols(opts)
            out.append(r"    \begin{tasks}(%d)" % cols)
            for o in opts:
                body_txt = escape_text(o.strip())
                # tasks 宏会先剥去 \task 后的 '{'，再判断紧随的是否为可选的 "[label]"。
                # 因此当选项正文以字面 "[" 开头（如区间 [0,2)）时，会被误当作可选参数，
                # 一路吞并到文件尾导致 "File ended while scanning"。
                # 用空组 {} 隔断首字符，既避免误判也不产生任何可见输出。
                if body_txt.startswith("["):
                    body_txt = "{}" + body_txt
                out.append("        " + r"\task {%s}" % body_txt)
            out.append(r"    \end{tasks}")
        elif q["options_raw"]:
            warn("第%d题选项解析失败" % q["num"])
    out.append(r"\end{enumerate}")
    return out


def render_fill(questions, start, md_path):
    out_arr = []
    out = out_arr
    head = r"\begin{enumerate}[start=%d, itemsep=0.8em]" % start
    out.append(head)
    for q in questions:
        body = []
        render_image_group(q["blocks"], md_path, body)
        first = body[0] if body else ""
        rest = body[1:]
        out.append(r"    \item " + first)
        out.extend("    " + r for r in rest if r)
    out.append(r"\end{enumerate}")
    return out


def render_solve(questions, start, md_path, itemsep="1.5cm"):
    out = []
    out.append(r"\begin{examenum}[start=%d, itemsep=%s]" % (start, itemsep))
    for q in questions:
        stem = []
        render_image_group(q["stem"], md_path, stem)
        first = stem[0] if stem else ""
        rest = stem[1:]
        out.append(r"    \item " + first)
        out.extend("    " + r for r in rest if r)

        if q["subs"]:
            out.append(r"    \begin{examenum}")
            for sub in q["subs"]:
                subout = []
                render_image_group(sub["blocks"], md_path, subout)
                sfirst = subout[0] if subout else ""
                srest = subout[1:]
                out.append(r"        \item " + sfirst)
                out.extend("        " + r for r in srest if r)
                if sub.get("subsubs"):
                    out.append(r"        \begin{examenum}")
                    for ss in sub["subsubs"]:
                        ssout = []
                        render_image_group(ss["blocks"], md_path, ssout)
                        f0 = ssout[0] if ssout else ""
                        out.append(r"            \item " + f0)
                        out.extend("            " + r for r in ssout[1:] if r)
                    out.append(r"        \end{examenum}")
            out.append(r"    \end{examenum}")
    out.append(r"\end{examenum}")
    return out


# --------------------------------------------------------------------------- #
#  十一、导言区
# --------------------------------------------------------------------------- #

PREAMBLE = r"""% ============================================================
%  高考数学试卷（学生版）——由 md2exam.py 自动生成
%  套用模板 gaokao-template.tex 的导言区风格
%  使用 XeLaTeX 编译
% ============================================================

\documentclass[12pt, a4paper, oneside]{ctexart}

% ── 数学与链接 ──
\usepackage{amsmath, amsthm, amssymb}
\usepackage[bookmarks=true, colorlinks, citecolor=blue, linkcolor=black]{hyperref}

% ── 字体方案（mathptmx + upgreek，对齐 2025.6 成品风格） ──
\usepackage{mathptmx}
\usepackage{upgreek}

% ── 页面布局（1.5cm 边距 + 1.5 倍行距，对齐 2025.6 成品风格） ──
\usepackage[a4paper, margin=1.5cm, footskip=1cm]{geometry}
\linespread{1.5}

% ── 页眉页脚 ──
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{数学试题\,第\thepage 页（共\pageref{LastPage}页）}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% ── 表格与插图 ──
\usepackage{graphicx}
\graphicspath{{__IMGBASE__/}}
\usepackage{adjustbox}
\usepackage{diagbox}
\usepackage{makecell}
\usepackage{caption}
\usepackage{float}
\usepackage{tikz}

% ── 选择题选项 ──
\usepackage{tasks}
\settasks{
    label       = \Alph*.,
    label-width = 1.8em,
    item-indent = 2.4em,
    label-offset = 0.5em,
    column-sep  = 2em,
    before-skip = 0pt,
    after-skip  = 0pt
}

% ── 大题编号 ──
\usepackage[shortlabels]{enumitem}
\newlist{examenum}{enumerate}{3}
\setlist[examenum,1]{label=\arabic*., leftmargin=2em, itemsep=0.3em, parsep=0em}
\setlist[examenum,2]{label=(\arabic*), leftmargin=1.5em, itemsep=0.1em, parsep=0em}
\setlist[examenum,3]{label=(\roman*), leftmargin=1.5em, itemsep=0.1em, parsep=0em}

% ── 自定义命令 ──
\newcommand{\mycircled}[1]{%
  \tikz[baseline=(char.base),outer sep=0pt]{%
    \node[draw,circle,inner sep=0.5pt,minimum size=1.4em,
          line width=0.4pt,font=\zihao{-5}] (char) {#1};%
  }%
}
\newcommand{\Parallel}{\raisebox{0.1ex}{\rotatebox[origin=c]{-20}{$\parallel$}}}
\newcommand{\bigstarraised}{\raisebox{0.2ex}{$\bigstar$}}
\newcommand{\blank}{\underline{\hspace{2cm}}}
\newcommand{\subjecttitle}[1]{{\fontsize{24pt}{22pt}\selectfont\centering\textbf{#1}\par}}
\newcommand{\subtitle}[1]{{\fontsize{16pt}{16pt}\selectfont\centering #1\par}}
\newcommand{\mi}{\mathrm{i}}
\newcommand{\me}{\mathrm{e}}

% ── 答题空间（纯留白，无线条无边框）──
\newcommand{\answerc}{\par\vspace{1.5em}}
\newcommand{\answern}{\par\vspace{3em}}
\newcommand{\answere}{\par\vspace{5em}}

% ============================================================
\begin{document}

"""


def build_title(h1_lines, subtitle_lines):
    out = []
    out.append(r"\begin{center}")
    if h1_lines:
        out.append(r"    {\LARGE\textbf{%s}}\\[0.4em]" % escape_text(h1_lines[0]))
        for extra in h1_lines[1:]:
            out.append(r"    {\Large\textbf{%s}}\\[0.3em]" % escape_text(extra))
    else:
        out.append(r"    {\LARGE\textbf{数学试卷}}")
    out.append(r"\end{center}")
    out.append("")
    if subtitle_lines:
        out.append(r"\begin{center}")
        out.append(r"    {\small %s}" % escape_text(subtitle_lines[0]))
        out.append(r"\end{center}")
        out.append("")
    return out


NOTICE = [
    r"\noindent\textbf{注意事项}：",
    "",
    "1．答卷前，考生务必将自己的姓名、准考证号填写在答题卡上。",
    "",
    "2．回答选择题时，选出每小题答案后，用铅笔把答题卡上对应题目的答案标号涂黑。",
    "如需改动，用橡皮擦干净后，再选涂其它答案标号。回答非选择题时，将答案写在答题卡上，",
    "写在本试卷上无效。",
    "",
    "3．考试结束后，将本试卷和答题卡一并交回。",
    "",
    r"\vspace{1em}",
    "",
]


# --------------------------------------------------------------------------- #
#  十二、主流程
# --------------------------------------------------------------------------- #

def convert(md_path, out_tex, img_base, img_srcs=None):
    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = collapse_dollar_blocks(raw)
    lines = filter_lines(raw.split("\n"))
    # 0) 拆分「题干末尾拼接了题型标题」的行（如 2604「…△ 。四、解答题：…」）
    lines = _split_embedded_headings(lines)

    # 1) 提取顶层标题（# 行）与副标题
    h1_lines = []
    body_start = 0
    for idx, ln in enumerate(lines):
        m = RE_HEADING.match(ln)
        if m and len(m.group(1)) == 1:
            h1_lines.append(m.group(2).strip())
            body_start = idx + 1

    # 若 H1 之后紧跟非 H1 文本行，取作副标题（如"本试卷共4页…"）
    subtitle_lines = []
    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            continue
        if RE_HEADING.match(ln):
            continue
        if s.startswith("注意事项"):
            break
        subtitle_lines.append(s)
        break

    # 2) 定位题型区块
    sections = []  # (type, title, start_idx, end_idx)
    cur = None
    for idx, ln in enumerate(lines):
        title = _heading_of(ln)          # 同时支持 "#" 标题与纯文本「中文序号+、」标题
        if title is None:
            continue
        st = section_type(title)
        if st:
            if cur:
                cur[3] = idx
                sections.append(cur)
            cur = [st, title, idx + 1, len(lines)]
    if cur:
        cur[3] = len(lines)
        sections.append(cur)

    if not sections:
        warn("未识别到任何题型区块，输出空试卷")

    # 3) 逐题型解析渲染
    body = []
    counts = {SEC_SINGLE: 0, SEC_MULTI: 0, SEC_FILL: 0, SEC_SOLVE: 0}
    first_nums = {}

    section_lines = {}  # 缓存解析结果
    for st, title, s, e in sections:
        try:
            if st in (SEC_SINGLE, SEC_MULTI):
                qs = parse_mcq(lines, md_path, s, e)
            elif st == SEC_FILL:
                qs = parse_fill(lines, s, e)
            else:
                qs = parse_solve(lines, s, e, md_path)
        except Exception as ex:  # 容错：单区块失败不影响其它
            warn("区块「%s」解析异常：%s" % (title, ex))
            qs = []
        section_lines[(st, s)] = (title, qs)
        counts[st] += len(qs)
        if qs:
            first_nums[st] = qs[0]["num"]

    # 累计 start
    single_n = counts[SEC_SINGLE]
    multi_n = counts[SEC_MULTI]
    fill_n = counts[SEC_FILL]
    solve_start = single_n + multi_n + fill_n + 1
    multi_start = single_n + 1
    fill_start = single_n + multi_n + 1

    for (st, s), (title, qs) in section_lines.items():
        if not qs:
            warn("区块「%s」无题目" % title)
            continue
        body.append("")
        body.append(r"\noindent\textbf{%s}" % escape_text(title.replace("#", "").strip()))
        body.append("")
        if st == SEC_SINGLE:
            body.extend(render_mcq(qs, SEC_SINGLE, md_path, start=first_nums.get(st)))
        elif st == SEC_MULTI:
            body.extend(render_mcq(qs, SEC_MULTI, md_path, start=first_nums.get(st, multi_start)))
        elif st == SEC_FILL:
            body.extend(render_fill(qs, first_nums.get(st, fill_start), md_path))
        else:
            body.extend(render_solve(qs, first_nums.get(st, solve_start), md_path))
        body.append("")

    # 4) 组装
    tex = [PREAMBLE.replace("__IMGBASE__", img_base)]
    tex.append("\n".join(build_title(h1_lines, subtitle_lines)))
    tex.append("\n".join(NOTICE))
    tex.append("\n".join(body))
    tex.append(r"\end{document}")
    tex.append("")

    os.makedirs(os.path.dirname(os.path.abspath(out_tex)), exist_ok=True)
    text = "\n".join(tex)
    out_dir = os.path.dirname(os.path.abspath(out_tex))
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(text)

    if img_srcs:
        try:
            collect_images(text, out_dir, img_base, img_srcs)
        except Exception as ex:  # 容错：归集失败不影响 tex 产出
            warn("图片归集失败：%s" % ex)

    eprint("已生成：%s" % out_tex)
    eprint("统计：单选 %d，多选 %d，填空 %d，解答 %d；解答 start=%d"
           % (single_n, multi_n, fill_n, counts[SEC_SOLVE], solve_start))
    eprint("警告数：%d" % _WARN_COUNT["n"])
    if counts[SEC_SOLVE] == 0:
        warn("未识别到解答题，请检查 MD 结构")


def main():
    ap = argparse.ArgumentParser(description="试题 Markdown → LaTeX")
    ap.add_argument("md", help="输入试题 Markdown")
    ap.add_argument("out", help="输出 tex 路径")
    ap.add_argument("--img-base", default="images",
                    help="图片目录名（相对 tex），写入 \\graphicspath，并为归集目标目录")
    ap.add_argument("--img-src", default=None,
                    help="源图片目录（可多个，逗号分隔）；提供时把被正文引用的图片"
                         "拷入 <输出tex目录>/<img-base>/，自动剔除水印条")
    args = ap.parse_args()
    if not os.path.exists(args.md):
        eprint("错误：输入文件不存在：%s" % args.md)
        sys.exit(2)
    img_srcs = [s.strip() for s in args.img_src.split(",") if s.strip()] if args.img_src else None
    convert(args.md, args.out, args.img_base, img_srcs)


if __name__ == "__main__":
    main()