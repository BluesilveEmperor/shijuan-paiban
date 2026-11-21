#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_test.py - 批量测试脚本：随机选择试卷，解析→生成→编译→统计

用法:
  python scripts/batch_test.py <试卷目录> <数量> [输出目录]
  python scripts/batch_test.py "D:/Documents/02_Program/math-exam-helper/高三数学" 30 ./test-output
"""

import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def find_pdfs(root_dir):
    """查找所有 PDF 文件"""
    pdfs = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith('.pdf'):
                pdfs.append(os.path.join(dirpath, f))
    return pdfs


def select_random(pdfs, count):
    """随机选择指定数量的 PDF"""
    if len(pdfs) <= count:
        return pdfs
    return random.sample(pdfs, count)


def extract_with_mineru(pdf_path, output_dir):
    """使用 MinerU SDK 提取 PDF 内容"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    extract_script = os.path.join(script_dir, "math_pdf_extract.py")

    if not os.path.exists(extract_script):
        return None, "math_pdf_extract.py not found"

    cmd = [
        sys.executable, extract_script,
        pdf_path,
        "--output-dir", output_dir,
        "--language", "ch"
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            # 查找生成的 md 文件
            pdf_stem = Path(pdf_path).stem
            for f in os.listdir(output_dir):
                if f.endswith('.md'):
                    return os.path.join(output_dir, f), None
            return None, "No .md file generated"
        else:
            return None, result.stderr[:500] if result.stderr else "Unknown error"
    except subprocess.TimeoutExpired:
        return None, "MinerU extraction timeout (300s)"
    except Exception as e:
        return None, str(e)


def generate_latex(md_path, output_tex, is_answer=False):
    """读取 Markdown 并生成 LaTeX（简化版：仅提取结构）"""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取标题（第一行）
        title = "数学试卷"
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                title = line.lstrip('#').strip()
                break

        # 生成简单的 LaTeX 骨架
        # 实际使用时，这里应该调用 AI 进行逐题转换
        # 这里仅做结构提取测试
        latex = r"""\documentclass[12pt, a4paper, oneside]{ctexart}
\usepackage{amsmath, amsthm, amssymb}
\usepackage[bookmarks=true, colorlinks, citecolor=blue, linkcolor=black]{hyperref}
\usepackage[a4paper, margin=2.5cm, footskip=1cm]{geometry}
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{数学试题第\thepage 页（共\pageref{LastPage}页）}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\usepackage{graphicx}
\usepackage{tasks}
\usepackage{enumitem}
\newlist{examenum}{enumerate}{3}
\setlist[examenum,1]{label=\arabic*., leftmargin=2em, itemsep=0.3em, parsep=0em}
\setlist[examenum,2]{label=(\arabic*), leftmargin=1.5em, itemsep=0.1em, parsep=0em}
\setlist[examenum,3]{label=(\roman*), leftmargin=1.5em, itemsep=0.1em, parsep=0em}
\newcommand{\blank}{\underline{\hspace{2cm}}}
\newcommand{\mi}{\mathrm{i}}
\newcommand{\me}{\mathrm{e}}

\begin{document}
\begin{center}
    {\LARGE\textbf{""" + title + r"""}}
\end{center}
\vspace{1em}

\section*{（AI 逐题转换区域）}
以下为 MinerU 提取的原始内容长度统计：
\begin{itemize}
    \item 总字符数：""" + str(len(content)) + r"""
    \item 总行数：""" + str(len(content.split('\n'))) + r"""
\end{itemize}

\end{document}
"""

        with open(output_tex, 'w', encoding='utf-8') as f:
            f.write(latex)
        return None
    except Exception as e:
        return str(e)


def compile_latex(tex_path, work_dir):
    """编译 LaTeX"""
    tex_name = os.path.basename(tex_path)
    for i in range(2):
        result = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', '-output-directory', work_dir, tex_name],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
            cwd=work_dir
        )

    pdf_path = tex_path.replace('.tex', '.pdf')
    if os.path.exists(pdf_path):
        return True, None
    else:
        # 提取错误信息
        log_path = tex_path.replace('.tex', '.log')
        errors = []
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if 'Error' in line or 'Undefined' in line:
                        errors.append(line.strip())
        return False, '; '.join(errors[:3]) if errors else "Compilation failed"


def run_single_test(pdf_path, output_dir, test_idx):
    """运行单份试卷测试"""
    result = {
        "index": test_idx,
        "pdf": pdf_path,
        "pdf_name": os.path.basename(pdf_path),
        "status": "pending",
        "mineru_time": 0,
        "compile_time": 0,
        "error": None,
        "md_chars": 0,
        "pages": 0,
    }

    pdf_name = Path(pdf_path).stem
    safe_name = re.sub(r'[^\w\-]', '_', pdf_name)[:50]
    test_dir = os.path.join(output_dir, f"{test_idx:03d}_{safe_name}")
    os.makedirs(test_dir, exist_ok=True)

    # 步骤 1: MinerU 提取
    t0 = time.time()
    md_path, err = extract_with_mineru(pdf_path, test_dir)
    result["mineru_time"] = time.time() - t0

    if err:
        result["status"] = "mineru_failed"
        result["error"] = err
        return result

    # 统计提取结果
    if md_path and os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        result["md_chars"] = len(content)

    # 步骤 2: 生成 LaTeX
    tex_path = os.path.join(test_dir, f"{safe_name}.tex")
    err = generate_latex(md_path, tex_path)
    if err:
        result["status"] = "latex_gen_failed"
        result["error"] = err
        return result

    # 步骤 3: 编译
    t0 = time.time()
    success, err = compile_latex(tex_path, test_dir)
    result["compile_time"] = time.time() - t0

    if success:
        result["status"] = "success"
        pdf_out = tex_path.replace('.tex', '.pdf')
        result["pages"] = 0  # 可用 pdfinfo 获取
    else:
        result["status"] = "compile_failed"
        result["error"] = err

    return result


def main():
    if len(sys.argv) < 3:
        print("用法: python scripts/batch_test.py <试卷目录> <数量> [输出目录]")
        sys.exit(1)

    root_dir = sys.argv[1]
    count = int(sys.argv[2])
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "./test-output"

    os.makedirs(output_dir, exist_ok=True)

    # 查找并选择 PDF
    all_pdfs = find_pdfs(root_dir)
    print(f"[INFO] 共找到 {len(all_pdfs)} 份 PDF 试卷")

    selected = select_random(all_pdfs, count)
    print(f"[INFO] 随机选择 {len(selected)} 份进行测试")
    print(f"[INFO] 输出目录: {output_dir}")
    print("=" * 60)

    # 运行测试
    results = []
    for i, pdf in enumerate(selected, 1):
        print(f"\n[{i}/{len(selected)}] 处理: {os.path.basename(pdf)}")
        result = run_single_test(pdf, output_dir, i)
        results.append(result)
        status_icon = {
            "success": "[OK]",
            "mineru_failed": "[FAIL-MinerU]",
            "latex_gen_failed": "[FAIL-Gen]",
            "compile_failed": "[FAIL-Compile]",
        }.get(result["status"], "?")
        print(f"    状态: {status_icon} | MinerU: {result['mineru_time']:.1f}s | 编译: {result['compile_time']:.1f}s")
        if result["error"]:
            print(f"    错误: {result['error'][:100]}")

    # 统计报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)

    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    mineru_fail = sum(1 for r in results if r["status"] == "mineru_failed")
    latex_fail = sum(1 for r in results if r["status"] == "latex_gen_failed")
    compile_fail = sum(1 for r in results if r["status"] == "compile_failed")

    print(f"总计: {total} 份")
    print(f"  [OK] 成功: {success} ({success/total*100:.1f}%)")
    print(f"  ❌ MinerU 失败: {mineru_fail}")
    print(f"  ❌ LaTeX 生成失败: {latex_fail}")
    print(f"  ❌ 编译失败: {compile_fail}")

    avg_mineru = sum(r["mineru_time"] for r in results) / total
    avg_compile = sum(r["compile_time"] for r in results) / total
    print(f"\n平均耗时:")
    print(f"  MinerU 提取: {avg_mineru:.1f}s")
    print(f"  LaTeX 编译: {avg_compile:.1f}s")

    # 保存详细报告
    report_path = os.path.join(output_dir, "test_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "success": success,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告: {report_path}")


if __name__ == "__main__":
    main()
