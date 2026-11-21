#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_convert.py - Markdown 表格 → LaTeX tabular 自动转换

用法:
  python scripts/table_convert.py <input.md> [--output <output.tex>]
  python scripts/table_convert.py <input.tex> [--inplace]
"""

import argparse
import os
import re
import sys

LINE_BREAK = ' \\'  # LaTeX 换行符


def detect_table_width(num_cols):
    """根据列数决定表格宽度策略"""
    if num_cols > 8:
        return r"\resizebox{\textwidth}{!}{%"
    elif num_cols > 6:
        return r"\small"
    return ""


def parse_markdown_table(md_text):
    """解析 Markdown 表格，返回 (headers, rows, align)"""
    lines = md_text.strip().split('\n')
    if len(lines) < 2:
        return None

    header_line = lines[0]
    headers = [cell.strip() for cell in header_line.strip('| ').split('|')]
    num_cols = len(headers)

    align_line = lines[1]
    align_cells = [cell.strip() for cell in align_line.strip('| ').split('|')]
    align = []
    for cell in align_cells:
        if cell.startswith(':') and cell.endswith(':'):
            align.append('c')
        elif cell.endswith(':'):
            align.append('r')
        elif cell.startswith(':'):
            align.append('l')
        else:
            align.append('c')
    while len(align) < num_cols:
        align.append('c')

    rows = []
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.strip('| ').split('|')]
        while len(cells) < num_cols:
            cells.append('')
        rows.append(cells[:num_cols])

    return headers, rows, align


def convert_to_latex(headers, rows, align):
    """将解析后的表格数据转换为 LaTeX tabular"""
    num_cols = len(headers)
    col_spec = ''.join(align[:num_cols])
    width_cmd = detect_table_width(num_cols)
    lines = []

    if width_cmd.startswith(r'\resizebox'):
        lines.append(width_cmd)
        lines.append('{')

    lines.append(r'\begin{table}[H]')
    lines.append(r'\centering')
    if width_cmd and not width_cmd.startswith(r'\resizebox'):
        lines.append(width_cmd)
    lines.append(r'\begin{tabular}{' + col_spec + '}')
    lines.append(r'\toprule')

    header_str = ' & '.join(headers) + LINE_BREAK
    header_str += r' \midrule'
    lines.append(header_str)

    for i, row in enumerate(rows):
        row_str = ' & '.join(row) + LINE_BREAK
        if i == len(rows) - 1:
            row_str += r' \bottomrule'
        lines.append(row_str)

    lines.append(r'\end{tabular}')
    if width_cmd and not width_cmd.startswith(r'\resizebox'):
        lines.append(r'\normalsize')
    if width_cmd.startswith(r'\resizebox'):
        lines.append('}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)


def find_markdown_tables(md_text):
    """查找文本中的所有 Markdown 表格和 HTML 表格"""
    tables = []
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Markdown 表格
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'^\|[\s:-|]+\|$', next_line):
                    table_lines = [line]
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith('|'):
                        table_lines.append(lines[j])
                        j += 1
                    table_text = '\n'.join(table_lines)
                    tables.append(('markdown', table_text, i, j))
                    i = j
                    continue
        # HTML 表格
        if '<table' in line.lower():
            table_lines = []
            j = i
            while j < len(lines):
                table_lines.append(lines[j])
                if '</table>' in lines[j].lower():
                    break
                j += 1
            table_text = '\n'.join(table_lines)
            tables.append(('html', table_text, i, j + 1))
            i = j + 1
            continue
        i += 1
    return tables


def parse_html_table(html_text):
    """解析 HTML 表格，返回 (headers, rows, align)"""
    tr_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r'<t[dh]>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)

    rows_data = []
    for tr_match in tr_pattern.finditer(html_text):
        tr_content = tr_match.group(1)
        cells = [cell.strip() for cell in td_pattern.findall(tr_content)]
        if cells:
            rows_data.append(cells)

    if not rows_data:
        return None

    headers = rows_data[0]
    data_rows = rows_data[1:]
    align = ['c'] * len(headers)

    return headers, data_rows, align


def convert_md_to_tex_tables(md_text):
    """将文本中所有 Markdown/HTML 表格替换为 LaTeX tabular"""
    tables = find_markdown_tables(md_text)
    if not tables:
        return md_text

    result = md_text
    for table_type, table_text, start_line, end_line in reversed(tables):
        if table_type == 'markdown':
            parsed = parse_markdown_table(table_text)
        else:
            parsed = parse_html_table(table_text)
        if parsed:
            headers, rows, align = parsed
            latex_table = convert_to_latex(headers, rows, align)
            lines = result.split('\n')
            lines[start_line:end_line] = latex_table.split('\n')
            result = '\n'.join(lines)

    return result


def main():
    parser = argparse.ArgumentParser(description='Markdown 表格 → LaTeX tabular 转换')
    parser.add_argument('input', help='输入文件 (.md 或 .tex)')
    parser.add_argument('--output', '-o', default=None, help='输出文件')
    parser.add_argument('--inplace', action='store_true', help='直接修改输入文件')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] 文件不存在: {args.input}")
        sys.exit(1)

    ext = os.path.splitext(args.input)[1].lower()

    if ext == '.md':
        with open(args.input, 'r', encoding='utf-8') as f:
            md_content = f.read()
        result = convert_md_to_tex_tables(md_content)
        output_path = args.output or args.input.replace('.md', '_tables.tex')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"[OK] 输出: {output_path}")

    elif ext == '.tex':
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
        tables = find_markdown_tables(content)
        if not tables:
            print(f"[INFO] 未发现 Markdown 表格: {args.input}")
            return
        print(f"[INFO] 发现 {len(tables)} 个 Markdown 表格")
        result = convert_md_to_tex_tables(content)
        output_path = args.output or args.input
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"[OK] 输出: {output_path}")
    else:
        print(f"[ERROR] 不支持的文件类型: {ext}")
        sys.exit(1)


if __name__ == '__main__':
    main()
