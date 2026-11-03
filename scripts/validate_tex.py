#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_tex.py - LaTeX 试卷结构验证器（规则 ID 驱动）

只验证不修改，输出 JSON 报告。每条问题都带 rule_id，可直接对应到
rules/layout.yaml 中的规则，供 scripts/evolve.py 做失败归因。

用法:
  python scripts/validate_tex.py <tex文件> [--expected-pages 4] [--is-answer] [--output report.json]

退出码:
  0  通过（无 error）
  1  存在 error
  2  文件不存在
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

# ── 检查注册表：check 名 → 实现函数 ──────────────────────────────
# rules/layout.yaml 中 rule.check 引用的名字必须出现在这里，
# scripts/gen_rules_doc.py 会做交叉校验。
CHECKS: Dict[str, Any] = {}


def check(name):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


LIST_ENVS = {"enumerate", "examenum", "itemize", "description"}
ANSWER_SPACE_CMDS = ("\\answern",)
IMAGE_RE = re.compile(r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]*)\}")
WIDTH_RE = re.compile(r"width\s*=\s*([\d.]+)\s*\\(?:textwidth|linewidth)")
HEIGHT_RE = re.compile(r"height\s*=\s*[\d.]+\s*(?:cm|mm|in|em|pt)")
BEGIN_RE = re.compile(r"\\begin\{(\w+)\}")
END_RE = re.compile(r"\\end\{(\w+)\}")
TASKS_BEGIN_RE = re.compile(r"\\begin\{tasks\}(?:\((\d+)\))?")


class TexValidator:
    def __init__(self, tex_path: str, expected_pages: int = None,
                 is_answer: bool = False):
        self.tex_path = Path(tex_path)
        self.expected_pages = expected_pages
        self.is_answer = is_answer
        self.content = self.tex_path.read_text(encoding="utf-8")
        self.lines = self.content.split("\n")
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []

    # ── 结果收集 ──
    def _add(self, bucket, rule_id, check_name, message,
             line_no=None, suggestion=None):
        item = {"rule_id": rule_id, "check": check_name, "message": message}
        if line_no:
            item["line"] = line_no
        if suggestion:
            item["suggestion"] = suggestion
        bucket.append(item)

    def error(self, rule_id, check_name, message, line_no=None, suggestion=None):
        self._add(self.errors, rule_id, check_name, message, line_no, suggestion)

    def warn(self, rule_id, check_name, message, line_no=None, suggestion=None):
        self._add(self.warnings, rule_id, check_name, message, line_no, suggestion)

    # ── 通用工具 ──
    def _env_stack_at(self, upto_line: int):
        """返回第 upto_line 行（0-based，不含）之前的环境栈。"""
        stack = []
        for i in range(min(upto_line, len(self.lines))):
            line = self.lines[i]
            for m in BEGIN_RE.finditer(line):
                stack.append((m.group(1), i + 1))
            for m in END_RE.finditer(line):
                env = m.group(1)
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][0] == env:
                        del stack[k:]
                        break
        return stack

    def _list_depth(self, stack):
        return sum(1 for e, _ in stack if e in LIST_ENVS)

    def _pdf_page_count(self):
        pdf = self.tex_path.with_suffix(".pdf")
        if not pdf.exists() or not shutil.which("pdfinfo"):
            return None
        try:
            out = subprocess.run(
                ["pdfinfo", str(pdf)], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            ).stdout or ""
            m = re.search(r"^Pages:\s+(\d+)", out, re.M)
            return int(m.group(1)) if m else None
        except Exception:
            return None

    # ══════════════════════ 检查实现 ══════════════════════

    @check("begin_end_balance")
    def _check_begin_end_balance(self):
        stack = []
        for i, line in enumerate(self.lines, 1):
            for m in BEGIN_RE.finditer(line):
                if m.group(1) != "document":
                    stack.append((m.group(1), i))
            for m in END_RE.finditer(line):
                env = m.group(1)
                if env == "document":
                    continue
                if stack and stack[-1][0] == env:
                    stack.pop()
                else:
                    self.error(
                        "STRUCT-ENV-001", "begin_end_balance",
                        f"\\end{{{env}}} 没有匹配的 \\begin",
                        line_no=i,
                        suggestion=f"检查遗漏的 \\begin{{{env}}} 或多余的 \\end{{{env}}}",
                    )
        for env, line_no in stack:
            self.error(
                "STRUCT-ENV-001", "begin_end_balance",
                f"\\begin{{{env}}} 没有匹配的 \\end{{{env}}}",
                line_no=line_no,
                suggestion=f"在文件末尾添加 \\end{{{env}}}",
            )

    @check("env_nesting")
    def _check_env_nesting(self):
        """tasks 必须嵌在列表环境内；解答题应用 examenum。"""
        for i, line in enumerate(self.lines):
            if "\\begin{tasks}" not in line:
                continue
            stack = self._env_stack_at(i)
            if self._list_depth(stack) == 0:
                self.error(
                    "STRUCT-ENV-001", "env_nesting",
                    "tasks 环境不在任何题目列表内（题目会失去编号）",
                    line_no=i + 1,
                    suggestion="外层用 enumerate，tasks 只作为选项容器",
                )

        if not self.is_answer and "\\begin{examenum}" not in self.content:
            if re.search(r"解答题", self.content):
                self.warn(
                    "STRUCT-ENV-002", "env_nesting",
                    "存在解答题标题但未使用 examenum 环境",
                    suggestion="解答题应使用 examenum，start = 单选数+多选数+填空数+1",
                )

    @check("fill_blank_marker")
    def _check_fill_blank(self):
        for i, line in enumerate(self.lines, 1):
            if re.search(r"\\underline\{\\hspace", line) and "newcommand" not in line:
                self.warn(
                    "STRUCT-BLANK-001", "fill_blank_marker",
                    "直接使用 \\underline{\\hspace} 造空位",
                    line_no=i,
                    suggestion="改用模板定义的 \\blank，保证全卷空位宽度一致",
                )

    @check("circled_glyph")
    def _check_circled_glyph(self):
        """①②③ 等圈号在默认中文字体下缺字形，会静默丢字。"""
        circled = re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩]", self.content)
        if not circled:
            return
        mapped = ("newunicodechar" in self.content
                  and "\\newunicodechar{①}" in self.content)
        if mapped:
            return
        self.warn(
            "STRUCT-GLYPH-001", "circled_glyph",
            f"正文含 {len(circled)} 个圈号字符（①②③…），但导言区未做字形映射——会静默丢字",
            suggestion="导言区添加 \\usepackage{newunicodechar} 并把 ①-⑩ 映射到 \\mycircled",
        )

    @check("image_max_width")
    def _check_image_max_width(self):
        for i, line in enumerate(self.lines, 1):
            for m in IMAGE_RE.finditer(line):
                opts = m.group(1) or ""
                wm = WIDTH_RE.search(opts)
                if not wm:
                    continue
                width = float(wm.group(1))
                if width > 0.35:
                    self.error(
                        "IMG-W-001", "image_max_width",
                        f"图片宽度 {width}\\textwidth 超过硬上限 0.35",
                        line_no=i,
                        suggestion="降到 0.30~0.35；并排图请用 minipage 分配宽度",
                    )

    @check("multi_image_height")
    def _check_multi_image_height(self):
        """figure 环境内 ≥2 张图时必须限高。"""
        for i, line in enumerate(self.lines):
            if not re.match(r"\s*\\begin\{figure\}", line):
                continue
            block, j = [], i
            while j < len(self.lines):
                block.append(self.lines[j])
                if "\\end{figure}" in self.lines[j]:
                    break
                j += 1
            body = "\n".join(block)
            images = IMAGE_RE.findall(body)
            if len(images) >= 2:
                missing = [m for m in images if not HEIGHT_RE.search(m[0] or "")]
                if missing:
                    self.error(
                        "IMG-W-003", "multi_image_height",
                        f"figure 内 {len(images)} 张并排图片中有 {len(missing)} 张未限高",
                        line_no=i + 1,
                        suggestion="加 height=3cm（2 张）或 height=2.5cm（3 张）+ keepaspectratio",
                    )

    @check("image_align")
    def _check_image_align(self):
        for i, line in enumerate(self.lines, 1):
            if "\\raggedleft" in line:
                self.error(
                    "IMG-ALIGN-001", "image_align",
                    "使用了 \\raggedleft（图注会与图片左边缘错位）",
                    line_no=i,
                    suggestion="改用 \\centering",
                )

    @check("wrapfigure_in_list")
    def _check_wrapfigure_in_list(self):
        for i, line in enumerate(self.lines):
            if "\\begin{wrapfigure}" not in line:
                continue
            stack = self._env_stack_at(i)
            if self._list_depth(stack) > 0:
                self.error(
                    "IMG-SCENE-001", "wrapfigure_in_list",
                    "wrapfigure 在列表环境内使用（会静默失效，图片跑到页首）",
                    line_no=i + 1,
                    suggestion="列表内改用 minipage 左右并排；或把 wrapfigure 移到 \\item 之前",
                )

    @check("tasks_cols")
    def _check_tasks_cols(self):
        for i, line in enumerate(self.lines, 1):
            m = TASKS_BEGIN_RE.search(line)
            if not m:
                continue
            cols = int(m.group(1)) if m.group(1) else 1
            if cols not in (1, 2, 3, 4):
                self.warn(
                    "TASKS-COL-001", "tasks_cols",
                    f"tasks 列数 {cols} 非常规",
                    line_no=i,
                    suggestion="使用 2 或 4 列",
                )

    @check("tasks_single_col_image")
    def _check_tasks_single_col_image(self):
        for i, line in enumerate(self.lines):
            m = TASKS_BEGIN_RE.search(line)
            if not m or (m.group(1) and m.group(1) != "1"):
                continue
            block, j = [], i
            while j < len(self.lines) and j < i + 30:
                block.append(self.lines[j])
                if "\\end{tasks}" in self.lines[j]:
                    break
                j += 1
            if "\\includegraphics" in "\n".join(block):
                self.error(
                    "TASKS-COL-002", "tasks_single_col_image",
                    "图片选项使用 tasks(1) 竖排",
                    line_no=i + 1,
                    suggestion="改用 tasks(4)（图宽 0.12\\textwidth）或 tasks(2)",
                )

    @check("examenum_start")
    def _check_examenum_start(self):
        """顶层列表的 start 值必须等于此前累计题数 + 1。"""
        if self.is_answer:
            return
        stack, counted = [], 0
        for i, line in enumerate(self.lines):
            depth_before = self._list_depth(stack)

            for m in BEGIN_RE.finditer(line):
                env = m.group(1)
                if env in LIST_ENVS:
                    if depth_before == 0:
                        sm = re.search(r"\[([^\]]*)\]", line)
                        opts = sm.group(1) if sm else ""
                        st = re.search(r"start\s*=\s*(\d+)", opts)
                        if st and "resume" not in opts:
                            expected = counted + 1
                            actual = int(st.group(1))
                            if actual != expected:
                                self.error(
                                    "ENUM-START-001", "examenum_start",
                                    f"列表起始编号 start={actual}，按前面题量应为 {expected}",
                                    line_no=i + 1,
                                    suggestion="start = 单选题数 + 多选题数 + 填空题数 + 1",
                                )
                            counted = expected - 1
                    stack.append((env, i + 1))
                else:
                    stack.append((env, i + 1))

            if self._list_depth(stack) == 1 and re.search(r"(?<!\\)\\item\b", line):
                counted += len(re.findall(r"(?<!\\)\\item\b", line))

            for m in END_RE.finditer(line):
                env = m.group(1)
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][0] == env:
                        del stack[k:]
                        break

    @check("answer_resume")
    def _check_answer_resume(self):
        """答案文档：只有顶层 enumerate 需要衔接编号，嵌套子问不参与。"""
        if not self.is_answer:
            return
        stack = []
        seen = 0
        for i, line in enumerate(self.lines):
            depth_before = self._list_depth(stack)
            for m in BEGIN_RE.finditer(line):
                env = m.group(1)
                if env == "enumerate" and depth_before == 0:
                    seen += 1
                    has_resume = "resume" in line
                    if seen == 1 and has_resume:
                        self.warn(
                            "ENUM-RESUME-001", "answer_resume",
                            "答案文档第一个 enumerate 不应带 [resume]",
                            line_no=i + 1,
                            suggestion="首个列表直接 \\begin{enumerate}",
                        )
                    elif seen > 1 and not has_resume:
                        self.error(
                            "ENUM-RESUME-001", "answer_resume",
                            f"答案文档第 {seen} 个顶层 enumerate 缺少 [resume]（编号会从 1 重新开始）",
                            line_no=i + 1,
                            suggestion="后续列表统一使用 \\begin{enumerate}[resume]",
                        )
                stack.append((env, i + 1))
            for m in END_RE.finditer(line):
                env = m.group(1)
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][0] == env:
                        del stack[k:]
                        break

    @check("page_count")
    def _check_page_count(self):
        if self.expected_pages is None or self.is_answer:
            return
        pages = self._pdf_page_count()
        if pages is None:
            self.info.append({
                "check": "page_count",
                "message": "未找到同名 PDF 或 pdfinfo 不可用，跳过页数检查",
            })
            return
        if pages != self.expected_pages:
            self.error(
                "PAGE-001", "page_count",
                f"实际 {pages} 页，期望 {self.expected_pages} 页",
                suggestion="优先调 itemsep；仍超页再加 \\linespread{1.05}\\selectfont",
            )
        else:
            self.info.append({
                "check": "page_count",
                "message": f"页数 {pages} 符合期望",
            })

    @check("answer_space")
    def _check_answer_space(self):
        if self.is_answer:
            return
        total = sum(self.content.count(c) for c in ANSWER_SPACE_CMDS)
        long_answer = len(re.findall(r"\\begin\{examenum\}\[start", self.content))
        if long_answer and total == 0:
            self.warn(
                "ANS-001", "answer_space",
                "解答题未插入任何答题空间命令",
                suggestion="插入 \\answern",
            )
        self.info.append({
            "check": "answer_space",
            "message": f"答题空间命令出现 {total} 次",
        })

    @check("answer_space_last")
    def _check_answer_space_last(self):
        if self.is_answer:
            return
        # 最后一个顶层 examenum 的最后一个 item 后不应有答题空间
        idx = self.content.rfind("\\end{examenum}")
        if idx < 0:
            return
        tail = self.content[max(0, idx - 400): idx]
        for cmd in ANSWER_SPACE_CMDS:
            if cmd in tail:
                after = tail.split(cmd)[-1]
                if "\\item" not in after:
                    self.warn(
                        "ANS-002", "answer_space_last",
                        "最后一道解答题后插入了答题空间（页尾会留大片空白）",
                        suggestion="最后一道解答题后不插入答题空间",
                    )
                break

    @check("answer_space_lines")
    def _check_answer_space_lines(self):
        if self.is_answer:
            return
        for i, line in enumerate(self.lines, 1):
            if "\\answern" in line:
                continue
            if re.search(r"\\(rule|fbox)\b", line) and "newcommand" not in line:
                self.warn(
                    "ANS-003", "answer_space_lines",
                    "答题区域出现线条类命令",
                    line_no=i,
                    suggestion="答题空间只允许 \\vspace 留白，禁止 \\rule / \\fbox / tcolorbox",
                )

    @check("graphicspath_match")
    def _check_graphicspath_match(self):
        gp_dirs = []
        m = re.search(r"\\graphicspath\{((?:\{[^}]*\})+)\}", self.content)
        if m:
            gp_dirs = re.findall(r"\{([^}]*)\}", m.group(1))
        if self.is_answer and not gp_dirs:
            self.error(
                "EXTRACT-001", "graphicspath_match",
                "答案文档缺少 \\graphicspath",
                suggestion="添加 \\graphicspath{{Images-<文件名>/}}",
            )
            return

        tex_dir = self.tex_path.parent
        for i, line in enumerate(self.lines, 1):
            # 跳过宏定义（\newcommand{\eqimg}[2][0.5]{...\includegraphics{#2}} 里的 #2 不是文件名）
            if "\\newcommand" in line or "#1" in line or "#2" in line:
                continue
            for m2 in IMAGE_RE.finditer(line):
                name = m2.group(2).strip()
                if not name or name.startswith(("http", "/", "#")):
                    continue
                candidates = [tex_dir / d.strip("/") / name for d in gp_dirs]
                candidates.append(tex_dir / name)
                if not any(c.exists() for c in candidates):
                    self.error(
                        "EXTRACT-001", "graphicspath_match",
                        f"图片不存在: {name}",
                        line_no=i,
                        suggestion="确认图片目录名与 \\graphicspath 一致",
                    )

    @check("no_wmf_remaining")
    def _check_no_wmf(self):
        for i, line in enumerate(self.lines, 1):
            if ".wmf" in line.lower():
                self.error(
                    "EXTRACT-003", "no_wmf_remaining",
                    "仍有 WMF 图片引用（xelatex 不支持）",
                    line_no=i,
                    suggestion="用 Pillow 批量转 PNG（600 DPI）",
                )

    @check("required_packages")
    def _check_required_packages(self):
        required = (
            ["amsmath", "graphicx", "enumitem", "fancyhdr", "xcolor"]
            if self.is_answer
            else ["amsmath", "graphicx", "tasks", "enumitem", "fancyhdr"]
        )
        for pkg in required:
            if not re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*" + re.escape(pkg), self.content):
                self.warn(
                    "STRUCT-ENV-001", "required_packages",
                    f"缺少宏包 {pkg}",
                    suggestion=f"导言区添加 \\usepackage{{{pkg}}}",
                )

    @check("dollar_balance")
    def _check_dollar_balance(self):
        clean = "\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in self.lines)
        n = len(re.findall(r"(?<!\\)\$", clean))
        if n % 2:
            self.error(
                "STRUCT-BLANK-001", "dollar_balance",
                f"$ 数量为奇数（{n}），存在未配对的行内公式",
                suggestion="检查遗漏的 $ 或未转义的 \\$",
            )

    # ══════════════════════ 主流程 ══════════════════════

    def validate(self) -> Dict[str, Any]:
        for name, fn in CHECKS.items():
            try:
                fn(self)
            except Exception as exc:  # 单个检查异常不应中断整体验证
                self.info.append({
                    "check": name,
                    "message": f"检查执行异常，已跳过: {exc}",
                })

        hit_rules = sorted({e["rule_id"] for e in self.errors + self.warnings})
        return {
            "file": str(self.tex_path),
            "passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "rule_ids": hit_rules,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


# 供 gen_rules_doc.py 交叉校验 rules/layout.yaml 的 check 字段
RULE_CHECKS = set(CHECKS)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="LaTeX 试卷结构验证")
    ap.add_argument("tex_file", help="要验证的 .tex 文件")
    ap.add_argument("--expected-pages", type=int, default=None, help="期望页数")
    ap.add_argument("--is-answer", action="store_true", help="是否为答案文档")
    ap.add_argument("--output", "-o", default=None, help="输出 JSON 文件路径")
    ap.add_argument("--quiet", "-q", action="store_true", help="只输出摘要")
    args = ap.parse_args()

    if not Path(args.tex_file).exists():
        print(json.dumps({"error": f"文件不存在: {args.tex_file}"}, ensure_ascii=False))
        sys.exit(2)

    report = TexValidator(
        args.tex_file,
        expected_pages=args.expected_pages,
        is_answer=args.is_answer,
    ).validate()

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.quiet:
        print(f"{report['file']}: {'PASS' if report['passed'] else 'FAIL'} "
              f"({report['error_count']} error, {report['warning_count']} warning)")
        for e in report["errors"]:
            print(f"  [{e['rule_id']}] {e['message']}")
    else:
        print(payload)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")

    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
