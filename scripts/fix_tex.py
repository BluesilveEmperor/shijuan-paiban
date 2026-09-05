#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_tex.py - 修复生成的 .tex 文件结构问题
将错误的 tasks 环境替换为正确的 enumerate + tasks 嵌套结构
"""

import os
import re
from pathlib import Path


def fix_tex_file(tex_path):
    """修复单个 .tex 文件"""
    content = tex_path.read_text(encoding='utf-8')
    original = content

    # 逐行处理
    lines = content.split('\n')
    new_lines = []
    in_outer_tasks = False
    outer_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # 检测外层 \begin{tasks}（紧跟在 section 后面）
        if '\\begin{tasks}' in line and not in_outer_tasks:
            # 检查前面是否有 section
            has_section = any('\\section' in l for l in new_lines[-5:] if l.strip())
            if has_section:
                new_lines.append('\\begin{enumerate}[itemsep=0.3em]')
                in_outer_tasks = True
                outer_depth = 1
                i += 1
                continue

        # 检测嵌套 \begin{tasks}
        if '\\begin{tasks}' in line and in_outer_tasks:
            outer_depth += 1
            new_lines.append(line)
            i += 1
            continue

        # 检测 \end{tasks}
        if '\\end{tasks}' in line and in_outer_tasks:
            outer_depth -= 1
            if outer_depth == 0:
                new_lines.append('\\end{enumerate}')
                in_outer_tasks = False
            else:
                new_lines.append(line)
            i += 1
            continue

        # 替换外层 \task 为 \item
        if in_outer_tasks and outer_depth == 1 and line.strip().startswith('\\task '):
            line = line.replace('\\task ', '\\item ', 1)

        new_lines.append(line)
        i += 1

    content = '\n'.join(new_lines)

    if content != original:
        tex_path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    output_dir = Path('./batch30-output')
    fixed = 0
    total = 0

    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir():
            continue

        for tex in paper_dir.glob('*_student.tex'):
            total += 1
            if fix_tex_file(tex):
                fixed += 1
                print(f'Fixed: {tex.parent.name[:40]}')

    print(f'\nTotal: {total} files')
    print(f'Fixed: {fixed} files')


if __name__ == '__main__':
    main()
