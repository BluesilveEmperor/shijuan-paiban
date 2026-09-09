#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_tex.py - LaTeX 试卷结构验证脚本

只验证不修改，输出 JSON 报告供 LLM 决定是否需要重新生成。
替代原来的 fix_tex.py / fix_pages.py 等事后修补脚本。

用法:
  python scripts/validate_tex.py <tex文件> [--expected-pages 4] [--is-answer]

输出:
  JSON 格式的验证报告，包含 pass/fail 状态和具体问题列表
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


class TexValidator:
    """LaTeX 试卷结构验证器"""

    def __init__(self, tex_path: str, expected_pages: int = None, is_answer: bool = False):
        self.tex_path = Path(tex_path)
        self.expected_pages = expected_pages
        self.is_answer = is_answer
        self.content = self.tex_path.read_text(encoding='utf-8')
        self.lines = self.content.split('\n')
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []

    def validate(self) -> Dict[str, Any]:
        """运行所有验证检查，返回报告"""
        self._check_begin_end_balance()
        self._check_enumeration_sequence()
        self._check_graphics_references()
        self._check_dollar_balance()
        self._check_required_packages()
        self._check_page_control()
        self._check_image_placement()
        self._check_template_consistency()

        if self.is_answer:
            self._check_answer_structure()

        passed = len(self.errors) == 0
        return {
            "file": str(self.tex_path),
            "passed": passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }

    def _add_error(self, check: str, message: str, line_no: int = None, suggestion: str = None):
        err = {"check": check, "message": message}
        if line_no:
            err["line"] = line_no
        if suggestion:
            err["suggestion"] = suggestion
        self.errors.append(err)

    def _add_warning(self, check: str, message: str, line_no: int = None, suggestion: str = None):
        warn = {"check": check, "message": message}
        if line_no:
            warn["line"] = line_no
        if suggestion:
            warn["suggestion"] = suggestion
        self.warnings.append(warn)

    def _check_begin_end_balance(self):
        """检查 begin/end 环境是否配对"""
        begin_pattern = re.compile(r'\\begin\{(\w+)\}')
        end_pattern = re.compile(r'\\end\{(\w+)\}')

        # 不需要配对的環境
        skip_envs = {'document'}

        stack = []
        for i, line in enumerate(self.lines, 1):
            for m in begin_pattern.finditer(line):
                env = m.group(1)
                if env not in skip_envs:
                    stack.append((env, i))
            for m in end_pattern.finditer(line):
                env = m.group(1)
                if env in skip_envs:
                    continue
                if stack and stack[-1][0] == env:
                    stack.pop()
                else:
                    self._add_error(
                        "begin_end_balance",
                        f"\\end{{{env}}} 没有匹配的 \\begin",
                        line_no=i,
                        suggestion=f"检查是否有遗漏的 \\begin{{{env}}} 或多余的 \\end{{{env}}}"
                    )

        for env, line_no in stack:
            self._add_error(
                "begin_end_balance",
                f"\\begin{{{env}}} 没有匹配的 \\end{{{env}}}",
                line_no=line_no,
                suggestion=f"在文件末尾添加 \\end{{{env}}}"
            )

    def _check_enumeration_sequence(self):
        """检查题目编号连续性"""
        # 提取所有 \item 的编号上下文
        enum_starts = []
        for i, line in enumerate(self.lines, 1):
            # 匹配 \begin{enumerate}[start=N]
            m = re.search(r'\\begin\{enumerate\}\[start=(\d+)', line)
            if m:
                enum_starts.append((i, int(m.group(1))))

        # 检查是否有嵌套的 examenum 环境
        examenum_starts = []
        for i, line in enumerate(self.lines, 1):
            m = re.search(r'\\begin\{examenum\}\[start=(\d+)', line)
            if m:
                examenum_starts.append((i, int(m.group(1)), line))

        # 验证 examenum 的 start 值
        for line_no, start_val, line_content in examenum_starts:
            # 检查是否有 itemsep=2.5cm（学生版应该有，教师版应该没有）
            if not self.is_answer:
                if 'itemsep' not in line_content:
                    self._add_warning(
                        "enumeration_sequence",
                        f"解答题 examenum 缺少 itemsep 设置",
                        line_no=line_no,
                        suggestion="学生版应包含 itemsep=2.5cm，教师版应移除"
                    )

    def _check_graphics_references(self):
        """检查图片引用是否存在"""
        # 提取 \graphicspath
        graphicspath_dirs = ['images']  # 默认
        for line in self.lines:
            m = re.search(r'\\graphicspath\{\{([^}]+)\}\}', line)
            if m:
                graphicspath_dirs = [d.strip() for d in m.group(1).split(',')]

        # 提取所有 \includegraphics 引用
        for i, line in enumerate(self.lines, 1):
            for m in re.finditer(r'\\includegraphics(?:\[[^\]]*\]?)\{([^}]+)\}', line):
                img_name = m.group(1)
                # 跳过 URL 和绝对路径
                if img_name.startswith(('http', '/')):
                    continue

                # 检查图片文件是否存在
                found = False
                for gp_dir in graphicspath_dirs:
                    gp_dir = gp_dir.strip('/')
                    # 相对于 tex 文件目录检查
                    tex_dir = self.tex_path.parent
                    candidate = tex_dir / gp_dir / img_name
                    if candidate.exists():
                        found = True
                        break
                    # 也检查不带 graphicspath 的相对路径
                    candidate2 = tex_dir / img_name
                    if candidate2.exists():
                        found = True
                        break

                if not found:
                    self._add_warning(
                        "graphics_references",
                        f"图片文件可能不存在: {img_name}",
                        line_no=i,
                        suggestion=f"确认 {img_name} 已提取到正确目录"
                    )

    def _check_dollar_balance(self):
        """检查美元符号配对（简单检查）"""
        # 移除注释行
        clean_lines = []
        for line in self.lines:
            # 移除行内注释（非转义的 %）
            cleaned = re.sub(r'(?<!\\)%.*$', '', line)
            clean_lines.append(cleaned)

        full_text = '\n'.join(clean_lines)

        # 统计非转义的 $ 数量
        dollar_count = len(re.findall(r'(?<!\\)\$', full_text))

        if dollar_count % 2 != 0:
            self._add_error(
                "dollar_balance",
                f"美元符号 $ 数量为奇数 ({dollar_count})，存在未配对的行内公式",
                suggestion="检查是否有遗漏的 $ 或转义字符 \\$"
            )

    def _check_required_packages(self):
        """检查必需宏包是否加载"""
        required_packages = {
            'gaokao': ['amsmath', 'graphicx', 'tasks', 'enumitem', 'fancyhdr'],
            'answer': ['amsmath', 'graphicx', 'enumitem', 'fancyhdr', 'xcolor'],
        }

        pkg_key = 'answer' if self.is_answer else 'gaokao'
        for pkg in required_packages.get(pkg_key, []):
            if f'\\usepackage' not in self.content or pkg not in self.content:
                # 更精确的检查
                if not re.search(r'\\usepackage(?:\[[^\]]*\])?\{[^}]*' + pkg, self.content):
                    self._add_warning(
                        "required_packages",
                        f"可能缺少宏包: {pkg}",
                        suggestion=f"在导言区添加 \\usepackage{{{pkg}}}"
                    )

    def _check_page_control(self):
        """检查页数控制相关设置"""
        if self.is_answer:
            return  # 答案文档不受页数限制

        # 检查是否有 geometry 设置
        if 'geometry' not in self.content and '\\geometry{' not in self.content:
            self._add_error(
                "page_control",
                "缺少页面几何设置 (geometry)",
                suggestion="添加 \\usepackage[a4paper, margin=2.5cm]{geometry}"
            )

        # 检查是否有重复的 geometry
        geometry_count = self.content.count('\\geometry{')
        if geometry_count > 1:
            self._add_error(
                "page_control",
                f"存在 {geometry_count} 个 \\geometry 命令，应只有一个",
                suggestion="合并为一个 \\geometry 命令"
            )

    def _check_image_placement(self):
        """检查图片放置方式是否正确"""
        for i, line in enumerate(self.lines, 1):
            if '\\includegraphics' not in line:
                continue

            # 获取上下文（前后5行）
            context_start = max(0, i - 6)
            context_end = min(len(self.lines), i + 5)
            context = '\n'.join(self.lines[context_start:context_end])

            # 检查是否在 wrapfigure 中
            in_wrapfigure = 'wrapfigure' in context
            # 检查是否在 minipage 中
            in_minipage = 'minipage' in context
            # 检查是否在 figure[H] 中
            in_figure = 'figure' in context

            # 检查是否在 enumerate/examenum 中（简单检测）
            in_list = False
            for j in range(max(0, i - 10), i):
                if re.search(r'\\begin\{(enumerate|examenum)\}', self.lines[j]):
                    in_list = True
                if re.search(r'\\end\{(enumerate|examenum)\}', self.lines[j]):
                    in_list = False

            # 如果在列表环境中且使用了 wrapfigure，警告
            if in_list and in_wrapfigure:
                self._add_error(
                    "image_placement",
                    "列表环境中使用了 wrapfigure（会失效）",
                    line_no=i,
                    suggestion="改用 minipage 左右并排方案"
                )

            # 如果不在任何浮动环境中，警告
            if not in_wrapfigure and not in_minipage and not in_figure:
                self._add_warning(
                    "image_placement",
                    "图片不在浮动环境中，可能位置不稳定",
                    line_no=i,
                    suggestion="使用 wrapfigure（列表外）或 minipage（列表内）"
                )

    def _check_template_consistency(self):
        """检查与模板一致性"""
        if self.is_answer:
            # 答案文档检查
            if '\\daan' not in self.content:
                self._add_warning(
                    "template_consistency",
                    "答案文档中未使用 \\daan 命令",
                    suggestion="答案应使用 \\daan{...} 标记"
                )
            if '\\graphicspath' not in self.content:
                self._add_error(
                    "template_consistency",
                    "答案文档缺少 \\graphicspath 设置",
                    suggestion="添加 \\graphicspath{{{图片目录}/}}"
                )
        else:
            # 试题文档检查
            if '\\blank' in self.content:
                # 检查是否有填空题环境
                if 'enumerate' not in self.content:
                    self._add_warning(
                        "template_consistency",
                        "使用了 \\blank 但没有 enumerate 环境",
                        suggestion="填空题应在 enumerate 环境中"
                    )

    def _check_answer_structure(self):
        """检查答案文档结构"""
        # 检查答案块结构
        has_daan = '\\daan' in self.content
        has_jieti = '\\jieti' in self.content
        has_xijie = '\\xijie' in self.content

        if not has_daan:
            self._add_error("answer_structure", "答案文档缺少 \\daan 命令")
        if not has_jieti:
            self._add_warning("answer_structure", "答案文档缺少 \\jieti 命令")
        if not has_xijie:
            self._add_warning("answer_structure", "答案文档缺少 \\xijie 命令")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='LaTeX 试卷结构验证')
    parser.add_argument('tex_file', help='要验证的 .tex 文件')
    parser.add_argument('--expected-pages', type=int, default=None, help='期望页数')
    parser.add_argument('--is-answer', action='store_true', help='是否为答案文档')
    parser.add_argument('--output', '-o', default=None, help='输出 JSON 文件路径')
    args = parser.parse_args()

    if not Path(args.tex_file).exists():
        print(json.dumps({"error": f"文件不存在: {args.tex_file}"}, ensure_ascii=False))
        sys.exit(1)

    validator = TexValidator(
        args.tex_file,
        expected_pages=args.expected_pages,
        is_answer=args.is_answer
    )
    report = validator.validate()

    # 输出 JSON
    json_output = json.dumps(report, ensure_ascii=False, indent=2)
    print(json_output)

    if args.output:
        Path(args.output).write_text(json_output, encoding='utf-8')

    # 返回码：0=通过，1=有错误
    sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
