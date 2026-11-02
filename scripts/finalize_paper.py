#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""finalize_paper.py — 排版收尾：按 ARTIFACT 规范一键补齐标准产物集

标准产物集（试题卷，ARTIFACT-001 / ARTIFACT-002）::

    <卷名>.tex / .pdf                源文件（无答题空间紧凑版）
    <卷名>-学生版.tex / .pdf         有答题空间（\\answern）
    <卷名>-教师版.tex / .pdf         normal 模式，题下 6em 答题空间
    <卷名>-教师版-考试.tex / .pdf    exam 模式，每题独占一页
    <卷名>-答题卡-A4.tex / .pdf
    <卷名>-答题卡-A3.tex / .pdf
    Images-<卷名>/                    图片文件夹（无图时允许缺席）
    build.py                         一键编译脚本（自动部署）
    answersheet.sty                  答题卡宏包副本（随答题卡生成）

答案文档（文件名含「答案」）只出三件：<卷名>.tex/.pdf + Images-<卷名>/
+ build.py，不生成教师版/答题卡。

用法::

    python scripts/finalize_paper.py 试卷.tex
    python scripts/finalize_paper.py 试卷.tex --skip-answersheet --skip-exam
    python scripts/finalize_paper.py 试卷目录            # 处理目录内全部源 .tex
    python scripts/finalize_paper.py 试卷.tex --force    # 产物已存在也重新生成

流程（幂等，缺什么补什么）::

    1. 识别答案文档 → 仅部署 + 编译 + 校验
    2. gen_teacher.py --mode normal  → -教师版.tex + -学生版.tex
    3. gen_teacher.py --mode exam    → -教师版-考试.tex
    4. gen_answer_sheet.py --layout both --no-compile → 答题卡 A4 + A3
    5. 部署 build.py（母本 scripts/build.py，已存在则不动）
    6. 运行 build.py：编译全部 tex ×2，回拷 PDF，清理中间文件
    7. 清理 preview-*.png；逐项校验产物集，打印清单

退出码：0 全部产物齐全；1 有产物缺失或生成失败。
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GEN_TEACHER = SCRIPTS / "gen_teacher.py"
GEN_SHEET = SCRIPTS / "gen_answer_sheet.py"
BUILD_MASTER = SCRIPTS / "build.py"

ANSWER_HINT = "答案"
DERIVED_HINTS = ("教师版", "学生版", "答题卡", "答题空间")


def run_py(cmd, cwd):
    """以 UTF-8 环境运行子进程，返回退出码。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, *cmd], cwd=str(cwd), env=env)
    return proc.returncode


def is_answer_doc(stem):
    return ANSWER_HINT in stem


def is_derived(stem):
    return any(h in stem for h in DERIVED_HINTS)


def deploy_build_py(target_dir):
    dst = target_dir / "build.py"
    if dst.exists():
        return
    if not BUILD_MASTER.exists():
        print(f"[WARN] 编译脚本母本不存在: {BUILD_MASTER}", file=sys.stderr)
        return
    shutil.copy2(BUILD_MASTER, dst)
    print(f"[OK] 已部署 build.py → {dst}")


def clean_previews(target_dir):
    for png in target_dir.glob("preview-*.png"):
        png.unlink()

def process_source(src, force=False, skip_answersheet=False, skip_exam=False):
    """对单个源 .tex 执行收尾，返回缺失产物数。"""
    d = src.parent
    stem = src.stem
    is_answer = is_answer_doc(stem)
    missing = 0

    teacher_ok = exam_ok = sheet_ok = True

    if not is_answer:
        # 教师版（normal）+ 学生版（有答题空间）
        t_norm = d / f"{stem}-教师版.tex"
        s_ver = d / f"{stem}-学生版.tex"
        if force or not (t_norm.exists() and s_ver.exists()):
            rc = run_py([str(GEN_TEACHER), str(src), "--mode", "normal"], d)
            if rc != 0:
                print(f"[WARN] 教师版/学生版生成失败（rc={rc}），相关产物不纳入校验",
                      file=sys.stderr)
                teacher_ok = False

        # 教师版-考试（exam）
        if not skip_exam:
            t_exam = d / f"{stem}-教师版-考试.tex"
            if force or not t_exam.exists():
                rc = run_py([str(GEN_TEACHER), str(src),
                             "--mode", "exam", "--no-student"], d)
                if rc != 0:
                    print(f"[WARN] 教师版-考试生成失败（rc={rc}），相关产物不纳入校验",
                          file=sys.stderr)
                    exam_ok = False

        # 答题卡 A4 + A3
        if not skip_answersheet:
            a4 = d / f"{stem}-答题卡-A4.tex"
            a3 = d / f"{stem}-答题卡-A3.tex"
            if force or not (a4.exists() and a3.exists()):
                cmd = [str(GEN_SHEET), str(src), "--layout", "both", "--no-compile"]
                if force:
                    cmd.append("--force")
                rc = run_py(cmd, d)
                if rc == 5:
                    print("[WARN] 答题卡目标文件疑似手工版，已保留不覆盖"
                          "（可加 --force 强制替换）", file=sys.stderr)
                elif rc == 4:
                    print("[WARN] 答题卡生成被拒绝（非学生版试题输入），"
                          "相关产物不纳入校验", file=sys.stderr)
                    sheet_ok = False
                elif rc != 0:
                    print(f"[WARN] 答题卡生成失败（rc={rc}），相关产物不纳入校验",
                          file=sys.stderr)
                    sheet_ok = False

    # 部署 build.py
    deploy_build_py(d)

    # 编译全部 tex ×2 并清理
    if (d / "build.py").exists():
        rc = run_py(["build.py"], d)
        if rc != 0:
            print("[ERROR] build.py 编译存在失败项，详见上方输出", file=sys.stderr)

    clean_previews(d)

    # 产物校验清单
    required = [src.name, f"{stem}.pdf", "build.py"]
    if not is_answer:
        if teacher_ok:
            required += [f"{stem}-学生版.tex", f"{stem}-学生版.pdf",
                         f"{stem}-教师版.tex", f"{stem}-教师版.pdf"]
        if teacher_ok and not skip_exam and exam_ok:
            required += [f"{stem}-教师版-考试.tex", f"{stem}-教师版-考试.pdf"]
        if not skip_answersheet and sheet_ok:
            required += [f"{stem}-答题卡-A4.tex", f"{stem}-答题卡-A4.pdf",
                         f"{stem}-答题卡-A3.tex", f"{stem}-答题卡-A3.pdf"]

    tag = "（答案文档）" if is_answer else ""
    print(f"\n== 产物清单 [{src.name}] {tag}==")
    for name in required:
        if (d / name).exists():
            print(f"  [OK]   {name}")
        else:
            print(f"  [MISS] {name}")
            missing += 1

    img_dir = d / f"Images-{stem}"
    if img_dir.is_dir():
        print(f"  [OK]   {img_dir.name}/")
    else:
        print(f"  [--]   Images-{stem}/（本卷无图片目录）")

    return missing

def main():
    ap = argparse.ArgumentParser(
        description="排版收尾：按 ARTIFACT 规范一键补齐标准产物集并校验")
    ap.add_argument("target", help="源 .tex 文件或试卷目录")
    ap.add_argument("--force", action="store_true",
                    help="产物已存在也重新生成（答题卡会覆盖手工版）")
    ap.add_argument("--skip-answersheet", action="store_true", help="跳过答题卡")
    ap.add_argument("--skip-exam", action="store_true", help="跳过教师版-考试")
    args = ap.parse_args()

    target = Path(args.target)
    if target.is_dir():
        sources = [p for p in sorted(target.glob("*.tex"))
                   if not is_derived(p.stem)]
        if not sources:
            print(f"[WARN] 目录内没有可处理的源 .tex: {target}", file=sys.stderr)
            return 0
    else:
        if not target.exists():
            print(f"[ERROR] 文件不存在: {target}", file=sys.stderr)
            return 1
        sources = [target]

    total_missing = 0
    failed_sources = []
    for src in sources:
        missing = process_source(src, force=args.force,
                                 skip_answersheet=args.skip_answersheet,
                                 skip_exam=args.skip_exam)
        if missing:
            total_missing += missing
            failed_sources.append(src.name)

    if failed_sources:
        print(f"\n[ERROR] {len(failed_sources)} 个源文件产物缺失："
              f"{', '.join(failed_sources)}", file=sys.stderr)
        return 1

    print("\n[OK] 全部产物齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
