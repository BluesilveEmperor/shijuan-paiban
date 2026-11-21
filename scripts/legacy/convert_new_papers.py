#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert and compile the 58 new OCR'd papers (exam via md2tex, ans via md2ans).

Targets are derived from finish_papers.MANIFEST with the 5 combined
试题+答案 stems replaced by their split outputs (see split_combined.py).

Resumable: a target is skipped when its PDF exists and its log has no '!' errors.
Run:  python3 /mnt/d/Desktop/shijuan-paiban/scripts/convert_new_papers.py [--list]
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
from finish_papers import MANIFEST  # noqa: E402
from batch_convert import fix_common_issues  # noqa: E402

BASE = Path(r"D:\Music\试题加题库\高三数学" if os.name == 'nt'
            else "/mnt/d/Music/试题加题库/高三数学")
MD_DIR = BASE / ".math-output"
XELATEX = 'xelatex' if os.name == 'nt' else 'xelatex.exe'

# combined stem -> [(split stem, kind), ...]
COMBINED_MAP = {
    "2025届长沙一中高三上学期阶段性检测（一）数学试题+答案":
        [("2025届长沙一中高三上学期阶段性检测（一）数学试题", "exam")],
    "广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题+答案":
        [("广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题", "exam"),
         ("广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题答案", "ans")],
    "湖南省长郡中学2025年高三下学期月考（七）数学试题+答案":
        [("湖南省长郡中学2025年高三下学期月考（七）数学试题", "exam"),
         ("湖南省长郡中学2025年高三下学期月考（七）数学试题答案", "ans")],
    "雅礼中学2025届高三第六次月考数学试题+答案":
        [("雅礼中学2025届高三第六次月考数学试题", "exam"),
         ("雅礼中学2025届高三第六次月考数学试题答案", "ans")],
    "浙江省杭州学军中学2025届高三下学期2月月考数学试题+答案":
        [("浙江省杭州学军中学2025届高三下学期2月月考数学试题", "exam"),
         ("浙江省杭州学军中学2025届高三下学期2月月考数学试题答案", "ans")],
}


# Regular manifest entries that contain a trailing answer key inside the
# same MD; the MD is split by split_xj3.py into exam + ans files.
SPLIT_MAP = {
    "浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题":
        [("浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题", "exam"),
         ("浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题答案", "ans")],
}


def build_targets():
    targets = []
    for _src, name, kind in MANIFEST:
        if name in COMBINED_MAP:
            targets.extend(COMBINED_MAP[name])
        elif name in SPLIT_MAP:
            targets.extend(SPLIT_MAP[name])
        else:
            targets.append((name, kind))
    return targets


def run(cmd, timeout=180):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=timeout, encoding='utf-8', errors='ignore')
    return r.returncode, r.stdout, r.stderr


def log_errors(log_path):
    if not log_path.exists():
        return -1
    return len(re.findall(r'^!', log_path.read_text(encoding='utf-8',
                                                    errors='ignore'), re.M))


def is_done(name):
    return (BASE / f"{name}.pdf").exists() and log_errors(BASE / f"{name}.log") == 0


def copy_images(name):
    src = MD_DIR / name
    dst = BASE / f"Images-{name}"
    if not src.is_dir():
        return 0
    n = 0
    for img in src.glob("**/*"):
        if img.suffix.lower() in ('.jpg', '.png', '.jpeg'):
            dst.mkdir(exist_ok=True)
            target = dst / img.name
            if not target.exists():
                shutil.copy2(img, target)
                n += 1
    return n


def process(name, kind):
    md_file = MD_DIR / f"{name}.md"
    tex_file = BASE / f"{name}.tex"
    script = SCRIPT_DIR / ("md2tex.py" if kind == "exam" else "md2ans.py")

    if not md_file.exists():
        return "NO_MD", 0
    if tex_file.exists() and kind not in ("exam", "ans"):
        return "SKIP", 0

    # convert
    cmd = f'"{sys.executable}" "{script}" "{md_file}" "{tex_file}" --img-base "Images-{name}"'
    rc, out, err = run(cmd, 120)
    if rc != 0:
        print(f"    CONVERT FAIL rc={rc}: {err.strip()[:300]}")
        return "CONVERT_FAIL", 1
    if not tex_file.exists():
        print(f"    no tex produced: {out.strip()[:200]}")
        return "NO_TEX", 1

    # fixes + images
    fix_common_issues(str(tex_file))
    copy_images(name)

    # compile twice
    os.chdir(BASE)
    for _ in range(2):
        run(f'{XELATEX} -interaction=nonstopmode "{name}.tex"', 180)

    n_err = log_errors(BASE / f"{name}.log")
    return ("OK" if n_err == 0 else "TEX_ERRORS"), n_err


def main():
    args = sys.argv[1:]
    targets = build_targets()
    print(f"targets: {len(targets)} "
          f"(exam={sum(1 for _n, k in targets if k == 'exam')}, "
          f"ans={sum(1 for _n, k in targets if k == 'ans')})")

    pending = [(n, k) for n, k in targets if not is_done(n)]
    skipped = len(targets) - len(pending)
    print(f"already done: {skipped}, pending: {len(pending)}")
    if "--list" in args:
        for n, k in pending:
            print(f"  [{k}] {n}")
        return

    ok = fail = 0
    failures = []
    for i, (name, kind) in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] [{kind}] {name[:46]}...")
        status, n_err = process(name, kind)
        if status == "OK":
            ok += 1
        elif status in ("NO_MD",):
            fail += 1
            failures.append((name, status))
            print(f"    {status}")
        else:
            fail += 1
            failures.append((name, f"{status} ({n_err})"))
            print(f"    {status}: {n_err} errors")

    print(f"\n===== RESULTS: ok={ok} fail={fail} (skipped {skipped}) =====")
    for name, why in failures:
        print(f"  {why}  {name}")


if __name__ == "__main__":
    main()
