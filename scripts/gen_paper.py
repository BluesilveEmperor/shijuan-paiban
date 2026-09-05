#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_paper.py - 周练卷 / 错题卷 变量替换 + 编译脚本

用法:
  python gen_paper.py --type zhoukan --vars vars.json --output week5_math
  python gen_paper.py --type cuoti --vars cuoti_vars.json --output cuoti_chap3
  python gen_paper.py --type zhoukan --vars vars.json --version student
  python gen_paper.py --type zhoukan --vars vars.json --version teacher
  python gen_paper.py --type zhoukan --vars vars.json --version all

vars.json 示例 (zhoukan):
{
    "weekNumber": "第5周",
    "zhoukanDate": "2026-03-15",
    "zhoukanClass": "高三(3)班",
    "zhoukanStudent": "李四",
    "zhoukanMode": "limited",
    "suggestedTime": "40分钟",
    "weekFocus": "导数概念与运算\\\\函数单调性\\\\切线方程",
    "mcqCount": 4,
    "msqCount": 1,
    "blankCount": 2,
    "saqCount": 1
}

vars.json 示例 (cuoti):
{
    "cuotiDate": "2026-03-15",
    "cuotiClass": "高三(3)班",
    "cuotiStudent": "李四",
    "cuotiSubject": "数学",
    "cuotiTitle": "导数章节错题订正",
    "cuotiSource": "第三章 函数与导数 周测"
}
"""

import argparse
import json
import os
import re
import subprocess
import sys


def load_vars(vars_path):
    """从 JSON 文件加载变量"""
    with open(vars_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def replace_vars(template_content, variables):
    """
    替换模板中的 \\providecommand{\\var}{default} 为实际值。
    只替换第一次出现的 \\newcommand{\\var}{default} 或 \\providecommand{\\var}{default}。
    """
    result = template_content
    for var_name, var_value in variables.items():
        # 匹配 \providecommand{var}{default} 或 \renewcommand{var}{value} 或 \newcommand{var}{value}
        # 注意: \renewcommand 是 "re" + "new" + "command"，所以用 (?:provide|renew|new)?
        pattern = re.compile(
            r'\\(?:provide|renew|new)?command\{' + re.escape('\\' + var_name) + r'\}\{[^}]*\}'
        )
        # 使用 \providecommand 而非 \renewcommand
        # 原因：wrapper (student/teacher) 可能已用 \providecommand 预定义了同名命令
        # \providecommand 仅在命令未定义时才生效，避免 "undefined command" 错误
        replacement = '\\providecommand{' + '\\' + var_name + '}{' + str(var_value) + '}'
        result = re.sub(pattern, lambda m, rep=replacement: rep, result, count=1)
    return result


def generate_content(template_path, variables, output_path):
    """读取模板，替换变量，写入输出文件"""
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    filled = replace_vars(template, variables)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(filled)

    print(f"[OK] 内容已生成: {output_path}")


def compile_latex(tex_path, work_dir, passes=2):
    """编译 LaTeX 文件（从 work_dir 目录执行，确保 \\input 相对路径正确）"""
    tex_basename = os.path.basename(tex_path)
    for i in range(passes):
        print(f"[INFO] 编译第 {i+1}/{passes} 遍...")
        result = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', '-output-directory', work_dir, tex_basename],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=work_dir  # 从模板目录执行，确保 \\input 找到同目录文件
        )
        if result.returncode != 0:
            print(f"[WARN] 编译第 {i+1} 遍有警告/错误")
            # 打印错误日志中的关键信息
            log_path = os.path.join(work_dir, os.path.basename(tex_path).replace('.tex', '.log'))
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if 'Error' in line or 'Undefined' in line:
                            print(f"  ! {line.strip()}")

    # 检查 Overfull
    log_path = os.path.join(work_dir, os.path.basename(tex_path).replace('.tex', '.log'))
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            overfull_count = 0
            for line in f:
                if 'Overfull' in line:
                    overfull_count += 1
            if overfull_count > 0:
                print(f"[WARN] 有 {overfull_count} 处 Overfull，可能需要调整")

    pdf_path = os.path.join(work_dir, os.path.basename(tex_path).replace('.tex', '.pdf'))
    if os.path.exists(pdf_path):
        print(f"[OK] PDF 已生成: {pdf_path}")
        return True
    else:
        print(f"[ERROR] PDF 生成失败")
        return False


def clean_aux(work_dir, prefix):
    """清理辅助文件"""
    for ext in ['.aux', '.log', '.out']:
        fpath = os.path.join(work_dir, prefix + ext)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"[OK] 已清理: {fpath}")


def main():
    parser = argparse.ArgumentParser(description='周练卷/错题卷 生成脚本')
    parser.add_argument('--type', required=True, choices=['zhoukan', 'cuoti'],
                        help='试卷类型: zhoukan=周练卷, cuoti=错题卷')
    parser.add_argument('--vars', required=True,
                        help='变量 JSON 文件路径')
    parser.add_argument('--output', required=True,
                        help='输出文件名前缀（不含扩展名）')
    parser.add_argument('--version', default='all',
                        choices=['all', 'student', 'teacher', 'onepage'],
                        help='编译版本 (默认 all)')
    parser.add_argument('--work-dir', default=None,
                        help='工作目录（默认当前目录）')
    parser.add_argument('--templates-dir', default=None,
                        help='模板目录（默认 <work_dir>/templates）')
    parser.add_argument('--no-compile', action='store_true',
                        help='只生成内容，不编译')
    parser.add_argument('--no-clean', action='store_true',
                        help='不清理辅助文件')

    args = parser.parse_args()

    # 确定目录
    work_dir = args.work_dir or os.getcwd()
    templates_dir = args.templates_dir or os.path.join(work_dir, 'templates')

    if not os.path.isdir(templates_dir):
        print(f"[ERROR] 模板目录不存在: {templates_dir}")
        sys.exit(1)

    # 加载变量
    variables = load_vars(args.vars)
    print(f"[INFO] 已加载 {len(variables)} 个变量")

    # 确定要编译的版本
    if args.type == 'zhoukan':
        versions = ['student', 'teacher', 'onepage'] if args.version == 'all' else [args.version]
        prefix = 'zhoukan'
    elif args.type == 'cuoti':
        versions = ['student', 'teacher'] if args.version == 'all' else [args.version]
        prefix = 'cuoti'
    else:
        print(f"[ERROR] 未知类型: {args.type}")
        sys.exit(1)

    # 步骤 1: 替换变量到 content 模板
    content_template = os.path.join(templates_dir, f'{prefix}_content.tex')
    if not os.path.exists(content_template):
        print(f"[ERROR] 内容模板不存在: {content_template}")
        sys.exit(1)

    # 输出到工作目录（与模板同目录，因为 wrapper 用相对路径 \input）
    content_output = os.path.join(templates_dir, f'{prefix}_content_filled.tex')

    # 备份原始 content 文件
    backup_path = content_template + '.bak'
    if not os.path.exists(backup_path):
        with open(content_template, 'r', encoding='utf-8') as f:
            original = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original)
        print(f"[OK] 已备份原始模板: {backup_path}")

    # 生成填充后的 content
    generate_content(content_template, variables, content_template)
    print(f"[INFO] 变量已注入到: {content_template}")

    if args.no_compile:
        print("[INFO] 跳过编译（--no-compile）")
        return

    # 步骤 2: 编译各版本
    success = []
    for ver in versions:
        tex_file = os.path.join(templates_dir, f'{prefix}_{ver}.tex')
        if not os.path.exists(tex_file):
            print(f"[WARN] 版本模板不存在，跳过: {tex_file}")
            continue

        print(f"\n{'='*50}")
        print(f"[INFO] 编译 {prefix}_{ver}.tex ...")
        print(f"{'='*50}")

        if compile_latex(tex_file, templates_dir):
            # 复制 PDF 到输出目录
            src_pdf = os.path.join(templates_dir, f'{prefix}_{ver}.pdf')
            dst_pdf = os.path.join(work_dir, f'{args.output}_{ver}.pdf')
            if os.path.exists(src_pdf):
                import shutil
                shutil.copy2(src_pdf, dst_pdf)
                print(f"[OK] 输出: {dst_pdf}")
                success.append(ver)

        # 清理辅助文件
        if not args.no_clean:
            clean_aux(templates_dir, f'{prefix}_{ver}')

    # 步骤 3: 恢复原始 content 模板
    if os.path.exists(backup_path):
        with open(backup_path, 'r', encoding='utf-8') as f:
            original = f.read()
        with open(content_template, 'w', encoding='utf-8') as f:
            f.write(original)
        os.remove(backup_path)
        print(f"\n[OK] 已恢复原始模板: {content_template}")

    # 总结
    print(f"\n{'='*50}")
    print(f"[DONE] 生成完成！成功编译 {len(success)}/{len(versions)} 个版本")
    if success:
        print(f"[DONE] 输出文件:")
        for ver in success:
            print(f"  - {os.path.join(work_dir, f'{args.output}_{ver}.pdf')}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
