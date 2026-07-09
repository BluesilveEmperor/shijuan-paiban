#!/usr/bin/env python3
"""
JSON 消毒/编码修复工具

用途：解决 AI 通过 Write 工具生成 JSON 时，中文特殊标点（如弯引号 ""、''）
       被错误转换为 ASCII 引号导致 JSON 解析失败的问题。

原理：将输入文件重新通过 Python 的 json.dump() 序列化，利用 Python 的
      ensure_ascii=False 保留原始 Unicode 字符，同时自动修复 JSON 结构。

用法：
    # 就地修复
    python scripts/sanitize_json.py --in-place output/xxx/中间数据/structure.json

    # 输出到新文件
    python scripts/sanitize_json.py output/xxx/broken.json --output output/xxx/fixed.json

    # 仅校验（不修改）
    python scripts/sanitize_json.py output/xxx/data.json --check-only

退出码：
    0: 文件正常 / 修复成功
    1: 解析失败（无法修复）
    2: 文件不存在
"""

import argparse
import json
import os
import sys


def try_parse_and_fix(file_path: str) -> tuple[bool, dict | None, str]:
    """尝试解析 JSON 文件，返回 (成功, 数据, 错误信息)。

    依次尝试标准解析和容错修复解析。
    """
    # 尝试1: 标准 UTF-8 解析
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return True, data, ''
    except json.JSONDecodeError as e:
        original_error = f"{e.msg} (第{e.lineno}行, 第{e.colno}列)"

    # 尝试2: 逐字符修复常见的编码问题
    try:
        data = _attempt_repair(file_path)
        if data is not None:
            return True, data, original_error
    except Exception:
        pass

    return False, None, original_error


def _attempt_repair(file_path: str) -> dict | None:
    """尝试修复被截断的 JSON。

    常见问题：
    1. 中文弯引号 "" (U+201C/U+201D) 被转为 ASCII " (U+0022)
       → 导致 JSON 字符串提前终止
       → 将上下文中的 ASCII " 替换为 Unicode 弯引号
    2. 中文弯引号 '' (U+2018/U+2019) 被转为 ASCII ' (U+0027)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # 策略: 尝试以宽松模式解析（逐步放宽）
    # 最简单的方法：将所有不在 JSON 结构位置的 " 替换为 Unicode 弯引号
    fixed = _fix_chinese_quotes_in_json(raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


def _fix_chinese_quotes_in_json(text: str) -> str:
    """修复 JSON 中被错误转换的中文引号。

    启发式方法：在 JSON 字符串值内部，成对出现的 ASCII 引号 "text" 中，
    如果引号包围的是中文字符，则将其替换为 Unicode 弯引号。

    更可靠的方法：找到所有 JSON 字符串值，对其内容中的 " 字符进行转义。
    """
    import re

    # 方法：找到所有 JSON 字符串值边界，替换内部的 ASCII " 为 \"
    # 这比猜测哪个"是中文弯引号更安全，因为 \u201c 和 \u201d 在 JSON 中
    # 本身就是合法的字符串内容。

    result = []
    in_string = False
    escape_next = False
    fixed_count = 0

    for i, ch in enumerate(text):
        if escape_next:
            result.append(ch)
            escape_next = False
            continue

        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue

        if ch == '"':
            if not in_string:
                # 进入字符串
                in_string = True
                result.append(ch)
            else:
                # 可能是字符串结束，也可能是中文引号
                # 检查下一个非空白字符是 : 还是 , 还是 } 还是 ]
                rest = text[i+1:].lstrip()
                if rest and rest[0] in (':', ',', '}', ']'):
                    # JSON 字符串正常结束
                    in_string = False
                    result.append(ch)
                else:
                    # 字符串内部的 " — 很可能是中文弯引号
                    # 将其转义为 \" 以保持 JSON 合法性
                    result.append('\\"')
                    fixed_count += 1
            continue

        result.append(ch)

    return ''.join(result)


def sanitize_file(input_path: str, output_path: str | None = None) -> dict:
    """清洗 JSON 文件。

    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出路径（None 表示原地修复）

    Returns:
        dict: 修复结果摘要
    """
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'文件不存在: {input_path}'}

    success, data, parse_error = try_parse_and_fix(input_path)

    if not success:
        return {
            'success': False,
            'error': f'无法解析 JSON: {parse_error}',
            'parse_error': parse_error
        }

    # 重新写入以规范化编码
    target = output_path or input_path
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 验证写入后的文件可正确解析
    with open(target, 'r', encoding='utf-8') as f:
        json.load(f)

    result = {
        'success': True,
        'was_repaired': bool(parse_error),
        'output': target,
        'original_error': parse_error or None
    }

    if bool(parse_error):
        result['message'] = f'修复成功: {parse_error} → 已重新编码为标准 UTF-8 JSON'

    return result


def main():
    parser = argparse.ArgumentParser(
        description='JSON 消毒/编码修复工具 - 地理试卷排版v3.0'
    )
    parser.add_argument(
        'input',
        help='输入 JSON 文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='输出 JSON 文件路径（默认原地修复）'
    )
    parser.add_argument(
        '--in-place', '-i',
        action='store_true',
        help='原地修复（等同不指定 --output）'
    )
    parser.add_argument(
        '--check-only', '-c',
        action='store_true',
        help='仅校验不修改'
    )

    args = parser.parse_args()

    if args.check_only:
        success, data, error = try_parse_and_fix(args.input)
        if success:
            print(f'✓ {args.input} — 格式正常')
            sys.exit(0)
        else:
            print(f'✗ {args.input} — {error}')
            sys.exit(1)

    result = sanitize_file(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result['success']:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
