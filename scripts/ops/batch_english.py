#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""batch_english.py — 英语题库批量转排（试题 + 参考答案）

从 ``evals/fixtures_english/manifest.json`` 读取 52 套卷的 PDF 映射，对每套执行::

    试题 PDF → MinerU OCR → md2english        → render_english → xelatex×2
    答案 PDF → MinerU OCR → md2english_answer → render_english → xelatex×2

产物（默认写到独立输出目录，不污染语料库）::

    <输出根>/<exam>/英语卷-<exam>.tex/.pdf
    <输出根>/<exam>/英语答案-<exam>.tex/.pdf

OCR 缓存在 ``<输出根>/.en-ocr/<kind>/``，重跑不重复计费。命名以 manifest 的
``exam`` 字段为准（md/tex 文件名与 exam 的映射唯一权威来源）。

用法::

    python scripts/ops/batch_english.py --only 2402武汉二调
    python scripts/ops/batch_english.py --limit 3 --kind shiti
    python scripts/ops/batch_english.py --output-dir ./english-batch
    python scripts/ops/batch_english.py --dry-run        # 只列计划，不跑 OCR/编译

注意：OCR 走 MinerU 云端 API，单份约 35~45 秒；52×2 份约 60~80 分钟。
"""

from __future__ import annotations

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

from md2english import parse_markdown as parse_shiti  # noqa: E402
from md2english_answer import parse_answer_markdown as parse_answer  # noqa: E402
from render_english import render_paper  # noqa: E402

FIX = ROOT / "evals" / "fixtures_english"
MANIFEST = FIX / "manifest.json"
TPL_DIR = ROOT / "templates" / "english"
EXTRACT = ROOT / "scripts" / "extract" / "pdf_extract.py"
OCR_CACHE = ".en-ocr"
TPL_FILES = ("英语试卷.cls", "英语试卷.sty")


def load_papers(manifest: Path = MANIFEST) -> list:
    return json.loads(manifest.read_text(encoding="utf-8"))["papers"]


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


def out_stem(kind: str, exam: str) -> str:
    """产物文件名：英语卷-<exam> / 英语答案-<exam>。

    exam 含空白时（如「2412  3+3+3」）连续空白折叠成单个下划线——
    xelatex 会把双空格折叠成单空格导致找不到文件；与 evals/fixtures_english/tex
    的 md→tex 命名惯例（md 保留空格、tex 用 `_`）一致。
    """
    safe_exam = re.sub(r"\s+", "_", exam)
    prefix = "英语卷" if kind == "shiti" else "英语答案"
    return f"{prefix}-{safe_exam}"


def ocr(pdf: Path, cache_dir: Path, model: str = "vlm",
        language: str = "en", timeout: int = 1800) -> tuple:
    """MinerU OCR，返回 (md 路径, 是否命中缓存)。用 Popen+timeout 防网络阻塞卡死。"""
    md = cache_dir / f"{pdf.stem}.md"
    if md.exists() and md.stat().st_size > 200:
        return md, True
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(EXTRACT), str(pdf),
           "--output-dir", str(cache_dir), "--language", language, "--model", model]
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RuntimeError(f"OCR 超时 {timeout}s: {pdf.name}")
    if not md.exists():
        raise RuntimeError(f"OCR 未产出 md: {md}\n{(out or '')[-500:]}")
    return md, False


def compile_tex(tex_path: Path, xelatex: str, log_path: Path):
    """连编两次（lastpage 页脚总页数需二次编译）。"""
    with open(log_path, "w", encoding="utf-8") as log:
        for _ in range(2):
            proc = subprocess.run(
                [xelatex, "-interaction=nonstopmode", tex_path.name],
                cwd=str(tex_path.parent), stdout=log, stderr=subprocess.STDOUT)
    pdf = tex_path.with_suffix(".pdf")
    if proc.returncode != 0 or not pdf.exists():
        raise RuntimeError(f"编译失败 rc={proc.returncode}: {tex_path.name}")


def process_paper(paper: dict, kind: str, library: Path, out_root: Path,
                  xelatex: str, model: str, keep_cache: bool) -> tuple:
    """处理一套卷的一种 kind。返回 (ok, msg)。"""
    exam = paper["exam"]
    pdf_field = "source_pdf" if kind == "shiti" else "source_answer_pdf"
    pdf_rel = paper.get(pdf_field)
    if not pdf_rel:
        return False, f"缺 {pdf_field} 映射"
    pdf = library / paper["source_dir"] / pdf_rel
    if not pdf.is_file():
        return False, f"PDF 不存在: {pdf}"

    work = out_root / exam
    work.mkdir(parents=True, exist_ok=True)
    # 缓存必须按卷（exam）分层：52 套卷的 PDF 大量同名（试题.pdf/答案.pdf），
    # 若按 kind 共用一层，同名 stem 的 md 会互相覆盖，导致产物串卷（实测 03 卷
    # 复用了 02 卷的 OCR 结果）。exam 目录名唯一，天然隔离。
    cache_dir = out_root / OCR_CACHE / exam / kind
    stem = out_stem(kind, exam)
    t0 = time.time()

    # 模板随卷部署（必须在编译前）；总是覆盖，保证模板更新同步到各卷
    for name in TPL_FILES:
        shutil.copy2(TPL_DIR / name, work / name)

    md, cached = ocr(pdf, cache_dir, model=model)
    md_text = md.read_text(encoding="utf-8")
    if kind == "shiti":
        ir, report = parse_shiti(md_text, source=md.name)
    else:
        ir, report = parse_answer(md_text, source=md.name)

    tex, rreport = render_paper(ir)
    tex_path = work / f"{stem}.tex"
    tex_path.write_text(tex, encoding="utf-8")
    compile_tex(tex_path, xelatex, work / f"{stem}.buildlog")

    # 图片（若有）拷到卷目录 images/
    img_src = md.parent / pdf.stem / "images"
    if img_src.is_dir():
        dst = work / "images"
        dst.mkdir(exist_ok=True)
        for f in img_src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)

    if not keep_cache:
        shutil.rmtree(out_root / OCR_CACHE, ignore_errors=True)

    m = ir["meta"]
    warns = (report.warnings + rreport.warnings)[:2]
    msg = (f"{stem}.pdf {int(time.time()-t0)}s" + ("(缓存)" if cached else "")
           + f" [{m['block_count']}块")
    if kind == "answer":
        msg += f" / {m.get('answer_groups', 0)}答案组 / {m.get('blank_answers', 0)}填空"
    msg += "]"
    if warns:
        msg += " | 告警: " + " / ".join(warns)
    return True, msg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", default=None,
                    help="题库根目录（默认取 manifest.corpus_root，可用 SHIJUAN_ENGLISH_CORPUS 覆盖）")
    ap.add_argument("--output-dir", default="./english-batch", help="产物输出根目录")
    ap.add_argument("--manifest", default=str(MANIFEST), help="manifest.json 路径")
    ap.add_argument("--only", nargs="+", help="只处理指定 exam 名（或序号，如 01）")
    ap.add_argument("--limit", type=int, help="最多处理 N 套卷")
    ap.add_argument("--start", type=int, default=0, help="从第 N 套开始（0-based）")
    ap.add_argument("--kind", choices=("shiti", "answer", "both"), default="both",
                    help="处理试题/答案/两者（默认 both）")
    ap.add_argument("--ocr-model", default="vlm", help="MinerU 模式 vlm/pipeline")
    ap.add_argument("--no-keep-cache", action="store_true", help="完成后删除 OCR 缓存")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不跑 OCR/编译")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    papers = load_papers(manifest)
    corpus_root = (args.library
                   or os.environ.get("SHIJUAN_ENGLISH_CORPUS")
                   or json.loads(manifest.read_text(encoding="utf-8")).get("corpus_root"))
    library = Path(corpus_root)
    out_root = Path(args.output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # 选择卷
    selected = papers[args.start:]
    if args.only:
        wanted = {w.zfill(2) for w in args.only}
        selected = [p for p in papers
                    if p["exam"] in args.only or f"{p['index']:02d}" in wanted]
    if args.limit:
        selected = selected[:args.limit]

    kinds = ("shiti", "answer") if args.kind == "both" else (args.kind,)
    print(f"[INFO] 题库: {library}")
    print(f"[INFO] 输出: {out_root}")
    print(f"[INFO] 计划: {len(selected)} 套 × {len(kinds)} 种 = {len(selected)*len(kinds)} 个产物")
    if args.dry_run:
        for p in selected:
            for k in kinds:
                field = "source_pdf" if k == "shiti" else "source_answer_pdf"
                print(f"  {p['index']:02d} {p['exam']} [{k}] "
                      f"{library / p['source_dir'] / p.get(field, '<无映射>')}")
        return 0

    xelatex = find_xelatex()
    if not xelatex:
        print("[FATAL] 未找到 xelatex")
        return 2

    ok, bad = 0, []
    total = len(selected) * len(kinds)
    done = 0
    for p in selected:
        for k in kinds:
            done += 1
            print(f"[{done}/{total}] {p['index']:02d} {p['exam']} [{k}] ...", flush=True)
            try:
                success, msg = process_paper(
                    p, k, library, out_root, xelatex, args.ocr_model,
                    not args.no_keep_cache)
            except Exception as exc:  # noqa: BLE001 - 单卷失败不中断批量
                success, msg = False, str(exc)
            print(f"    {'[OK]' if success else '[FAIL]'} {msg}", flush=True)
            if success:
                ok += 1
            else:
                bad.append(f"{p['exam']}[{k}]")

    print(f"\n完成：{ok}/{total} 成功")
    if bad:
        print("失败：" + ", ".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
