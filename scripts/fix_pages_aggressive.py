#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_pages_aggressive.py - 强力压缩页数到 4 页以内
策略：
1. 缩小边距到 2cm
2. 行距压缩到 0.95
3. 解答题间距缩小到 0.3cm
4. 图片宽度缩小到 0.22\textwidth
5. 所有图片使用 [H] + \raggedleft 靠右
6. 移除多余的空白
"""

from pathlib import Path


def fix_page_control(tex_path):
    """修复单个文件的页数控制"""
    content = tex_path.read_text(encoding='utf-8')
    original = content

    # 1. 缩小边距 2.5cm → 2cm
    content = content.replace(
        '\\geometry{a4paper, margin=2.5cm, footskip=1cm}',
        '\\geometry{a4paper, margin=2cm, footskip=0.8cm}'
    )

    # 2. 行距压缩 1.0 → 0.95
    content = content.replace('\\linespread{1.0}\\selectfont', '\\linespread{0.95}\\selectfont')

    # 3. 调整解答题间距 0.5cm → 0.3cm
    content = content.replace(
        '\\setlist[examenum,1]{label=\\arabic*., leftmargin=2em, itemsep=0.5cm, parsep=0em}',
        '\\setlist[examenum,1]{label=\\arabic*., leftmargin=1.8em, itemsep=0.3cm, parsep=0em}'
    )

    # 4. 缩小图片宽度到 0.22
    for w in ['0.35', '0.28', '0.25']:
        content = content.replace(
            f'\\includegraphics[width={w}\\textwidth]',
            '\\includegraphics[width=0.22\\textwidth]'
        )

    # 5. 修复重复的 geometry
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

    # 6. 修复图片放置：独立图片使用 [H] + \raggedleft 靠右
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if '\\includegraphics' in line:
            # 检查是否在浮动环境中
            context_before = ''.join(lines[max(0,i-5):i])
            in_float = ('wrapfigure' in context_before or
                       'minipage' in context_before or
                       'figure' in context_before)

            if not in_float:
                # 使用 [H] + \raggedleft 靠右
                img_cmd = line.strip()
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

    # 7. 添加必要的包
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

    if content != original:
        tex_path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    output_dir = Path('./batch30-output')
    fixed = 0

    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir():
            continue

        for tex in paper_dir.glob('*_student.tex'):
            if fix_page_control(tex):
                fixed += 1

    print(f'Fixed {fixed} files')


if __name__ == '__main__':
    main()
