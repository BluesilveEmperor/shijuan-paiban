#!/usr/bin/env python3
"""Batch convert and compile all answer documents (答案 MDs from MinerU)."""
import os, sys, subprocess, shutil, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_convert import fix_common_issues


def run(cmd, timeout=120):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                            timeout=timeout, encoding='utf-8', errors='ignore')
    return result.returncode, result.stdout, result.stderr


def main():
    base = Path(r"D:\Music\试题加题库\高三数学") if os.name == 'nt' else Path("/mnt/d/Music/试题加题库/高三数学")
    md_dir = base / ".math-output"
    script = Path(__file__).parent / "md2ans.py"
    xelatex = 'xelatex' if os.name == 'nt' else 'xelatex.exe'  # interop from WSL

    md_files = sorted(p for p in md_dir.glob("*.md") if '答案' in p.stem)
    print(f"Found {len(md_files)} answer markdown files\n")

    success = failed = 0
    results = []
    for idx, md_file in enumerate(md_files, 1):
        name = md_file.stem
        print(f"[{idx}/{len(md_files)}] {name}...")
        tex_file = base / f"{name}.tex"

        # Convert
        cmd = f'"{sys.executable}" "{script}" "{md_file}" "{tex_file}" --img-base "Images-{name}"'
        rc, out, err = run(cmd, 60)
        if out.strip():
            print('    ' + out.strip().replace('\n', '\n    '))
        if rc != 0 and err.strip():
            print(f'    CONVERT ERROR: {err.strip()[:500]}')

        # Fix common issues (body only)
        if tex_file.exists():
            fix_common_issues(str(tex_file))

        # Copy images
        src_img_dir = md_dir / name
        img_dir = base / f"Images-{name}"
        if src_img_dir.exists():
            img_dir.mkdir(exist_ok=True)
            for img in src_img_dir.glob("**/*"):
                if img.suffix.lower() in ('.jpg', '.png', '.jpeg'):
                    if not (img_dir / img.name).exists():
                        shutil.copy2(img, img_dir / img.name)

        # Compile
        os.chdir(base)
        run(f'{xelatex} -interaction=nonstopmode "{name}.tex"', 90)

        log_file = base / f"{name}.log"
        if log_file.exists():
            log_text = log_file.read_text(encoding='utf-8', errors='ignore')
            error_count = len(re.findall(r'^!', log_text, re.MULTILINE))
            if error_count == 0:
                run(f'xelatex -interaction=nonstopmode "{name}.tex"', 90)  # LastPage pass
                print("  OK (0 errors)")
                success += 1
                results.append((name, 0))
            else:
                print(f"  ERRORS: {error_count}")
                failed += 1
                results.append((name, error_count))
        else:
            print("  NO LOG")
            failed += 1
            results.append((name, -1))

    print(f"\n{'='*60}")
    print(f"RESULTS: {success} OK, {failed} failed")

    errs = sorted((e, n) for n, e in results if e != 0)
    if errs:
        print("\nERRORS:")
        for e, n in errs:
            print(f"  ERRORS({e}): {n}")

    print("\nERROR DISTRIBUTION:")
    from collections import Counter
    dist = Counter(e for _, e in results)
    for e in sorted(dist):
        print(f"  {e} errors: {dist[e]} files")


if __name__ == '__main__':
    main()
