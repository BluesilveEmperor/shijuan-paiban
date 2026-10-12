#!/usr/bin/env python3
"""Rebuild every .tex whose .log still shows compile errors, from its MD."""
import os, re, subprocess, shutil
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_convert import fix_common_issues

BASE = Path(r"D:\Music\试题加题库\高三数学") if os.name == 'nt' else Path("/mnt/d/Music/试题加题库/高三数学")
MD_DIR = BASE / ".math-output"
XELATEX = 'xelatex' if os.name == 'nt' else 'xelatex.exe'  # interop from WSL


def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=timeout, encoding='utf-8', errors='ignore')
    return r.returncode, r.stdout, r.stderr


def log_errors(tex: Path) -> int:
    log = tex.with_suffix('.log')
    if not log.exists():
        return -1
    return len(re.findall(r'^!', log.read_text(encoding='utf-8', errors='ignore'), re.MULTILINE))


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    targets = []
    for tex in sorted(BASE.glob('*.tex')):
        if only and not any(o in tex.stem for o in only):
            continue
        n = log_errors(tex)
        if n != 0:
            targets.append((tex, n))
    print(f"Files with errors: {len(targets)}")
    for tex, n in targets:
        print(f"  {n:>4}  {tex.stem}")

    results = []
    for tex, old_n in targets:
        name = tex.stem
        md = MD_DIR / f"{name}.md"
        if not md.exists():
            print(f"SKIP (no md): {name}")
            results.append((name, old_n, 'NO MD'))
            continue
        is_ans = any(k in name for k in ('答案', '参考', '解析'))
        script = Path(__file__).parent / ('md2ans.py' if is_ans else 'md2tex.py')
        print(f"\n=== {name} (was {old_n} errors) ===")
        rc, out, err = run(f'"{sys.executable}" "{script}" "{md}" "{tex}" --img-base "Images-{name}"', 60)
        if rc != 0 and err.strip():
            print(f"  CONVERT ERROR: {err.strip()[:300]}")
        fix_common_issues(str(tex))
        # ensure images
        src_img = MD_DIR / name
        dst_img = BASE / f"Images-{name}"
        if src_img.exists():
            dst_img.mkdir(exist_ok=True)
            for img in src_img.glob('**/*'):
                if img.suffix.lower() in ('.jpg', '.png', '.jpeg'):
                    if not (dst_img / img.name).exists():
                        shutil.copy2(img, dst_img / img.name)
        os.chdir(BASE)
        run(f'{XELATEX} -interaction=nonstopmode "{name}.tex"', 120)
        n = log_errors(tex)
        if n == 0:
            run(f'{XELATEX} -interaction=nonstopmode "{name}.tex"', 120)
            print("  OK (0 errors)")
        else:
            print(f"  ERRORS: {n}")
        results.append((name, n, 'OK' if n == 0 else 'ERR'))

    print("\n" + "=" * 60)
    ok = sum(1 for _, n, _ in results if n == 0)
    print(f"RESULTS: {ok} fixed / {len(results)} total")
    for name, n, st in results:
        if n != 0:
            print(f"  STILL {n}: {name}")


if __name__ == '__main__':
    main()
