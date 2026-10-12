#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split the 5 combined 试题+答案 MDs into exam/ans pairs.

- 长沙一中: source PDF is 试题-only (4 pages) -> plain rename (drop "+答案").
- 深圳/长郡七/雅礼六/学军2月: split at the answer heading.
After splitting, the combined MD is renamed to <name>.md.combined-bak so
batch globs (*.md) no longer pick it up.
Run:  python3 /mnt/d/Desktop/shijuan-paiban/scripts/split_combined.py
"""
import os
import shutil
from pathlib import Path

BASE = Path(r"D:\Music\试题加题库\高三数学" if os.name == 'nt'
            else "/mnt/d/Music/试题加题库/高三数学")
MD = BASE / ".math-output"


def read_lines(stem):
    return (MD / f"{stem}.md").read_text(encoding='utf-8').split('\n')


def write_md(stem, lines):
    (MD / f"{stem}.md").write_text('\n'.join(lines).rstrip() + '\n',
                                   encoding='utf-8')


def copy_img_dir(src_stem, dst_stem):
    src = MD / src_stem
    dst = MD / dst_stem
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"  imgdir copy: {src_stem} -> {dst_stem}")
    else:
        print(f"  imgdir missing (ok if no images): {src_stem}")


def retire(stem):
    p = MD / f"{stem}.md"
    p.rename(MD / f"{stem}.md.combined-bak")


def find_line(lines, text, occurrence=1):
    n = 0
    for i, line in enumerate(lines):
        if line.strip() == text:
            n += 1
            if n == occurrence:
                return i
    raise SystemExit(f"marker not found ({occurrence}x): {text}")


# 1) 长沙一中: exam-only, plain rename
COMBINED = "2025届长沙一中高三上学期阶段性检测（一）数学试题+答案"
EXAM = "2025届长沙一中高三上学期阶段性检测（一）数学试题"
print(f"=== {COMBINED} -> rename (exam only) ===")
if (MD / f"{EXAM}.md").exists():
    print("  already done")
else:
    write_md(EXAM, read_lines(COMBINED))
    copy_img_dir(COMBINED, EXAM)
    retire(COMBINED)
    print("  done")

# 2) 深圳
COMBINED = "广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题+答案"
EXAM = "广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题"
ANS = EXAM + "答案"
print(f"=== {COMBINED} -> split ===")
if (MD / f"{EXAM}.md").exists():
    print("  already done")
else:
    lines = read_lines(COMBINED)
    i = find_line(lines, "# 2025 届高三年级第一次阶段考试数学参考答案")
    write_md(EXAM, lines[:i])
    write_md(ANS, lines[i:])
    copy_img_dir(COMBINED, EXAM)
    copy_img_dir(COMBINED, ANS)
    retire(COMBINED)
    print(f"  split at L{i+1}: exam {i} lines / ans {len(lines)-i} lines")

# 3) 长郡七
COMBINED = "湖南省长郡中学2025年高三下学期月考（七）数学试题+答案"
EXAM = "湖南省长郡中学2025年高三下学期月考（七）数学试题"
ANS = EXAM + "答案"
print(f"=== {COMBINED} -> split ===")
if (MD / f"{EXAM}.md").exists():
    print("  already done")
else:
    lines = read_lines(COMBINED)
    i = find_line(lines, "# 长郡中学 2025 届高三月考试卷(七)", occurrence=2)
    write_md(EXAM, lines[:i])
    write_md(ANS, lines[i:])
    copy_img_dir(COMBINED, EXAM)
    copy_img_dir(COMBINED, ANS)
    retire(COMBINED)
    print(f"  split at L{i+1}: exam {i} lines / ans {len(lines)-i} lines")

# 4) 雅礼六
COMBINED = "雅礼中学2025届高三第六次月考数学试题+答案"
EXAM = "雅礼中学2025届高三第六次月考数学试题"
ANS = EXAM + "答案"
print(f"=== {COMBINED} -> split ===")
if (MD / f"{EXAM}.md").exists():
    print("  already done")
else:
    lines = read_lines(COMBINED)
    i = find_line(lines, "# 雅礼中学 2025 届高三月考试卷(六)", occurrence=2)
    write_md(EXAM, lines[:i])
    write_md(ANS, lines[i:])
    copy_img_dir(COMBINED, EXAM)
    copy_img_dir(COMBINED, ANS)
    retire(COMBINED)
    print(f"  split at L{i+1}: exam {i} lines / ans {len(lines)-i} lines")

# 5) 学军2月
COMBINED = "浙江省杭州学军中学2025届高三下学期2月月考数学试题+答案"
EXAM = "浙江省杭州学军中学2025届高三下学期2月月考数学试题"
ANS = EXAM + "答案"
print(f"=== {COMBINED} -> split ===")
if (MD / f"{EXAM}.md").exists():
    print("  already done")
else:
    lines = read_lines(COMBINED)
    i = find_line(lines, "## 参考答案")
    write_md(EXAM, lines[:i])
    write_md(ANS, lines[i:])
    copy_img_dir(COMBINED, EXAM)
    copy_img_dir(COMBINED, ANS)
    retire(COMBINED)
    print(f"  split at L{i+1}: exam {i} lines / ans {len(lines)-i} lines")

print("\nAll combined MDs processed.")
