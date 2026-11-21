#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split 学军3月 MD (exam + trailing answer key) and fix OCR issues.

- exam part: L1-100 of the current MD; fix '12 已知复数' -> '12. 已知复数'
  (missing period made md2tex drop the question).
- ans part: L101-end (【N题答案】【答案】 answer key), retitled.
- 陕西 MD: fix OCR'd table header cell '组别\\米数' -> '组别\\textbackslash{}米数'
  ('\\米' is an undefined control sequence).
Run:  python3 /mnt/d/Desktop/shijuan-paiban/scripts/split_xj3.py
"""
import os
import shutil
from pathlib import Path

BASE = Path(r"D:\Music\试题加题库\高三数学" if os.name == 'nt'
            else "/mnt/d/Music/试题加题库/高三数学")
MD = BASE / ".math-output"

EXAM = "浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题"
ANS = EXAM + "答案"

src = MD / f"{EXAM}.md"
if (MD / f"{ANS}.md").exists():
    print("already split")
else:
    lines = src.read_text(encoding='utf-8').split('\n')
    # boundary: the answer-key header '## 高三数学学科' (exam copy uses '#')
    idxs = [i for i, l in enumerate(lines) if l.strip() == '## 高三数学学科']
    assert len(idxs) == 1, f'expected 1 answer-key title line, got {idxs}'
    i = idxs[0]
    exam = lines[:i]
    ans = lines[i:]

    # fix Q12 numbering in exam part
    fixed = 0
    for j, l in enumerate(exam):
        if l.startswith('12 已知复数'):
            exam[j] = '12. ' + l[3:]
            fixed += 1
    assert fixed == 1, f'Q12 fix count {fixed}'

    # retitle answer key
    assert ans[0].strip() == '## 高三数学学科'
    ans[0] = '## ' + ANS

    src.rename(MD / f"{EXAM}.md.bak3")
    (MD / f"{EXAM}.md").write_text('\n'.join(exam).rstrip() + '\n', encoding='utf-8')
    (MD / f"{ANS}.md").write_text('\n'.join(ans).rstrip() + '\n', encoding='utf-8')
    img_src = MD / EXAM
    if img_src.is_dir():
        img_dst = MD / ANS
        if not img_dst.exists():
            shutil.copytree(img_src, img_dst)
    print(f"split at L{i+1}: exam {len(exam)} lines / ans {len(ans)} lines; Q12 fixed")

# 陕西 table header cell
SX = "陕西省2025届高三下学期高考适应性检测数学试题"
p = MD / f"{SX}.md"
t = p.read_text(encoding='utf-8')
old = r'<td>组别\米数</td>'
new = r'<td>组别\textbackslash{}米数</td>'
n = t.count(old)
assert n == 1, f'陕西 table cell count {n}'
p.rename(MD / f"{SX}.md.bak3")
p.write_text(t.replace(old, new), encoding='utf-8')
print("陕西 table header cell fixed")
