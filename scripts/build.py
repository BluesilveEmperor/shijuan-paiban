#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build.py — 一键编译本文件夹内的 .tex（母本，带 pip 同款彩色进度条）

部署方式：把本文件复制到任一含 .tex 的试卷/高校/年份/书稿文件夹即可。
（各文件夹里的 build.py 都应是本文件的副本，改母本后同步覆盖）

用法：
    python build.py                 # 通用版：编译全部 *.tex，每个连编两次
    python build.py --book          # 书稿版：只编 main.tex，连编三次（目录页码稳定）
    python build.py --times 3       # 自定义连编次数
    python build.py a.tex b.tex     # 只编指定文件
    python build.py --no-bar        # 关闭进度条
    python build.py --keep-build    # 保留 _build/ 目录（默认编译后自动清理）

行为：
    * 自动探测 xelatex：shutil.which → 各盘 texlive → MiKTeX → Linux/macOS
      （不假设固定盘符/年份，WSL 与 Windows 都能用）
    * 中间产物（.aux/.log/.out）统一写到 _build/，不污染源目录
    * 每个 .tex 连编 N 次（lastpage 页码、目录、交叉引用才准），PDF 回拷到当前目录
    * 编译成功后自动清理：删除 _build/ 目录 + 当前目录下散落的 .aux/.log/.out/.toc
    * 统计 log 中以 "!" 开头的错误行，失败打印前几条
    * rich 进度条（pip 同款配色：粉色进行中 / 绿色完成）；未装 rich 退回
      tqdm 彩色条；两者都没有则纯文本；输出被重定向时自动关闭
    * 全部成功退出码 0，有失败退出码 1（便于 xargs / CI 判失败）
"""

import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.getcwd()
BUILD = os.path.join(HERE, "_build")

try:
    from rich.table import Column
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
except ImportError:
    Progress = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


class _RichBar:
    """pip 同款彩色进度条（rich 默认主题：粉色进行中，完成转绿）。"""

    def __init__(self, total=0, disable=False):
        self.console = Console(highlight=False)
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn(
                "{task.description}",
                style="cyan",
                markup=False,
                table_column=Column(no_wrap=True, overflow="ellipsis",
                                    max_width=34),
            ),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            disable=disable,
        )
        self.task = self.progress.add_task("准备编译", total=total)
        self.progress.start()

    def set_description_str(self, desc):
        self.progress.update(self.task, description=desc)

    def write(self, s, **_k):
        self.console.print(s, markup=False, highlight=False, soft_wrap=True)

    def update(self, n=1):
        self.progress.advance(self.task, n)

    def close(self):
        self.progress.stop()


class _PlainBar:

    def __init__(self, total=0, **_):
        self.total = total

    def set_description_str(self, *_a, **_k):
        pass

    def update(self, n=1):
        pass

    def write(self, s, **_k):
        print(s, flush=True)

    def close(self):
        pass


def find_xelatex():
    for name in ("xelatex", "xelatex.exe"):
        p = shutil.which(name)
        if p:
            return p
    patterns = [
        r"?:\texlive\*\bin\windows\xelatex.exe",
        r"?:\texlive\*\bin\xelatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
        r"C:\Program Files*\MiKTeX*\miktex\bin*\xelatex.exe",
        r"/usr/local/texlive/*/bin/*/xelatex",
        r"/usr/bin/xelatex",
        r"/Library/TeX/texbin/xelatex",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def compile_one(xelatex, tex, times):
    base = os.path.splitext(os.path.basename(tex))[0]
    os.makedirs(BUILD, exist_ok=True)
    log = os.path.join(BUILD, base + ".log")
    errors, rc = [], 1
    for _ in range(times):
        proc = subprocess.run(
            [xelatex, "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory=" + BUILD, os.path.basename(tex)],
            cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rc = proc.returncode
        if os.path.exists(log):
            with open(log, "r", encoding="utf-8", errors="ignore") as f:
                errors = [ln.rstrip() for ln in f if ln.startswith("!")]
        if rc != 0:
            break
    pdf = os.path.join(BUILD, base + ".pdf")
    ok = rc == 0 and os.path.exists(pdf)
    pages = ""
    if ok:
        try:
            shutil.copy(pdf, os.path.join(HERE, base + ".pdf"))
            out = subprocess.run(["pdfinfo", "-enc", "UTF-8", pdf],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
            m = re.search(r"Pages:\s+(\d+)", out)
            pages = (m.group(1) + " 页") if m else ""
        except Exception:
            pass
    return ok, errors, pages


def cleanup(keep_build=False):
    if not keep_build:
        if os.path.isdir(BUILD):
            shutil.rmtree(BUILD)
    for ext in (".aux", ".log", ".out", ".toc"):
        for f in glob.glob(os.path.join(HERE, "*" + ext)):
            try:
                os.remove(f)
            except OSError:
                pass


def make_bar(total, no_bar=False):
    """优先 rich（pip 同款彩色条），其次 tqdm 彩色条，均未安装则返回 None。"""
    if Progress is not None:
        return _RichBar(total=total,
                        disable=(no_bar or not sys.stdout.isatty()))
    if tqdm is not None:
        return tqdm(total=total, ncols=90, dynamic_ncols=True, file=sys.stdout,
                    disable=(True if no_bar else None),
                    colour="magenta", ascii=" ━",
                    bar_format="{desc}  {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} "
                               "[{elapsed}<{remaining}]")
    return None


def main():
    argv = sys.argv[1:]
    book = no_bar = keep_build = False
    times = 2
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--book":
            book = True
        elif a == "--no-bar":
            no_bar = True
        elif a == "--keep-build":
            keep_build = True
        elif a == "--times":
            if i + 1 < len(argv):
                times = int(argv[i + 1])
                i += 1
            else:
                print("[ERROR] --times 需要一个数字")
                return 1
        elif a.startswith("--"):
            print(f"[WARN] 忽略未知参数 {a}")
        else:
            args.append(a)
        i += 1

    xelatex = find_xelatex()
    if not xelatex:
        print("[ERROR] 未找到 xelatex，请安装 TeX Live 或 MiKTeX 并加入 PATH")
        return 1
    print(f"[OK] xelatex: {xelatex}")

    if args:
        texs = [os.path.join(HERE, a) for a in args]
    elif book:
        main_tex = os.path.join(HERE, "main.tex")
        if not os.path.exists(main_tex):
            print("[ERROR] 书稿版需要 main.tex（章节 tex 不要单独编）")
            return 1
        texs = [main_tex]
        times = 3
    else:
        texs = sorted(glob.glob(os.path.join(HERE, "*.tex")))
    if not texs:
        print("[WARN] 当前目录没有 .tex 文件")
        return 0

    bad, failed = 0, []
    bar = make_bar(len(texs), no_bar=no_bar)
    if bar is None:
        print("[提示] 未安装 rich 或 tqdm，进度条不可用；"
              "pip install rich 可启用 pip 同款彩色进度条")
        bar = _PlainBar(total=len(texs))
    for tex in texs:
        name = os.path.basename(tex)
        short = name if len(name) <= 30 else name[:27] + "…"
        bar.set_description_str(f"编译 {short}")
        ok, errors, pages = compile_one(xelatex, tex, times)
        if ok:
            bar.write(f"  [OK]   {name:<52} {pages}")
        else:
            bad += 1
            failed.append(name)
            bar.write(f"  [FAIL] {name}")
            for e in errors[:4]:
                bar.write(f"         {e}")
        bar.update(1)
    bar.close()

    print(f"\n完成：{len(texs) - bad}/{len(texs)} 成功" + (f"，{bad} 个失败" if bad else ""))
    if failed:
        print("失败清单：")
        for n in failed:
            print("  -", n)

    cleanup(keep_build=keep_build)
    if not keep_build:
        print("已清理编译中间文件（_build/ 及 .aux/.log/.out/.toc）")
    else:
        print(f"中间文件保留在 {BUILD}（--keep-build）")

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
