# -*- coding: utf-8 -*-
"""
流水线合规检查脚本 v3.0 (check_compliance)

在每步流水线结束后运行，检测 AI 是否违规操作：
  1. 工作目录中是否存在非官方 .py 文件（AI 自行创建）
  2. 指定 JSON 产物是否已通过 Schema 校验
  3. 步骤执行顺序是否正确

用法:
    # 检查 Step2 结束后
    python scripts/check_compliance.py --work-dir output/{试卷名称}/ --step step2

    # 检查 Step3 结束后
    python scripts/check_compliance.py --work-dir output/{试卷名称}/ --step step3 --json 中间数据/with_placeholders.json

    # 检查 Step5 结束后
    python scripts/check_compliance.py --work-dir output/{试卷名称}/ --step step5 --json 试卷数据/final_exam.json

退出码:
    0 = 合规检查通过
    1 = 发现违规（不允许进入下一步）
    2 = 参数错误
"""

import argparse
import json
import os
import sys
import time

# 官方脚本白名单（相对于项目根目录 scripts/）
OFFICIAL_SCRIPTS = {
    "clean_docx.py",
    "extract_images.py",
    "validate_json.py",
    "sanitize_json.py",
    "typeset_exam.py",
    "utils.py",
    "map_images.py",
    "batch_process.py",
    "e2e_test.py",
    "check_compliance.py",  # 本脚本自身
}

# 各步骤的预期产物
STEP_PRODUCTS = {
    "step1": ["清洗产物/cleaned_no_images.docx", "清洗产物/content.md", "清洗产物/image_manifest.json"],
    "step2": ["中间数据/structure.json"],
    "step3": ["中间数据/with_placeholders.json"],
    "step4": ["中间数据/image_descriptions.json"],
    "step5": ["试卷数据/final_exam.json"],
    "step6": ["排版文档/quality_report.html", "排版文档/typeset_log.txt"],
}


def find_unauthorized_scripts(work_dir):
    """扫描工作目录，查找非官方 .py 文件。"""
    unauthorized = []
    for root, dirs, files in os.walk(work_dir):
        for f in files:
            if f.endswith('.py'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, work_dir)
                # 只要工作目录下出现 .py 文件就是违规（AI 不能在工作目录创建任何 .py）
                unauthorized.append(rel_path)
    return unauthorized


def check_products(work_dir, step):
    """检查指定步骤的预期产物是否存在。"""
    expected = STEP_PRODUCTS.get(step, [])
    missing = []
    present = []
    for p in expected:
        full_path = os.path.join(work_dir, p)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            present.append({"path": p, "size": size})
        else:
            missing.append(p)
    return present, missing


def check_schema_validation(work_dir, json_rel_path, project_dir):
    """对指定 JSON 文件运行 Schema 校验。"""
    json_path = os.path.join(work_dir, json_rel_path)
    schema_path = os.path.join(project_dir, "schemas", "exam_paper.schema.json")
    sanitize_script = os.path.join(project_dir, "scripts", "sanitize_json.py")
    validate_script = os.path.join(project_dir, "scripts", "validate_json.py")

    if not os.path.exists(json_path):
        return False, f"JSON 文件不存在: {json_rel_path}"

    import subprocess

    # 先 sanitize
    try:
        subprocess.run(
            [sys.executable, sanitize_script, "--in-place", json_path],
            capture_output=True, text=True, timeout=30, cwd=project_dir
        )
    except Exception as e:
        return False, f"sanitize_json.py 执行失败: {e}"

    # 再 validate
    try:
        result = subprocess.run(
            [sys.executable, validate_script, "--schema", schema_path, "--json", json_path, "--quiet"],
            capture_output=True, text=True, timeout=30, cwd=project_dir
        )
        if result.returncode != 0:
            return False, f"Schema 校验失败 (退出码 {result.returncode}): {result.stderr[:500]}"
        try:
            parsed = json.loads(result.stdout) if result.stdout else {}
            if not parsed.get("valid", False):
                return False, f"Schema 校验不通过: {parsed.get('error', '未知错误')}"
        except json.JSONDecodeError:
            pass  # 退出码为0视为通过
        return True, "Schema 校验通过"
    except subprocess.TimeoutExpired:
        return False, "Schema 校验超时 (>30s)"
    except Exception as e:
        return False, f"校验异常: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="流水线合规检查 - 检测 AI 违规操作",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", "-w", required=True, help="试卷工作目录")
    parser.add_argument("--step", "-s", required=True,
                        choices=["step1", "step2", "step3", "step4", "step5", "step6"],
                        help="当前完成的步骤")
    parser.add_argument("--json", "-j", help="需要校验的 JSON 产物路径（相对于 work-dir）")
    parser.add_argument("--quiet", "-q", action="store_true", help="精简输出")

    args = parser.parse_args()

    work_dir = os.path.abspath(args.work_dir)
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if not os.path.isdir(work_dir):
        print(f"[COMPLIANCE] 错误: 工作目录不存在: {work_dir}", file=sys.stderr)
        sys.exit(2)

    violations = []
    warnings = []
    ok_items = []

    # 1. 检测非官方 .py 文件
    unauthorized = find_unauthorized_scripts(work_dir)
    if unauthorized:
        for script in unauthorized:
            violations.append(f"违规脚本: {script} —— AI 不得在工作目录创建 .py 文件")
    else:
        ok_items.append("工作目录无违规 .py 文件")

    # 2. 检测产物存在性
    present, missing = check_products(work_dir, args.step)
    if missing:
        for m in missing:
            violations.append(f"产物缺失: {m}")
    for p in present:
        size_kb = p["size"] / 1024
        ok_items.append(f"产物存在: {p['path']} ({size_kb:.1f} KB)")

    # 3. Schema 校验（如果指定了 --json）
    if args.json:
        schema_ok, schema_msg = check_schema_validation(work_dir, args.json, project_dir)
        if schema_ok:
            ok_items.append(schema_msg)
        else:
            violations.append(f"Schema 校验: {schema_msg}")

    # 4. 输出结果
    if not args.quiet:
        print()
        print("=" * 60)
        print(f"  合规检查 - {args.step}")
        print(f"  工作目录: {work_dir}")
        print("=" * 60)
        for item in ok_items:
            print(f"  [OK]    {item}")
        for w in warnings:
            print(f"  [WARN]  {w}")
        for v in violations:
            print(f"  [VIOL]  {v}")

    if violations:
        print()
        print("=" * 60)
        print(f"  合规检查失败: 发现 {len(violations)} 项违规")
        for i, v in enumerate(violations, 1):
            print(f"  {i}. {v}")
        print()
        print("  修复方法:")
        print("    1. 删除工作目录下所有非官方 .py 文件")
        print("    2. 使用 Write/Edit 工具（而非脚本）生成 JSON 产物")
        print("    3. 确保每步 Schema 校验通过后再进入下一步")
        print("=" * 60)
        sys.exit(1)
    else:
        if not args.quiet:
            print()
            print(f"  合规检查通过 - 允许进入下一步")
            print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
