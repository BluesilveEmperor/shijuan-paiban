#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_adjust.py - 编译后页数自适应调整

自动检测编译后的页数，超页时自动压缩行距或 itemsep，
页数不足时自动增大 itemsep，直到匹配目标页数。

用法:
  python scripts/auto_adjust.py <tex文件> [--target-pages 4] [--max-rounds 5]

调整策略（优先级从高到低）：
1. 调整 itemsep（优先）
2. 调整 linespread（次之）
3. 调整 margin（最后手段）
"""

import argparse
import os
import re
import subprocess
import sys


def get_page_count(tex_path, work_dir):
    """通过 pdfinfo 获取 PDF 页数"""
    pdf_name = os.path.basename(tex_path).replace('.tex', '.pdf')
    pdf_path = os.path.join(work_dir, pdf_name)

    if not os.path.exists(pdf_path):
        return None

    try:
        result = subprocess.run(
            ['pdfinfo', pdf_path],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace'
        )
        for line in result.stdout.split('\n'):
            if line.startswith('Pages:'):
                return int(line.split(':')[1].strip())
    except (FileNotFoundError, ValueError):
        pass

    return None


def compile_latex(tex_path, work_dir, passes=2):
    """编译 LaTeX 文件"""
    tex_basename = os.path.basename(tex_path)
    for _ in range(passes):
        result = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', '-output-directory', work_dir, tex_basename],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
            cwd=work_dir
        )
    return result.returncode == 0


def adjust_itemsep(tex_path, factor):
    """
    调整 examenum 的 itemsep。
    factor > 1 表示增大，factor < 1 表示减小。
    """
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def replace_itemsep(match):
        sep = match.group(1)
        # 解析当前值
        m = re.match(r'([\d.]+)\s*(cm|em|pt)', sep)
        if m:
            val = float(m.group(1)) * factor
            unit = m.group(2)
            val = max(val, 0.3)  # 最小值限制
            return f"itemsep={val:.1f}{unit}"
        return match.group(0)

    # 匹配 itemsep=xxx
    content = re.sub(
        r'itemsep=([^,\]]+)',
        replace_itemsep,
        content
    )

    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(content)


def adjust_linespread(tex_path, factor):
    """
    调整 linespread。
    factor > 1 表示增大（更宽松），factor < 1 表示减小（更紧凑）。
    """
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def replace_linespread(match):
        val = float(match.group(1)) * factor
        val = max(0.85, min(val, 1.2))  # 限制范围
        return f"linespread{{{val:.2f}}}"

    content = re.sub(
        r'linespread\{([\d.]+)\}',
        replace_linespread,
        content
    )

    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(content)


def auto_adjust(tex_path, target_pages=4, max_rounds=5):
    """
    自动调整以匹配目标页数。
    返回 (是否成功, 最终页数, 调整轮次)
    
    改进逻辑：
    - 超页时：压缩 itemsep → 压缩 linespread
    - 不足时：增大 itemsep → 增大 linespread
    - 如果连续 2 轮页数不变，说明已达到自然页数，接受实际页数
    """
    work_dir = os.path.dirname(tex_path) or '.'

    # 初始编译
    print(f"[INFO] 初始编译: {os.path.basename(tex_path)}")
    if not compile_latex(tex_path, work_dir):
        print("[ERROR] 初始编译失败")
        return False, None, 0

    current_pages = get_page_count(tex_path, work_dir)
    if current_pages is None:
        print("[ERROR] 无法获取页数")
        return False, None, 0

    print(f"[INFO] 初始页数: {current_pages}, 目标: {target_pages}")

    if current_pages == target_pages:
        print("[OK] 页数已匹配，无需调整")
        return True, current_pages, 0

    # 调整策略
    no_change_count = 0  # 连续页数不变的轮次数
    for round_num in range(1, max_rounds + 1):
        prev_pages = current_pages
        
        if current_pages > target_pages:
            # 超页 → 压缩
            if round_num <= 2:
                factor = 0.85
                print(f"[INFO] 第{round_num}轮: 减小 itemsep (×{factor})")
                adjust_itemsep(tex_path, factor)
            else:
                factor = 0.95
                print(f"[INFO] 第{round_num}轮: 减小 linespread (×{factor})")
                adjust_linespread(tex_path, factor)
        else:
            # 页数不足 → 增大
            if round_num <= 2:
                factor = 1.15
                print(f"[INFO] 第{round_num}轮: 增大 itemsep (×{factor})")
                adjust_itemsep(tex_path, factor)
            else:
                factor = 1.05
                print(f"[INFO] 第{round_num}轮: 增大 linespread (×{factor})")
                adjust_linespread(tex_path, factor)

        # 重新编译
        if not compile_latex(tex_path, work_dir):
            print(f"[ERROR] 第{round_num}轮编译失败")
            return False, current_pages, round_num

        new_pages = get_page_count(tex_path, work_dir)
        if new_pages is None:
            print(f"[ERROR] 无法获取新页数")
            return False, current_pages, round_num

        print(f"[INFO] 第{round_num}轮后: {new_pages} 页")
        current_pages = new_pages

        if current_pages == target_pages:
            print(f"[OK] 页数匹配！共调整 {round_num} 轮")
            return True, current_pages, round_num

        # 检测自然页数：如果连续 2 轮页数不变，说明已达到自然页数
        if current_pages == prev_pages:
            no_change_count += 1
            if no_change_count >= 2:
                print(f"[INFO] 连续 {no_change_count} 轮页数不变，接受自然页数 {current_pages} 页")
                return True, current_pages, round_num
        else:
            no_change_count = 0

    print(f"[WARN] 达到最大调整轮次 ({max_rounds})，当前 {current_pages} 页")
    return current_pages == target_pages, current_pages, max_rounds


def main():
    parser = argparse.ArgumentParser(description='编译后页数自适应调整')
    parser.add_argument('tex_file', help='要调整的 .tex 文件')
    parser.add_argument('--target-pages', type=int, default=4, help='目标页数 (默认 4)')
    parser.add_argument('--max-rounds', type=int, default=5, help='最大调整轮次 (默认 5)')

    args = parser.parse_args()

    if not os.path.exists(args.tex_file):
        print(f"[ERROR] 文件不存在: {args.tex_file}")
        sys.exit(1)

    success, pages, rounds = auto_adjust(
        args.tex_file,
        target_pages=args.target_pages,
        max_rounds=args.max_rounds
    )

    if success:
        print(f"\n[DONE] 成功！{pages} 页（{rounds} 轮调整）")
    else:
        print(f"\n[FAIL] 未达到目标页数，当前 {pages} 页")
        sys.exit(1)


if __name__ == '__main__':
    main()
