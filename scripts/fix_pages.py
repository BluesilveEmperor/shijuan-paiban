#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_pages.py - 修复页数控制问题
目标：每份试卷控制在 4 页以内
规则（来自 SKILL.md）：
- 单张插图（无子问）→ 用 [H] + \raggedleft 靠右
- 几何/示意图在列表环境外 → 用 wrapfigure 右侧环绕
- 几何/示意图在列表环境中 → 用 minipage 左右并排
"""

import re
from pathlib import Path


def fix_page_control(tex_path):
    """修复单个文件的页数控制"""
    content = tex_path.read_text(encoding='utf-8')
    original = content

    # 1. 添加行距压缩
    if '\\linespread' not in content:
        content = content.replace(
            '\\geometry{a4paper, margin=2.5cm, footskip=1cm}',
            '\\geometry{a4paper, margin=2.5cm, footskip=1cm}\n\\linespread{1.0}\\selectfont'
        )
    else:
        content = content.replace('\\linespread{1.05}', '\\linespread{1.0}')

    # 2. 修复重复的 geometry
    if content.count('\\geometry{') > 1:
        lines = content.split('\n')
        new_lines = []
        geo_count = 0
        for line in lines:
            if '\\geometry{' in line:
                geo_count += 1
                if geo_count > 1:
                    continue
            new_lines.append(line)
        content = '\n'.join(new_lines)

    # 3. 调整解答题间距（更紧凑）
    content = content.replace(
        '\\setlist[examenum,1]{label=\\arabic*., leftmargin=2em, itemsep=0.3em, parsep=0em}',
        '\\setlist[examenum,1]{label=\\arabic*., leftmargin=2em, itemsep=0.5cm, parsep=0em}'
    )

    # 4. 缩小图片宽度（0.35 → 0.28）
    content = content.replace(
        '\\includegraphics[width=0.35\textwidth]',
        '\\includegraphics[width=0.28\textwidth]'
    )
    content = content.replace(
        '\\includegraphics[width=0.25\textwidth]',
        '\\includegraphics[width=0.28\textwidth]'
    )

    # 5. 修复图片放置：独立图片使用 [H] + \raggedleft 靠右
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 检测独立的 includegraphics（不在 wrapfigure/minipage/figure 中）
        if '\\includegraphics' in line:
            # 检查是否在浮动环境中
            context = ''.join(lines[max(0,i-5):i])
            in_float = 'wrapfigure' in context or 'minipage' in context or 'figure' in context

            if not in_float:
                # 检查是否是独立图片（前后有空行或 item 内容）
                prev_empty = i == 0 or lines[i-1].strip() == '' or lines[i-1].strip().startswith('\\item')
                next_empty = i >= len(lines)-1 or lines[i+1].strip() == ''

                if prev_empty or next_empty:
                    # 使用 [H] + \raggedleft 靠右（SKILL.md 规则）
                    img_cmd = line.strip()
                    # 移除可能的 \centering
                    img_cmd = img_cmd.replace('\\centering\n', '').replace('\\centering ', '')
                    wrap_block = [
                        '',
                        '\\begin{figure}[H]',
                        '\\raggedleft',
                        img_cmd,
                        '\\end{figure}',
                        ''
                    ]
                    new_lines.extend(wrap_block)
                    i += 1
                    continue

        new_lines.append(line)
        i += 1

    content = '\n'.join(new_lines)

    # 6. 添加必要的包
    if 'wrapfig' not in content:
        if '\\usepackage{float}' in content:
            content = content.replace(
                '\\usepackage{float}',
                '\\usepackage{float}\n\\usepackage{wrapfig}'
            )
        else:
            content = content.replace(
                '\\usepackage{tikz}',
                '\\usepackage{tikz}\n\\usepackage{float}\n\\usepackage{wrapfig}'
            )

    # 7. 检测是否是答案卷
    is_answer_only = '本卷为答案卷' in content or '答案卷' in content

    if is_answer_only:
        content = content.replace(
            '\\begin{document}',
            '\\begin{document}\n\\noindent\\textbf{\\large 本卷为参考答案卷，原题未提供。}\\\\[0.5em]'
        )

    if content != original:
        tex_path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    output_dir = Path('./batch30-output')
    fixed = 0
    answer_only = 0

    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir():
            continue

        for tex in paper_dir.glob('*_student.tex'):
            if fix_page_control(tex):
                fixed += 1
                if '答案卷' in tex.read_text(encoding='utf-8') or '本卷为答案卷' in tex.read_text(encoding='utf-8'):
                    answer_only += 1

    print(f'Fixed {fixed} files')
    print(f'  Answer-only papers: {answer_only}')


if __name__ == '__main__':
    main()
