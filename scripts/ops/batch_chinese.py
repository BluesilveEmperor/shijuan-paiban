#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_chinese.py — 语文题库批量排版

对题库根下的每个试卷目录执行：

    PDF（试题/答案）
      → MinerU OCR（md + images，缓存在 .yw-ocr/）
      → md2chinese（块流 IR）
      → render_chinese（LaTeX）
      → xelatex ×2
      → 产物：语文卷-<考试名>.tex/.pdf、语文答案-<考试名>.tex/.pdf

命名以文件夹名优先（chinese_naming.exam_name，prefer=folder）。

用法::

    python scripts/ops/batch_chinese.py --only 2511杭州一模
    python scripts/ops/batch_chinese.py --limit 3
    python scripts/ops/batch_chinese.py                 # 全部

注意：OCR 走 MinerU 云端 API，单份约 35~45 秒；104 份约 70 分钟。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "render"))

from md2chinese import convert as md_convert          # noqa: E402
from render_chinese import render_paper                # noqa: E402
from chinese_naming import exam_name, output_stem     # noqa: E402

DEFAULT_LIBRARY = Path(r"D:\Documents\01_Study_Research\高中语文")
STY_SRC = ROOT / "templates" / "chinese" / "ywexam.sty"
BUILD_SRC = ROOT / "scripts" / "build" / "build.py"     # 一键编译母本，随卷部署
EXTRACT = ROOT / "scripts" / "extract" / "pdf_extract.py"
OCR_CACHE = ".yw-ocr"
# 首选模式；选项缺失时切到另一种（vlm ↔ pipeline 双向）
PRIMARY_MODEL = "vlm"
ALT_MODEL = "pipeline" if PRIMARY_MODEL == "vlm" else "vlm"

# 用户给的 52 个试验目录（按给出顺序）
TRIAL_DIRS = """2605 Z20
2409武汉九调
2502深圳一模
2502武汉二调
2503福建一模
2503湖北七市州
2503济南一模
2503金丽衢
2503泉州三模
2503温州二模
2503郑州二模
2504成都三诊
2504佛山二模
2504福建九地市
2504高二七彩阳光
2504广东二模
2504广州一模
2504杭州二模
2504湖北九地市
2504湖丽衢
2504稽阳联谊
2504嘉兴二模
2504金华十校
2504南充三模
2504南京师范大学附属中学杭二长郡三校联考
2504绍兴二模
2504台州二模
2504太原一模
2504重庆康德二次
2505  Z20
2505南京二模
2505山东滨州二模
2505绍兴上虞
2505苏北八市三次
2505苏锡常镇四市
2505天域全国
2505温州三模
2505县域教研联盟
2505义乌二模
2505浙江六校联盟
2505诸暨二模
2506嘉兴高一期末
2506绍兴高一期末
2508湖南雅礼
2508浙江Z20+
2508浙江七彩阳光高三
2508浙江强基联盟
2509江苏苏州开学考
2511杭州一模
2511金华十校
2511宁波一模
2511绍兴一模""".splitlines()


def pick_pdfs(folder: Path):
    """返回 (试题 PDF, 答案 PDF, 附加 PDF)。"""
    shiti = daan = None
    extra = []
    for p in sorted(folder.glob("*.pdf")):
        n = p.name
        if "作文" in n and "评分" in n:
            extra.append(p)
        elif "答案" in n or re.search(r"DA\.pdf$", n, re.I) or "评分" in n:
            if daan is None:
                daan = p
            else:
                extra.append(p)
        else:
            if shiti is None:
                shiti = p
            else:
                extra.append(p)
    return shiti, daan, extra


def find_xelatex():
    import glob
    p = shutil.which("xelatex")
    if p:
        return p
    for pat in (r"D:\texlive\*\bin\windows\xelatex.exe",
                r"?:\texlive\*\bin\windows\xelatex.exe",
                r"/usr/local/texlive/*/bin/*/xelatex"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def _kill_tree(proc):
    """杀掉子进程及其子进程（Windows 用 taskkill /T，其它平台 killpg 兜底）。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20)
        else:
            os.killpg(os.getpgid(proc.pid), 9)
    except Exception:  # noqa: BLE001 - 杀不掉也要往下走
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def ocr(pdf: Path, cache_dir: Path, model="vlm", timeout=300):
    """MinerU OCR，返回 (md 路径, 是否命中缓存)；vlm 沿用旧缓存名。

    用 Popen + wait 轮询 + 硬杀进程树，**不用 communicate/PIPE**：
    MinerU SDK 是网络长轮询（内部 timeout=1800s），子进程超时被杀后，
    它派生的网络线程/孙进程可能仍持有 stdout 管道句柄，`communicate()`
    会一直等管道 EOF，整批卡死（实测一份试卷卡了 20 分钟、无任何进程活动）。
    把子进程输出重定向到临时文件就没有这个管道可等。

    超时后：kill → 等 20s → 仍不退出则放弃该文档并报错，批量继续。
    """
    # 两种模式的 md 同名（都由 math_pdf_extract 按 pdf stem 命名），
    # 必须分目录缓存，否则 pipeline 会覆盖 vlm 结果
    out_dir = cache_dir if model == "vlm" else cache_dir / model
    md = out_dir / f"{pdf.stem}.md"
    if md.exists() and md.stat().st_size > 500:
        return md, True
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    logf = open(out_dir / f"{pdf.stem}.ocr.log", "w", encoding="utf-8",
                errors="replace")
    proc = subprocess.Popen(
        [sys.executable, str(EXTRACT), str(pdf),
         "--output-dir", str(out_dir), "--language", "ch", "--model", model],
        cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            pass
        logf.close()
        raise RuntimeError(f"OCR 超时 {timeout}s（已杀进程）: {pdf.name}")
    logf.close()
    if not md.exists():
        tail = ""
        try:
            tail = (out_dir / f"{pdf.stem}.ocr.log").read_text(
                encoding="utf-8", errors="replace")[-500:]
        except OSError:
            pass
        raise RuntimeError(f"OCR 未产出 md: {md}\n{tail}")
    return md, False


def ir_option_quality(ir):
    """统计选择题选项质量：(完整四项的选择题数, 散落在正文的孤儿选项数)。"""
    choices = sum(1 for b in ir.get("blocks", [])
                  if b.get("type") == "question" and len(b.get("options", [])) == 4)
    orphan = 0
    for b in ir.get("blocks", []):
        if b.get("type") == "para":
            orphan += sum(1 for ln in b.get("text", "").splitlines()
                          if re.match(r"^[A-D]\s*[.．、]", ln.strip()))
    return choices, orphan


def fix_missing_images(tex: str, folder: Path) -> str:
    """MinerU 偶尔只给图片引用不给图片文件；缺图改为占位，避免整卷编译失败。"""
    def repl(m):
        path = m.group(3)
        if (folder / path).exists():
            return m.group(0)
        return r"\mbox{〔图略〕}"

    return re.sub(r"(\\includegraphics)(\[[^\]]*\])?\{([^}]+)\}", repl, tex)


def process_dir(folder: Path, xelatex, keep_cache=True, ocr_timeout=300):
    shiti_pdf, daan_pdf, extra = pick_pdfs(folder)
    if not shiti_pdf or not daan_pdf:
        return False, f"缺试题或答案 PDF（试题={bool(shiti_pdf)} 答案={bool(daan_pdf)}）"

    exam = exam_name(folder.name, shiti_pdf.name, daan_pdf.name, prefer="folder")
    cache_root = folder / OCR_CACHE
    results = []
    problems = []           # 只有 OCR/编译失败才让整卷失败
    warnings = []           # 题号不连续等只是提醒，产物仍算成功

    # 宏包副本随卷部署，且必须在编译之前（否则 xelatex 找不到 ywexam.sty）
    for src in (STY_SRC, BUILD_SRC):
        dst = folder / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        elif src is BUILD_SRC:
            # 母本更新后同步覆盖，保证每卷 build.py 都是最新版
            shutil.copy2(src, dst)

    for kind, pdf in (("shiti", shiti_pdf), ("daan", daan_pdf)):
        stem = output_stem(kind, exam)
        cache_dir = cache_root / kind
        t0 = time.time()
        try:
            print(f"    [OCR] {stem} ← {pdf.name} (model={PRIMARY_MODEL}, "
                  f"timeout={ocr_timeout}s)", flush=True)
            md, cached = ocr(pdf, cache_dir, PRIMARY_MODEL, timeout=ocr_timeout)
            ir = md_convert(md.read_text(encoding="utf-8"), kind, title=exam)

            # 试题卷：选项解析不完整时换 OCR 模式重试（vlm ↔ pipeline），
            # 取选项更完整的一份。答案卷无 choices 结构，不做切换。
            switch_note = ""
            n_choices = n_orphan = 0
            if kind == "shiti":
                n_choices, n_orphan = ir_option_quality(ir)
                if n_choices < 6 or n_orphan > 0:
                    alt = ALT_MODEL
                    try:
                        md2, cached2 = ocr(pdf, cache_dir, alt, timeout=ocr_timeout)
                        ir2 = md_convert(md2.read_text(encoding="utf-8"), kind, title=exam)
                        c2, o2 = ir_option_quality(ir2)
                        if c2 * 10 - o2 > n_choices * 10 - n_orphan:
                            ir, md, n_choices, n_orphan = ir2, md2, c2, o2
                            switch_note = f" [切换{alt}: 选项{n_choices} 孤儿{n_orphan}]"
                        else:
                            switch_note = f" [{alt}无改善: 选项{c2} 孤儿{o2}]"
                        cached = cached and cached2
                    except Exception as exc:  # noqa: BLE001 - 重试失败保留原结果
                        switch_note = f" [{alt}失败: {exc}]"

            tex, report = render_paper(ir)
            tex = fix_missing_images(tex, folder)
            (folder / f"{stem}.tex").write_text(tex, encoding="utf-8")
            if report.warnings:
                warnings.append(f"{stem}: {report.warnings[0]}")

            # 图片放到试卷目录的 images/，OCR 输出里引用的是相对路径
            img_src = md.parent / pdf.stem / "images"
            if img_src.is_dir():
                dst = folder / "images"
                dst.mkdir(exist_ok=True)
                for f in img_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, dst / f.name)

            with open(folder / f"{stem}.buildlog", "w", encoding="utf-8") as log:
                for _ in range(2):
                    proc = subprocess.run(
                        [xelatex, "-interaction=nonstopmode", f"{stem}.tex"],
                        cwd=str(folder), stdout=log, stderr=subprocess.STDOUT)
                rc = proc.returncode
            if rc != 0 or not (folder / f"{stem}.pdf").exists():
                problems.append(f"{stem}: 编译失败 rc={rc}")

            if kind == "shiti" and (n_choices < 6 or n_orphan > 0):
                warnings.append(f"{stem}: 选项仍不完整（选项{n_choices} 孤儿{n_orphan}）")

            results.append(f"{stem} {int(time.time() - t0)}s"
                           + ("(缓存)" if cached else "") + switch_note)
        except Exception as exc:  # noqa: BLE001 - 单卷失败不中断批量
            problems.append(f"{stem}: {exc}")

    if not keep_cache:
        shutil.rmtree(cache_root, ignore_errors=True)

    msg = "; ".join(results)
    if problems:
        msg += " | " + " | ".join(problems)
    if warnings:
        msg += " | 警告: " + " / ".join(warnings)
    return not problems, msg


def main():
    ap = argparse.ArgumentParser(description="语文题库批量排版")
    ap.add_argument("--library", default=str(DEFAULT_LIBRARY), help="题库根目录")
    ap.add_argument("--only", nargs="+", help="只处理指定目录名")
    ap.add_argument("--limit", type=int, help="最多处理 N 个目录")
    ap.add_argument("--start", type=int, default=0, help="从第 N 个目录开始（0-based）")
    ap.add_argument("--no-keep-cache", action="store_true", help="完成后删除 .yw-ocr/")
    ap.add_argument("--ocr-timeout", type=int, default=300,
                    help="单份 OCR 超时秒数（默认 300；超时杀进程并记为失败，批量继续）")
    args = ap.parse_args()

    lib = Path(args.library)
    names = args.only or TRIAL_DIRS
    names = names[args.start:]
    if args.limit:
        names = names[:args.limit]

    xelatex = find_xelatex()
    if not xelatex:
        print("[FATAL] 未找到 xelatex")
        return 2

    ok, bad = 0, []
    for idx, name in enumerate(names, 1):
        folder = lib / name
        if not folder.is_dir():
            print(f"[{idx}/{len(names)}] {name}: 目录不存在")
            bad.append(name)
            continue
        print(f"[{idx}/{len(names)}] {name} ...", flush=True)
        success, msg = process_dir(folder, xelatex, not args.no_keep_cache,
                                   ocr_timeout=args.ocr_timeout)
        print(f"    {'[OK]' if success else '[FAIL]'} {msg}", flush=True)
        if success:
            ok += 1
        else:
            bad.append(name)

    print(f"\n完成：{ok}/{len(names)} 成功")
    if bad:
        print("失败目录：" + ", ".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
