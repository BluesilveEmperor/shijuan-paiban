#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_teacher.py - 从学生版 .tex 生成教师版 / 带答题空间的学生版

修复了 v3 内联脚本的静默失败问题：
  v3 用 content.find("[start=15, itemsep=2.5cm]") 定位解答题块，
  一旦 itemsep 被改成 1.5cm 就返回 -1，脚本会静默写出错误文件。
  本脚本改用环境扫描定位，itemsep 取值任意都能正确定位。

用法:
  python scripts/gen_teacher.py 学生版.tex                      # normal（默认）
  python scripts/gen_teacher.py 学生版.tex --mode compact
  python scripts/gen_teacher.py 学生版.tex --mode exam
  python scripts/gen_teacher.py 学生版.tex --mode normal --start 15

产出（与输入同目录）:
  <stem>-教师版-紧凑.tex   compact
  <stem>-教师版.tex        normal
  <stem>-教师版-考试.tex   exam
  <stem>-学生版.tex        学生版 + 答题空间命令（ARTIFACT-002；
                            旧名 <stem>-答题空间.tex 自动迁移）

退出码:
  0 成功
  1 未找到解答题块
"""

import argparse
import re
import sys
from pathlib import Path

MODES = {
    "compact": {"itemsep": "0.5em", "gap": r"\vspace{2em}", "space": r"\answerc", "suffix": "-教师版-紧凑"},
    "normal":  {"itemsep": "1.5em", "gap": r"\vspace{6em}", "space": r"\answern", "suffix": "-教师版"},
    "exam":    {"itemsep": None,    "gap": r"\newpage",    "space": r"\answere", "suffix": "-教师版-考试"},
}

BEGIN_RE = re.compile(r"\\begin\{examenum\}(\[[^\]]*\])?")
END_RE = re.compile(r"\\end\{examenum\}")
ITEM_RE = re.compile(r"^\s*\\item\b")


def locate_long_answer(content):
    """定位顶层解答题块，返回 (start_idx, end_idx, start_num, opts)。

    顶层 = 带 [start=N] 的那个 examenum。嵌套子问的 examenum 不带 start。
    """
    m = BEGIN_RE.search(content)
    while m:
        opts = m.group(1) or ""
        if "start=" in opts:
            sm = re.search(r"start\s*=\s*(\d+)", opts)
            start_num = int(sm.group(1)) if sm else None
            # 从该处向后扫描，配对 end（跳过嵌套 begin）
            depth = 0
            pos = m.start()
            for mm in re.finditer(r"\\begin\{examenum\}(\[[^\]]*\])?|\\end\{examenum\}", content[pos:]):
                if mm.group(0).startswith("\\begin"):
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        end_idx = pos + mm.end()
                        return pos, end_idx, start_num, opts
            return None, None, None, None
        m = BEGIN_RE.search(content, m.end())
    return None, None, None, None


def split_block(block):
    """把解答题块拆成行，并标注每个顶层 \\item 的行号。"""
    lines = block.split("\n")
    depth = 0
    item_lines = []
    for i, line in enumerate(lines):
        depth += len(re.findall(r"\\begin\{examenum\}", line))
        depth -= len(re.findall(r"\\end\{examenum\}", line))
        # 顶层 item：本行是 item 且当前深度为 1（还在外层 examenum 内）
        if ITEM_RE.match(line) and depth == 1:
            item_lines.append(i)
    return lines, item_lines


def _set_itemsep(opts, new_itemsep):
    if new_itemsep is None:
        cleaned = re.sub(r",?\s*itemsep\s*=\s*[^,\]]+", "", opts)
        return cleaned
    if "itemsep" in opts:
        return re.sub(r"itemsep\s*=\s*[^,\]]+", f"itemsep={new_itemsep}", opts)
    return opts[:-1] + f", itemsep={new_itemsep}]"


def _insert_before_items(lines, item_lines, payload):
    """在第 2..n 个顶层 item 之前插入 payload（从后往前插，行号不偏移）。

    第 1 个 item 前不插（题目紧跟大题标题），最后一个 item 之后也不插。
    """
    out = list(lines)
    for pos in sorted(item_lines[1:], reverse=True):
        j = pos
        while j > 0 and out[j - 1].strip() == "":
            j -= 1
        out.insert(j, payload)
    return out


def build_teacher(content, mode):
    cfg = MODES[mode]
    start_idx, end_idx, start_num, opts = locate_long_answer(content)
    if start_idx is None:
        return None, "未找到带 [start=N] 的顶层 examenum"

    block = content[start_idx:end_idx]

    # 1) 调整 itemsep（exam 模式直接移除）
    if opts:
        block = block.replace(opts, _set_itemsep(opts, cfg["itemsep"]), 1)

    # 2) 在每题之间插入 gap（compact/normal 为 \vspace，exam 为 \newpage）
    lines, item_lines = split_block(block)
    lines = _insert_before_items(lines, item_lines, cfg["gap"])

    return content[:start_idx] + "\n".join(lines) + content[end_idx:], None


def build_student_space(content, mode):
    """在学生版每道解答题后插入答题空间（最后一题除外）。

    若解答题块里已经有答题空间命令（例如由 render_tex.py 渲染时已按
    meta.answer_space 插入），直接跳过，避免重复插入。
    """
    cfg = MODES[mode]
    start_idx, end_idx, _, _ = locate_long_answer(content)
    if start_idx is None:
        return None, "未找到解答题块"

    block = content[start_idx:end_idx]
    existing = sum(block.count(c) for c in (r"\answerc", r"\answern", r"\answere"))
    if existing:
        # 渲染器已按 meta.answer_space 插入过，直接沿用，不再重复插入
        return content, f"已包含 {existing} 处答题空间命令，直接沿用"

    lines, item_lines = split_block(block)
    lines = _insert_before_items(lines, item_lines, cfg["space"])

    return content[:start_idx] + "\n".join(lines) + content[end_idx:], None


def main():
    ap = argparse.ArgumentParser(description="生成教师版 / 带答题空间的学生版")
    ap.add_argument("tex", help="学生版 .tex 路径")
    ap.add_argument("--mode", choices=list(MODES), default="normal")
    ap.add_argument("--no-student", action="store_true", help="不生成带答题空间的学生版")
    args = ap.parse_args()

    path = Path(args.tex)
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8")
    stem = path.stem

    teacher, err = build_teacher(content, args.mode)
    if err:
        print(f"[ERROR] {err}", file=sys.stderr)
        print("提示：解答题块必须是 \\begin{examenum}[start=N, ...]，且 N 已按题量计算。",
              file=sys.stderr)
        return 1

    suffix = MODES[args.mode]["suffix"]
    teacher_path = path.with_name(stem + suffix + ".tex")
    teacher_path.write_text(teacher, encoding="utf-8")
    print(f"[OK] {teacher_path.name}  (mode={args.mode})")

    if not args.no_student:
        student, note = build_student_space(content, args.mode)
        if student is None:
            print(f"[WARN] 学生版答题空间生成失败: {note}", file=sys.stderr)
        else:
            sp = path.with_name(stem + "-学生版.tex")
            legacy = path.with_name(stem + "-答题空间.tex")
            if legacy.exists() and not sp.exists():
                legacy.rename(sp)
                print(f"[MIGRATE] {legacy.name} -> {sp.name}")
            sp.write_text(student, encoding="utf-8")
            if legacy.exists():
                print(f"[WARN] 旧名文件 {legacy.name} 已被 {sp.name} 取代，可手动删除",
                      file=sys.stderr)
            print(f"[OK] {sp.name}  ({note or '答题空间 = ' + MODES[args.mode]['space']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
