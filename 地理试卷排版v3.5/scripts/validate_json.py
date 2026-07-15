#!/usr/bin/env python3
"""
JSON Schema 校验工具

用途：读取 JSON Schema 文件和待校验的 JSON 文件，输出校验结果（结构化 JSON）。
用于 v3.0 六步流水线每步产物的格式校验。

用法：
    python validate_json.py --schema schemas/exam_paper.schema.json --json output/{试卷名称}/中间数据/structure.json [--log validate.log]

退出码：
    0: 校验通过
    1: 校验失败（含错误明细）
    2: 运行异常（如文件不存在、Schema 格式错误）
"""

import argparse
import json
import sys
import os
import traceback
from datetime import datetime


def load_json(file_path: str) -> dict:
    """加载 JSON 文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_json(schema: dict, data: dict) -> dict:
    """使用 jsonschema 库验证数据"""
    try:
        import jsonschema
    except ImportError:
        return {
            "valid": False,
            "error": "缺少 jsonschema 库，请执行: pip install jsonschema",
            "details": []
        }

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))

    if not errors:
        return {
            "valid": True,
            "error": None,
            "details": []
        }

    error_details = []
    for err in errors:
        # 构建人类可读的错误路径
        path = " → ".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
        error_details.append({
            "path": path,
            "message": err.message,
            "schema_path": " → ".join(str(p) for p in err.schema_path) if err.schema_path else "",
            "validator": err.validator
        })

    return {
        "valid": False,
        "error": f"共 {len(errors)} 个校验错误",
        "details": error_details
    }


def write_log(log_path: str, result: dict, schema_path: str, json_path: str):
    """写入日志文件"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "schema": os.path.abspath(schema_path),
        "target": os.path.abspath(json_path),
        "result": result
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="JSON Schema 校验工具 - 地理试卷排版v3.0"
    )
    parser.add_argument(
        "--schema", "-s",
        required=True,
        help="JSON Schema 文件路径"
    )
    parser.add_argument(
        "--json", "-j",
        required=True,
        help="待校验的 JSON 文件路径"
    )
    parser.add_argument(
        "--log", "-l",
        default=None,
        help="日志文件路径（可选，追加写入）"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，仅输出 JSON 结果"
    )

    args = parser.parse_args()

    result = {}
    exit_code = 0

    try:
        if not args.quiet:
            print(f"[validate_json] 加载 Schema: {args.schema}", file=sys.stderr)
        schema = load_json(args.schema)

        if not args.quiet:
            print(f"[validate_json] 加载目标: {args.json}", file=sys.stderr)
        data = load_json(args.json)

        if not args.quiet:
            print(f"[validate_json] 开始校验...", file=sys.stderr)
        result = validate_json(schema, data)

        if result["valid"]:
            if not args.quiet:
                print(f"[validate_json] ✓ 校验通过", file=sys.stderr)
            exit_code = 0
        else:
            if not args.quiet:
                print(f"[validate_json] ✗ 校验失败:", file=sys.stderr)
                for d in result["details"]:
                    print(f"  - {d['path']}: {d['message']}", file=sys.stderr)
            exit_code = 1

    except FileNotFoundError as e:
        result = {
            "valid": False,
            "error": str(e),
            "details": []
        }
        exit_code = 2
        print(f"[validate_json] 错误: {e}", file=sys.stderr)

    except json.JSONDecodeError as e:
        result = {
            "valid": False,
            "error": f"JSON 解析错误: {e.msg} (第{e.lineno}行, 第{e.colno}列)",
            "details": [{"path": f"line {e.lineno}, col {e.colno}", "message": e.msg}]
        }
        exit_code = 2
        print(f"[validate_json] JSON 解析错误: {e}", file=sys.stderr)

    except Exception as e:
        result = {
            "valid": False,
            "error": f"未知错误: {str(e)}",
            "details": [{"path": "", "message": traceback.format_exc()}]
        }
        exit_code = 2
        print(f"[validate_json] 未知错误: {e}", file=sys.stderr)

    # 写日志
    if args.log:
        try:
            write_log(args.log, result, args.schema, args.json)
        except Exception as e:
            print(f"[validate_json] 日志写入失败: {e}", file=sys.stderr)

    # 输出 JSON 结果到 stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
