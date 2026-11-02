#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_docx.py - 内置 DOCX 解包与图片提取（替代外部 docx skill）

只依赖标准库 zipfile（WMF 转换额外需要 Pillow），不依赖任何外部 skill。

用法:
  # 解包图片到 <out_dir>/<images_dir>/（默认 Images-<docx文件名>，ARTIFACT-003）
  python scripts/extract_docx.py 试卷.docx ./输出目录

  # 答案文档：WMF 批量转 600 DPI PNG
  python scripts/extract_docx.py 试卷-答案.docx ./ --images-dir Images-试卷-答案 --convert-wmf

  # 只看结构不落盘
  python scripts/extract_docx.py 试卷.docx --list

  # 同时导出 pandoc markdown（若已安装 pandoc）
  python scripts/extract_docx.py 试卷.docx ./out --markdown

退出码:
  0  成功
  1  输入有问题（非 docx / 文件不存在）
  2  WMF 转换失败但其他成功（部分失败）
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".emf", ".wmf", ".tif", ".tiff"}
MEDIA_PREFIX = "word/media/"


def list_media(docx_path: Path):
    with zipfile.ZipFile(docx_path) as z:
        return [n for n in z.namelist()
                if n.startswith(MEDIA_PREFIX) and not n.endswith("/")]


def extract_images(docx_path: Path, out_dir: Path, images_dir: str,
                   convert_wmf: bool, dpi: int):
    """返回 (提取数量, 转换成功数, 转换失败列表)"""
    target = out_dir / images_dir
    target.mkdir(parents=True, exist_ok=True)

    extracted, converted, failed = 0, 0, []
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if not name.startswith(MEDIA_PREFIX) or name.endswith("/"):
                continue
            base = os.path.basename(name)
            if Path(base).suffix.lower() not in IMAGE_EXTS:
                continue
            data = z.read(name)
            dest = target / base
            dest.write_bytes(data)
            extracted += 1

    if convert_wmf:
        for wmf in sorted(target.glob("*")):
            if wmf.suffix.lower() != ".wmf":
                continue
            try:
                _wmf_to_png(wmf, dpi)
                converted += 1
            except Exception as exc:
                failed.append(f"{wmf.name}: {exc}")

    return extracted, converted, failed


def _wmf_to_png(wmf_path: Path, dpi: int):
    """WMF/EMF → PNG。Windows 下走 GDI，其他平台需要 libwmf。"""
    from PIL import Image  # 延迟导入，避免无 Pillow 时整体失败

    png_path = wmf_path.with_suffix(".png")
    im = Image.open(str(wmf_path))
    try:
        im.load(dpi=dpi)          # WMF 插件按 dpi 光栅化，比 resize 清晰得多
    except TypeError:
        im.load()                 # 非 WMF 插件不支持 dpi 参数
    if im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGBA")
    im.save(str(png_path), dpi=(dpi, dpi))
    wmf_path.unlink()


def export_markdown(docx_path: Path, out_dir: Path):
    if not shutil.which("pandoc"):
        print("[WARN] 未安装 pandoc，跳过 Markdown 导出", file=sys.stderr)
        return None
    md_path = out_dir / (docx_path.stem + ".md")
    result = subprocess.run(
        ["pandoc", str(docx_path), "-t", "markdown",
         "--wrap=none", "--track-changes=all", "-o", str(md_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[WARN] pandoc 失败: {result.stderr.strip()}", file=sys.stderr)
        return None
    return md_path


def main():
    ap = argparse.ArgumentParser(description="DOCX 解包与图片提取")
    ap.add_argument("docx", help="DOCX 文件路径")
    ap.add_argument("out_dir", nargs="?", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--images-dir", default=None,
                    help="图片子目录名（默认 Images-<docx文件名>，ARTIFACT-003）")
    ap.add_argument("--convert-wmf", action="store_true", help="WMF/EMF 转 PNG")
    ap.add_argument("--dpi", type=int, default=600, help="WMF 转换 DPI（默认 600）")
    ap.add_argument("--markdown", action="store_true", help="同时导出 pandoc Markdown")
    ap.add_argument("--list", action="store_true", help="只列出包内媒体文件")
    args = ap.parse_args()

    docx_path = Path(args.docx)
    if not docx_path.exists():
        print(f"[ERROR] 文件不存在: {docx_path}", file=sys.stderr)
        return 1
    if docx_path.suffix.lower() != ".docx":
        print(f"[ERROR] 不是 .docx 文件: {docx_path}", file=sys.stderr)
        return 1

    if args.list:
        media = list_media(docx_path)
        print(f"{len(media)} 个媒体文件:")
        for name in media:
            print(f"  {name}")
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.images_dir:
        args.images_dir = f"Images-{docx_path.stem}"

    extracted, converted, failed = extract_images(
        docx_path, out_dir, args.images_dir, args.convert_wmf, args.dpi
    )
    print(f"[OK] 提取 {extracted} 张图片 → {out_dir / args.images_dir}")
    if args.convert_wmf:
        print(f"[OK] WMF 转换成功 {converted} 个（{args.dpi} DPI）")
    for f in failed:
        print(f"[WARN] WMF 转换失败: {f}", file=sys.stderr)

    if args.markdown:
        md = export_markdown(docx_path, out_dir)
        if md:
            print(f"[OK] Markdown → {md}")

    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
