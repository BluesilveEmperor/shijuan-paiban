#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tex2chinese.py — 语文成品 tex → 块流 IR（chinese.json）

用途有两个：

1. 把已人工排好的成品卷（`chinese-shiti.tex` / `chinese-daan.tex`）反解成 IR，
   作为 `render_chinese.py` 的回归语料（IR → tex → PDF，与人工 PDF 比对）；
2. 提取器（PDF/DOCX → IR）写好之前，先用成品 tex 作为 IR 的稳定来源。

设计原则：**保真优先，结构化其次**
    * 已知块（sechead / subsechead / material / question / choices / duanju /
      ans / subans / scorenote / translation）解析为结构化字段；
    * 其余一切文本原样保留为 `para` 块，渲染时逐字输出 ——
      因此任何不认识的排版写法都不会丢失。

用法::

    python scripts/render/tex2chinese.py chinese-shiti.tex -o chinese.json
    python scripts/render/tex2chinese.py chinese-daan.tex -o daan.json --kind daan
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# 触发「结构化块」的命令；块间的一切文本都归入 para
BLOCK_STARTS = (
    "\\sechead{", "\\subsechead{", "\\material{", "\\question{",
    "\\duanju{", "\\ans{", "\\subans{", "\\scorenote{", "\\translabel{",
)


class Cursor:
    """带平衡括号读取的文本游标。"""

    def __init__(self, text):
        self.s = text
        self.i = 0
        self.n = len(text)

    def eof(self):
        return self.i >= self.n

    def skip_ws(self):
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "%":                       # 行注释
                while self.i < self.n and self.s[self.i] != "\n":
                    self.i += 1
            else:
                break

    def peek(self, k=0):
        return self.s[self.i:self.i + k]

    def match(self, lit):
        return self.s.startswith(lit, self.i)

    def read_group(self):
        """读一个 {…} 平衡组，返回组内文本；不匹配返回 None。"""
        if self.i >= self.n or self.s[self.i] != "{":
            return None
        depth, start = 0, self.i
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":                        # 跳过转义字符 \{ \}
                self.i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    body = self.s[start + 1:self.i]
                    self.i += 1
                    return body
            self.i += 1
        return None

    def read_cmd(self, name):
        """若当前位置是 \\name{…}，读掉并返回参数；否则返回 None。"""
        if not self.match("\\" + name):
            return None
        save = self.i
        self.i += len(name) + 1
        self.skip_ws()
        arg = self.read_group()
        if arg is None:
            self.i = save
        return arg

    def read_env(self, name):
        """若当前位置是 \\begin{name}，读到对应 \\end{name}，返回内部文本。"""
        head = "\\begin{" + name + "}"
        if not self.match(head):
            return None
        self.i += len(head)
        depth, start = 1, self.i
        open_tag = "\\begin{" + name + "}"
        close_tag = "\\end{" + name + "}"
        while self.i < self.n:
            if self.match(close_tag):
                body = self.s[start:self.i]
                self.i += len(close_tag)
                return body
            if self.match(open_tag):
                depth += 1
            self.i += 1
        return None

    def read_until_block(self):
        """读到下一个 BLOCK_STARTS 之前；返回原文（保持空行语义）。"""
        start = self.i
        while self.i < self.n:
            if any(self.s.startswith(b, self.i) for b in BLOCK_STARTS):
                # 行首才算块起点，避免正文里出现 "\question{" 字样被误切
                line_start = self.s.rfind("\n", 0, self.i) + 1
                if not self.s[line_start:self.i].strip():
                    break
            self.i += 1
        return self.s[start:self.i]


def _clean_paras(text):
    return text.strip("\n")


def parse_meta(text, kind_hint=None):
    meta = {}
    body_at = text.find("\\begin{document}")
    head = text[:body_at] if body_at >= 0 else ""

    m = re.search(r"\\examfooter\{([^}]*)\}", head)
    if m:
        meta["footer"] = m.group(1).strip()

    if "\\answertitle" in text:
        m = re.search(r"\\answertitle\{((?:[^{}]|\{[^{}]*\})*)\}\{([^}]*)\}", text)
        meta["kind"] = "daan"
    else:
        m = re.search(r"\\examtitle\{((?:[^{}]|\{[^{}]*\})*)\}\{([^}]*)\}", text)
        meta["kind"] = "shiti"
    if m:
        meta["title"] = m.group(1).strip()
        meta["subtitle"] = m.group(2).strip()
    if kind_hint:
        meta["kind"] = kind_hint

    m = re.search(r"\\examnote\{((?:[^{}]|\{[^{}]*\})*)\}", text)
    if m:
        meta["exam_note"] = m.group(1).strip()

    # ywexam 之外的额外宏包（如 graphicx / multirow）：原样带进 IR，
    # 否则渲染时表格会因缺宏包而错位
    pkgs = re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}", head)
    extra = []
    for grp in pkgs:
        for p in grp.split(","):
            p = p.strip()
            if p and p != "ywexam" and p not in extra:
                extra.append(p)
    if extra:
        meta["extra_packages"] = extra
    return meta


def parse_body(body, meta):
    cur = Cursor(body)
    blocks = []

    while True:
        cur.skip_ws()
        if cur.eof():
            break

        # 卷首标题/说明已进 meta，正文里不要再当 para（否则渲染时重复输出）
        if cur.match("\\examtitle") or cur.match("\\answertitle"):
            cur.read_cmd("examtitle") or cur.read_cmd("answertitle")
            cur.skip_ws()
            cur.read_group()
            continue
        if cur.match("\\examnote"):
            cur.read_cmd("examnote")
            continue

        v = cur.read_cmd("sechead")
        if v is not None:
            blocks.append({"type": "sechead", "text": v.strip()})
            continue

        v = cur.read_cmd("subsechead")
        if v is not None:
            blocks.append({"type": "subsechead", "text": v.strip()})
            continue

        v = cur.read_cmd("duanju")
        if v is not None:
            blocks.append({"type": "duanju", "text": v.strip()})
            continue

        v = cur.read_cmd("scorenote")
        if v is not None:
            blocks.append({"type": "scorenote", "text": v.strip()})
            continue

        # 答案块：\ans{n}{…} / \subans{label}{…}
        label = cur.read_cmd("translabel")
        if label is not None:
            cur.skip_ws()
            inner = cur.read_env("translation")
            blocks.append({"type": "translation", "label": label.strip(),
                           "text": (inner or "").strip()})
            continue

        save = cur.i
        no = cur.read_cmd("subans")
        if no is not None:
            cur.skip_ws()
            text = cur.read_group()
            if text is not None:
                blocks.append({"type": "subans", "label": no.strip(),
                               "text": text.strip()})
                continue
            cur.i = save

        no = cur.read_cmd("ans")
        if no is not None:
            cur.skip_ws()
            text = cur.read_group()
            if text is not None:
                blocks.append({"type": "ans", "no": _to_int(no), "text": text.strip()})
                continue
            cur.i = save

        # 材料：\material{标签} 后接 materialtext 或其它内容
        label = cur.read_cmd("material")
        if label is not None:
            cur.skip_ws()
            inner = cur.read_env("materialtext")
            if inner is not None:
                blocks.append({
                    "type": "material",
                    "label": label.strip(),
                    "text": [p.strip() for p in re.split(r"\n\s*\n", inner.strip()) if p.strip()],
                })
                continue
            # 表格类材料：整块原样保留（含 \material 本身）
            tail = cur.read_until_block()
            blocks.append({"type": "raw",
                           "tex": f"\\material{{{label.strip()}}}\n" + _clean_paras(tail)})
            continue

        # 题目
        no = cur.read_cmd("question")
        if no is not None:
            cur.skip_ws()
            stem = cur.read_group()
            if stem is None:
                cur.i -= len(no) + len("\\question") + 2
                blocks.append({"type": "para", "text": _clean_paras(cur.read_until_block())})
                continue
            q = {"type": "question", "no": _to_int(no), "stem": stem.strip()}
            save = cur.i
            cur.skip_ws()
            opts = _read_choices(cur)
            if opts:
                q["options"] = opts
            else:
                cur.i = save
            blocks.append(q)
            continue

        # 块间文本：原样保留（空行语义不能丢，否则 \par 会消失）
        chunk = cur.read_until_block()
        if chunk.strip():
            blocks.append({"type": "para", "text": _clean_paras(chunk)})
        elif chunk:
            blocks.append({"type": "para", "text": chunk})
        if not chunk:
            cur.i += 1          # 保底前进，避免死循环

    return blocks


def _read_choices(cur):
    body = cur.read_env("choices")
    if body is None:
        return None
    opts = []
    # \item 后到下一个 \item / 结尾
    parts = re.split(r"\\item\b", body)
    for p in parts[1:]:
        opts.append(p.strip())
    return opts or None


def _to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return v


def convert(tex_path, kind_hint=None):
    text = Path(tex_path).read_text(encoding="utf-8")
    meta = parse_meta(text, kind_hint)

    at = text.find("\\begin{document}")
    end = text.rfind("\\end{document}")
    body = text[at + len("\\begin{document}"):end if end > 0 else len(text)]
    meta.setdefault("kind", "shiti")
    meta.setdefault("title", "")
    meta.setdefault("subtitle", "语文参考答案" if meta["kind"] == "daan" else "语文试题卷")

    blocks = parse_body(body, meta)
    return {"meta": meta, "blocks": blocks}


def main():
    ap = argparse.ArgumentParser(description="语文成品 tex → 块流 IR")
    ap.add_argument("tex", help="chinese-shiti.tex / chinese-daan.tex")
    ap.add_argument("-o", "--output", help="输出 chinese.json（默认同名 .json）")
    ap.add_argument("--kind", choices=["shiti", "daan"], help="强制卷别")
    args = ap.parse_args()

    ir = convert(args.tex, args.kind)
    out = Path(args.output) if args.output else Path(args.tex).with_suffix(".json")
    out.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")

    kinds = {}
    for b in ir["blocks"]:
        kinds[b["type"]] = kinds.get(b["type"], 0) + 1
    print(f"[OK] {out}")
    print(f"     kind={ir['meta']['kind']} blocks={len(ir['blocks'])} "
          + " ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
