#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_verify.py - PDF 视觉验证辅助脚本

将 PDF 转为 PNG 图片，供 LLM 用 read_image 工具直接查看排版效果。
这是从"能编译"到"排版正确"的关键验证步骤。

用法:
  python scripts/visual_verify.py <pdf文件> [--dpi 150] [--output-dir <dir>]

输出:
  在输出目录生成 preview-1.png, preview-2.png, ...
  打印图片路径列表
"""

import os
import subprocess
import sys
from pathlib import Path


def pdf_to_images(pdf_path: str, dpi: int = 150, output_dir: str = None) -> list:
    """
    将 PDF 转换为 PNG 图片列表。
    优先使用 pdftoppm（poppler），回退到 ImageMagick 的 convert。
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        print(f"[ERROR] PDF 文件不存在: {pdf_path}")
        return []

    if output_dir is None:
        output_dir = pdf_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    output_prefix = output_dir / "preview"

    # 方法 1: pdftoppm（poppler-utils / poppler-windows）
    try:
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(output_prefix)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            # 收集生成的图片
            images = sorted(output_dir.glob("preview-*.png"))
            return [str(img) for img in images]
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print("[WARN] pdftoppm 超时")

    # 方法 2: pdftocairo（poppler 的另一个工具）
    try:
        result = subprocess.run(
            ["pdftocairo", "-png", "-r", str(dpi), str(pdf_path), str(output_prefix)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            images = sorted(output_dir.glob("preview-*.png"))
            return [str(img) for img in images]
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print("[WARN] pdftocairo 超时")

    # 方法 3: ImageMagick convert
    try:
        result = subprocess.run(
            ["convert", "-density", str(dpi), str(pdf_path),
             str(output_prefix + "-%03d.png")],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            images = sorted(output_dir.glob("preview-*.png"))
            return [str(img) for img in images]
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print("[WARN] convert 超时")

    # 方法 4: Python + pdf2image（需要 pip install pdf2image）
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=dpi)
        output_paths = []
        for i, img in enumerate(images, 1):
            out_path = output_dir / f"preview-{i}.png"
            img.save(str(out_path), "PNG")
            output_paths.append(str(out_path))
        return output_paths
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] pdf2image 失败: {e}")

    print("[ERROR] 无法转换 PDF 为图片。请安装以下工具之一：")
    print("  - poppler (pdftoppm / pdftocairo): https://github.com/oschwartz10612/poppler-windows")
    print("  - ImageMagick: https://imagemagick.org")
    print("  - pip install pdf2image (需要系统安装 poppler)")
    return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description='PDF 视觉验证')
    parser.add_argument('pdf_file', help='PDF 文件路径')
    parser.add_argument('--dpi', type=int, default=150, help='DPI (默认 150)')
    parser.add_argument('--output-dir', default=None, help='输出目录 (默认与 PDF 同目录)')
    args = parser.parse_args()

    images = pdf_to_images(args.pdf_file, args.dpi, args.output_dir)

    if images:
        print(f"[OK] 生成 {len(images)} 张预览图:")
        for img in images:
            print(f"  - {img}")
        print(f"\n提示: 使用 Read 工具查看这些图片，确认排版效果。")
        print(f"检查要点:")
        print(f"  1. 图片是否在正确位置（右侧环绕或靠右）")
        print(f"  2. 公式是否正常渲染（无乱码、无溢出）")
        print(f"  3. 文字是否溢出页面边界")
        print(f"  4. 页码是否正确")
        print(f"  5. 答案文档的【答案】【解析】【详解】结构是否清晰")
    else:
        print("[FAIL] 无法生成预览图")
        sys.exit(1)


if __name__ == '__main__':
    main()
