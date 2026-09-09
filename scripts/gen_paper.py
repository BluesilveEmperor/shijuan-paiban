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


# ── 答题空间配置 ──
ANSWER_SPACE_CONFIG = {
    "compact": {
        "itemsep": "0.5em",
        "vspace": r"\vspace{2em}",
        "student_cmd": r"\answerc",
        "suffix": "-紧凑",
    },
    "normal": {
        "itemsep": "1.5em",
        "vspace": r"\vspace{6em}",
        "student_cmd": r"\answern",
        "suffix": "",
    },
    "exam": {
        "itemsep": None,  # 移除 itemsep，改用分页
        "vspace": r"\newpage",
        "student_cmd": r"\answere",
        "suffix": "-考试",
    },
}


def apply_answer_space(tex_content, start_num, mode):
    """
    应用答题空间设置到 examenv 环境。
    - 替换 itemsep
    - 在每道 item 后插入答题空间命令（学生版）或 vspace（教师版）
    """
    cfg = ANSWER_SPACE_CONFIG[mode]
    # 替换 itemsep
    old = rf"\begin{{examenum}}[start={start_num}, itemsep=2.5cm]"
    if cfg["itemsep"]:
        new = rf"\begin{{examenum}}[start={start_num}, itemsep={cfg['itemsep']}]"
    else:
        new = rf"\begin{{examenum}}[start={start_num}]"
    return tex_content.replace(old, new)


# ── 题目内容感知空间分配 ──

def analyze_question_weight(item_text):
    """
    分析单道题目的空间需求权重。
    返回值越大，表示该题需要越多答题空间。
    """
    weight = 1.0  # 基础权重

    # 子问数量（内层 \item 数量）
    sub_questions = len(re.findall(r'\\item\s', item_text))
    weight += sub_questions * 0.4

    # 含图片
    if '\\includegraphics' in item_text:
        weight += 0.6

    # 文本长度（去除 LaTeX 命令后）
    clean_text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', item_text)
    clean_text = re.sub(r'\\[a-zA-Z]+', '', clean_text)
    clean_text = re.sub(r'[\$\{\}\\]', '', clean_text)
    text_len = len(clean_text.strip())
    if text_len > 200:
        weight += 0.3
    elif text_len > 100:
        weight += 0.15

    # 证明题需要更多空间
    if '证明' in item_text or '证:' in item_text or '证：' in item_text:
        weight += 0.5

    # 应用题/统计题（通常需要更多作答空间）
    if '分布' in item_text or '期望' in item_text or '概率' in item_text:
        weight += 0.3

    # 压轴题（最后一题通常最难）
    if '（17分）' in item_text or '(17分)' in item_text:
        weight += 0.4

    return round(weight, 2)


def analyze_all_questions(tex_content, start_num):
    """
    分析 examenum 环境中所有题目的空间权重。
    返回 [(item_text, weight), ...] 列表。
    """
    start_marker = rf"\begin{{examenum}}[start={start_num}"
    end_marker = r"\end{examenum}"

    start_idx = tex_content.find(start_marker)
    end_idx = tex_content.rfind(end_marker)

    if start_idx == -1 or end_idx == -1:
        return []

    exam_block = tex_content[start_idx:end_idx + len(end_marker)]

    # 用正则按外层 \item 分割（只匹配顶层的 \item，不匹配嵌套内层的）
    # 策略：找到所有顶层的 \item 位置，然后按位置切分
    lines = exam_block.split('\n')

    # 找到所有顶层 \item 的行号
    # 外层 \begin{examenum} 使 depth=1，所以外层 \item 在 depth=1
    # 内层 \begin{examenum} 使 depth=2，内层 \item 在 depth=2
    item_lines = []
    depth = 0
    for i, line in enumerate(lines):
        # 跟踪深度
        if r'\begin{enumerate}' in line or r'\begin{examenum}' in line:
            depth += 1
            continue
        elif r'\end{enumerate}' in line or r'\end{examenum}' in line:
            depth -= 1
            continue
        
        stripped = line.lstrip()
        if stripped.startswith(r'\item ') and depth == 1:
            item_lines.append(i)

    # 按 \item 位置切分
    questions = []
    for i, start_line in enumerate(item_lines):
        if i + 1 < len(item_lines):
            end_line = item_lines[i + 1]
        else:
            # 最后一个 \item 到 \end{examenum}
            # 找到对应的 \end{examenum}
            for j in range(start_line, len(lines)):
                if lines[j].strip() == r'\end{examenum}':
                    end_line = j
                    break
            else:
                end_line = len(lines)
        q_text = '\n'.join(lines[start_line:end_line])
        questions.append(q_text)

    # 分析每道题的权重
    results = []
    for q in questions:
        w = analyze_question_weight(q)
        results.append((q, w))

    return results


def distribute_space(tex_content, start_num, target_pages=4, mode="normal"):
    """
    根据题目内容权重分配答题空间。
    返回修改后的 tex_content。
    """
    questions = analyze_all_questions(tex_content, start_num)
    if not questions:
        return tex_content

    total_weight = sum(w for _, w in questions)
    n = len(questions)

    # 计算每道题的 vspace（按权重比例）
    cfg = ANSWER_SPACE_CONFIG[mode]
    base_vspace = {"compact": 2, "normal": 6, "exam": 0}[mode]  # em

    if mode == "exam":
        # exam 模式：每题一页，不需要 vspace
        return tex_content

    # 总可用 vspace（经验值：每页约 15em 可用于答题空间）
    total_vspace = target_pages * 15  # em

    # 按权重分配
    vspaces = []
    for _, w in questions:
        ratio = w / total_weight
        vspace = round(total_vspace * ratio, 1)
        vspace = max(vspace, 2.0)  # 最小 2em
        vspaces.append(vspace)

    # 替换每道题后的答题空间
    result = tex_content
    for i, (q, w) in enumerate(questions):
        if i < len(questions) - 1:  # 最后一道题不加
            old_vspace = cfg["vspace"]
            new_vspace = rf"\vspace{{{vspaces[i]}em}}"
            # 替换该题后的 vspace
            result = result.replace(old_vspace, new_vspace, 1)

    print(f"[INFO] 空间分配: {n} 题, 总权重 {total_weight:.1f}")
    for i, (q, w) in enumerate(questions):
        score = re.search(r'（(\d+)分）', q)
        score_str = f"{score.group(1)}分" if score else "?"
        print(f"  第{start_num+i}题: {score_str}, 权重 {w:.1f}, 空间 {vspaces[i]:.1f}em")

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
    parser.add_argument('--answer-space', default='normal',
                        choices=['compact', 'normal', 'exam'],
                        help='答题空间模式: compact=紧凑, normal=标准(默认), exam=考试')
    parser.add_argument('--pages', default=None,
                        help='页码范围，如 "1-4" 或 "1,3,5"（用于从合并 PDF 中提取试题部分）')
    parser.add_argument('--source-pdf', default=None,
                        help='源 PDF 路径（与 --pages 配合使用，用于提取指定页）')

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
