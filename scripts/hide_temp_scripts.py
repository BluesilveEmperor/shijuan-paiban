#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hide_temp_scripts.py — 收尾隐藏每卷的临时脚本目录

把试卷工作目录下的 ``temp_scripts/`` 重命名为 ``.temp_scripts/``（点前缀，
类 Unix 默认不可见），并在 Windows 下设置 FILE_ATTRIBUTE_HIDDEN，使资源
管理器默认也不显示。目录保留，便于复查本次提取/排版用过的一次性脚本；
绝不写入技能安装目录。

用法::

    python scripts/hide_temp_scripts.py <试卷目录或 .tex> [...]
    python scripts/hide_temp_scripts.py 试卷目录/试卷.tex

已有 ``.temp_scripts/`` 时逐个合并，重名文件自动加时间戳后缀。
退出码：0 成功（没有 temp_scripts 也算成功）；1 有目录无法隐藏。
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

TEMP_NAME = "temp_scripts"
HIDDEN_NAME = ".temp_scripts"


def _set_windows_hidden(path):
    """Windows：给目录设置 FILE_ATTRIBUTE_HIDDEN（资源管理器默认不可见）。"""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    FILE_ATTRIBUTE_HIDDEN = 0x2
    INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetFileAttributesW.restype = wintypes.DWORD
    kernel32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.SetFileAttributesW.restype = wintypes.BOOL

    attrs = kernel32.GetFileAttributesW(str(path))
    if attrs == INVALID_FILE_ATTRIBUTES:
        raise ctypes.WinError(ctypes.get_last_error())
    if not attrs & FILE_ATTRIBUTE_HIDDEN:
        if not kernel32.SetFileAttributesW(str(path),
                                           attrs | FILE_ATTRIBUTE_HIDDEN):
            raise ctypes.WinError(ctypes.get_last_error())


def hide_temp_scripts(folder):
    """把 folder/temp_scripts 隐藏为 folder/.temp_scripts，返回隐藏后的路径。"""
    folder = Path(folder)
    src = folder / TEMP_NAME
    if not src.is_dir():
        return None

    dst = folder / HIDDEN_NAME
    if not dst.exists():
        src.rename(dst)
    else:
        # 已有历史隐藏目录：逐个合并，重名加时间戳，避免覆盖旧脚本
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for item in sorted(src.iterdir()):
            target = dst / item.name
            if target.exists():
                target = dst / f"{item.stem}-{stamp}{item.suffix}"
                n = 2
                while target.exists():
                    target = dst / f"{item.stem}-{stamp}-{n}{item.suffix}"
                    n += 1
            shutil.move(str(item), str(target))
        src.rmdir()

    _set_windows_hidden(dst)
    return dst


def _iter_folders(targets):
    for target in targets:
        path = Path(target)
        yield path.parent if path.is_file() else path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把试卷工作目录的 temp_scripts/ 隐藏为 .temp_scripts/")
    ap.add_argument("targets", nargs="+", help="试卷目录或试卷文件")
    args = ap.parse_args(argv)

    rc = 0
    for folder in _iter_folders(args.targets):
        try:
            dst = hide_temp_scripts(folder)
        except OSError as exc:
            print(f"[ERROR] 隐藏失败: {folder}（{exc}）", file=sys.stderr)
            rc = 1
            continue
        if dst is None:
            print(f"[--] 无 {TEMP_NAME}/：{folder}")
        else:
            print(f"[OK] 已隐藏 {TEMP_NAME}/ → {HIDDEN_NAME}/：{folder}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
