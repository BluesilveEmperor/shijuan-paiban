#!/usr/bin/env python3
"""Batch convert and compile all exam papers."""
import os, sys, subprocess, shutil, re
from pathlib import Path

def run(cmd, timeout=120):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='ignore')
    return result.returncode, result.stdout, result.stderr

def fix_common_issues(tex_path):
    """Apply common fixes to generated tex (body only, preamble untouched)."""
    text = Path(tex_path).read_text(encoding='utf-8')
    # Split at \begin{document}: all fixes below must NEVER touch the preamble
    # (an earlier version escaped '#1' inside \newcommand{\cir} and then the
    # '\#' line-deletion rule truncated the macro definitions -> \@argdef EOF).
    marker = r'\begin{document}'
    pos = text.find(marker)
    if pos >= 0:
        head, body = text[:pos + len(marker)], text[pos + len(marker):]
    else:
        head, body = '', text
    # Fix \left\lbracket -> \left[
    body = re.sub(r'\\left\\lbracket', r'\\left[', body)
    # Fix \left( ... \right] -> \left( ... \right)
    body = re.sub(r'\\left\(([^)]*?)\\right\]', r'\\left(\1\\right)', body)
    # Fix split math: $formula$ text\cmd -> $formula text\cmd$
    body = re.sub(r'\$([^$]*?)\\geqslant\$\s+g\s*\(x\)\\geqslant', r'$\1\\geqslant g(x) \\geqslant', body)
    # Fix # in text
    body = re.sub(r'(?<!\\)#', r'\\#', body)
    # Remove heading-like lines only: escaped # must sit at line start.
    # (A mid-line \# is OCR noise inside prose/math -- deleting to EOL there
    # truncates single-line items and uncloses \daan{...} / math spans.)
    body = re.sub(r'^[ \t]*\\#[ \t]*非选择题部分.*$', '', body, flags=re.MULTILINE)
    body = re.sub(r'^[ \t]*\\#.*$', '', body, flags=re.MULTILINE)
    # Compile guard for inline math spans (OCR noise that breaks xelatex)
    body = _fix_math_spans(body)
    # Bare \limits-mathop sub/superscripts need braces: x_\min -> x_{\min}
    # (TeX reports "Missing { inserted ... \mathop" for x_\min / x_\max).
    body = re.sub(r'([_^])\\(min|max|sup|inf|lim)(?![a-zA-Z{])', r'\1{\\\2}', body)
    Path(tex_path).write_text(head + body, encoding='utf-8')


_ALIGN_ENV_RE = re.compile(
    r'\\begin\{(?:aligned|align|cases|array|(?:p|b|v|B|V|small)?matrix|'
    r'tabular|gather|gathered|split|multline)\*?\}')


def _math_brace_depth(s):
    """Net {}/{} depth, treating \\{ \\} as literals and skipping cmd chars."""
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        if s[i] == '\\':
            i += 2
            continue
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    return depth


def _fix_math_span(s):
    """Compile-safe cleanups inside one inline math span (no unescaped '$')."""
    # MinerU escaped underscores: \_ renders as literal '_' char, not subscript
    s = s.replace('\\_', '_')
    # Superscript/subscript of a text discretionary: ^\* -> ^{\ast}
    s = re.sub(r'([_^])\s*\\\*', r'\1{\\ast}', s)
    # Stray bare \array token (leftover from a broken \begin{array})
    s = re.sub(r'\\array(?![a-zA-Z])', '', s)
    # \kern with non-numeric argument (e.g. '\kern - d', '\kern - delimiterspace')
    s = re.sub(r'\\kern\s*-?\s*(?![-0-9.])\S*', '', s)
    # \frac/\dfrac/\tfrac with a truncated second argument:
    # '\frac{X}' at span end or followed by '}' -> give it an empty denominator
    s = re.sub(r'(\\[dt]?frac)\s*(\{(?:[^{}]|\{[^{}]*\})*\})\s*(?=\}|$)', r'\1\2{}', s)
    # Alignment tabs are only legal inside alignment environments
    if not _ALIGN_ENV_RE.search(s):
        s = s.replace('&', ' ')
    # Dangling ^/_ at span end (lost exponent/argument)
    s = re.sub(r'[_^]\s*$', '', s)
    # Unbalanced braces: close what was left open (truncated OCR groups)
    d = _math_brace_depth(s)
    if d > 0:
        s = s + '}' * d
    return s


def _fix_math_spans(body):
    """Apply _fix_math_span to every $...$ span in body.

    With a balanced '$' count every odd part is a math span.  With an odd
    count (broken OCR) the prefix pairs are still processed and the
    dangling tail is preserved untouched.
    """
    parts = re.split(r'(?<!\\)\$', body)
    out = [parts[0]]
    k = 1
    while k + 1 < len(parts):
        out.append('$')
        out.append(_fix_math_span(parts[k]))
        out.append('$')
        out.append(parts[k + 1])
        k += 2
    if k < len(parts):  # dangling unpaired tail (odd '$' count)
        out.append('$')
        out.append(parts[k])
    return ''.join(out)

def main():
    base = Path(r"D:\Music\试题加题库\高三数学") if os.name == 'nt' else Path("/mnt/d/Music/试题加题库/高三数学")
    md_dir = base / ".math-output"
    script = Path(__file__).parent / "md2tex.py"
    xelatex = 'xelatex' if os.name == 'nt' else 'xelatex.exe'  # interop from WSL
    
    # Get all exam markdown files (not answers)
    exam_files = sorted([f for f in md_dir.glob("*.md") 
                        if "答案" not in f.name and "解析" not in f.name and "参考" not in f.name
                        and "雅礼中学2025届高三月考数学试卷一" not in f.name])  # skip already done
    
    print(f"Found {len(exam_files)} exam files to process")
    
    success = 0
    failed = 0
    results = []
    
    for i, md_file in enumerate(exam_files):
        name = md_file.stem
        tex_file = base / f"{name}.tex"
        img_dir = base / f"Images-{name}"
        src_img_dir = md_dir / name / "images"
        
        print(f"\n[{i+1}/{len(exam_files)}] {name[:40]}...")
        
        # Convert
        cmd = f'"{sys.executable}" "{script}" "{md_file}" "{tex_file}" --img-base "Images-{name}"'
        rc, out, err = run(cmd, 30)
        
        # Fix common issues
        if tex_file.exists():
            fix_common_issues(tex_file)
        
        # Copy images
        if src_img_dir.exists():
            img_dir.mkdir(exist_ok=True)
            for img in src_img_dir.glob("*"):
                if not (img_dir / img.name).exists():
                    shutil.copy2(img, img_dir / img.name)
        
        # Compile
        os.chdir(base)
        rc, out, err = run(f'{xelatex} -interaction=nonstopmode "{name}.tex"', 60)

        # Check for errors
        log_file = base / f"{name}.log"
        if log_file.exists():
            log_text = log_file.read_text(encoding='utf-8', errors='ignore')
            error_count = len(re.findall(r'^!', log_text, re.MULTILINE))
            if error_count == 0:
                # Second pass for references
                run(f'{xelatex} -interaction=nonstopmode "{name}.tex"', 60)
                print(f"  OK (0 errors)")
                success += 1
                results.append((name, "OK", 0))
            else:
                print(f"  ERRORS: {error_count}")
                failed += 1
                results.append((name, "ERRORS", error_count))
        else:
            print(f"  NO LOG")
            failed += 1
            results.append((name, "NO LOG", -1))
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {success} OK, {failed} failed")
    for name, status, count in results:
        if status != "OK":
            print(f"  {status}({count}): {name[:50]}")
    # error distribution (compare with baseline)
    dist = {}
    for name, status, count in results:
        k = count if count >= 0 else 'nolog'
        dist[k] = dist.get(k, 0) + 1
    print("\nERROR DISTRIBUTION:")
    for k in sorted(dist, key=lambda x: (isinstance(x, str), x)):
        print(f"  {k} errors: {dist[k]} files")

if __name__ == "__main__":
    main()
