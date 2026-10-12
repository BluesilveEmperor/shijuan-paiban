#!/usr/bin/env python3
"""Re-process files with errors."""
import os, sys, subprocess, shutil, re
from pathlib import Path

def run(cmd, timeout=120):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='ignore')
    return result.returncode, result.stdout, result.stderr

def fix_common_issues(tex_path):
    text = Path(tex_path).read_text(encoding='utf-8')
    text = re.sub(r'\\left\\lbracket', r'\\left[', text)
    text = re.sub(r'\\left\(([^)]*?)\\right\]', r'\\left(\1\\right)', text)
    text = re.sub(r'\$([^$]*?)\\geqslant\$\s+g\s*\(x\)\\geqslant', r'$\1\\geqslant g(x) \\geqslant', text)
    text = re.sub(r'(?<!\\)#', r'\\#', text)
    text = re.sub(r'\\#\s*非选择题部分.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\#\s*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\right\)\$', r'\\right)', text)
    Path(tex_path).write_text(text, encoding='utf-8')

def main():
    base = Path(r"D:\Music\试题加题库\高三数学")
    md_dir = base / ".math-output"
    script = r"D:\Desktop\shijuan-paiban\scripts\md2tex.py"
    
    # Files with errors (from previous run)
    error_files = [
        "浙江省温州市2024-2025学年高三下学期第二次适应性考试数学试题",
        "湖北省武汉市2024年9月部分学校高三调研考试数学试题",
        "湖北省高中名校联盟第三次联合测评2025届高三数学测评卷",
        "湖南省2025届高三一轮复习收官数学试题",
        "甘肃省兰州市2025届高三下学期诊断考试（一模）数学试题",
        "湖南雅礼中学2025届高三上学期1月综合自主测试数学试题",
        "雅礼2025届高三入学考试数学",
        "雅礼中学2025届高三月考试卷三数学",
        "雅礼中学2025届高三月考（四）数学试卷",
        "辽宁省名校联盟2025届高三下学期3月联合考试数学试题",
        "湖南省2025届高三九校联盟第一次联考数学试题",
        "河南省2025年高考综合改革适应性演练-数学",
    ]
    
    for name in error_files:
        md_file = md_dir / f"{name}.md"
        tex_file = base / f"{name}.tex"
        img_dir = base / f"Images-{name}"
        src_img_dir = md_dir / name / "images"
        
        if not md_file.exists():
            print(f"SKIP: {name} (no md)")
            continue
        
        print(f"Processing: {name[:40]}...")
        
        # Convert
        cmd = f'python "{script}" "{md_file}" "{tex_file}" --img-base "Images-{name}"'
        run(cmd, 30)
        
        # Fix issues
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
        rc, out, err = run(f'xelatex -interaction=nonstopmode "{name}.tex"', 60)
        
        log_file = base / f"{name}.log"
        if log_file.exists():
            log_text = log_file.read_text(encoding='utf-8', errors='ignore')
            error_count = len(re.findall(r'^!', log_text, re.MULTILINE))
            print(f"  Errors: {error_count}")
        else:
            print(f"  No log")

if __name__ == "__main__":
    main()
