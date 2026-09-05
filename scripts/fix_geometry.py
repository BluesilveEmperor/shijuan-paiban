#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_geometry.py - 修复缺少 geometry 包的问题
"""

from pathlib import Path


def main():
    output_dir = Path('./batch30-output')
    fixed = 0

    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir():
            continue

        for tex in paper_dir.glob('*_student.tex'):
            content = tex.read_text(encoding='utf-8')

            # Check if geometry package is properly loaded (not just \geometry command)
            has_geometry_pkg = ('\\usepackage{geometry}' in content or
                              '\\usepackage[a4paper' in content or
                              '\\usepackage{geometry' in content)

            if not has_geometry_pkg:
                # Add geometry package after \documentclass
                content = content.replace(
                    '\\documentclass[12pt, a4paper, oneside]{ctexart}',
                    '\\documentclass[12pt, a4paper, oneside]{ctexart}\n\\usepackage[a4paper, margin=2.5cm, footskip=1cm]{geometry}'
                )
                # Remove the standalone \geometry line if present
                if '\\geometry{margin=2.5cm}' in content:
                    content = content.replace('\\geometry{margin=2.5cm}', '')
                tex.write_text(content, encoding='utf-8')
                fixed += 1
                print(f'Fixed: {tex.parent.name[:40]}')

    print(f'\nFixed {fixed} files')


if __name__ == '__main__':
    main()
