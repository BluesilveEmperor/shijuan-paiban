# -*- coding: utf-8 -*-
"""
JSON 文件消毒脚本 - 修复中文弯引号损坏问题

地理试卷排版流水线中，AI 使用 Write 工具写入 JSON 文件时，
中文弯引号 "" (U+201C/U+201D) 可能被转换为 ASCII " (U+0022)，
导致 JSON 语法断裂或语义损坏。

本脚本处理两种损坏场景：
  场景A（语法断裂）：内部 " 被当作字符串结束符，json.loads() 失败
  场景B（语义损坏）：json.loads() 成功但内容中 " 为 U+0022 而非弯引号

用法:
    python sanitize_json.py --in-place <文件路径>
    python sanitize_json.py --input <输入路径> --output <输出路径>
    python sanitize_json.py --check <文件路径>
"""

import argparse
import json
import re
import sys
import os

LQ = '\u201c'  # 左弯引号 "
RQ = '\u201d'  # 右弯引号 "


def sanitize_json(raw_text):
    """修复 JSON 文本中的中文弯引号损坏。

    Returns:
        tuple: (fixed_text, stats_dict)
            fixed_text: 修复后的 JSON 文本
            stats_dict: 修复统计信息
    """
    stats = {
        'syntax_fixes': 0,
        'semantic_fixes': 0,
        'phases': [],
    }

    # Phase 1: 尝试直接解析
    try:
        data = json.loads(raw_text)
        stats['phases'].append('Phase1: JSON语法正确')
    except json.JSONDecodeError:
        stats['phases'].append('Phase1: JSON语法错误，进入Phase2修复')
        # Phase 2: 修复语法断裂
        raw_text, syntax_fixes = _fix_syntax_errors(raw_text)
        stats['syntax_fixes'] = syntax_fixes
        stats['phases'].append(f'Phase2: 修复了{syntax_fixes}处语法断裂')

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            return None, {**stats, 'error': f'Phase2修复后仍无法解析: {e}'}

    # Phase 3: 修复语义损坏（JSON 语法正确但内容中的 " 应为弯引号）
    data, semantic_fixes = _fix_semantic_quotes(data)
    stats['semantic_fixes'] = semantic_fixes
    if semantic_fixes > 0:
        stats['phases'].append(f'Phase3: 修复了{semantic_fixes}处语义损坏')
    else:
        stats['phases'].append('Phase3: 无语义损坏')

    # Phase 4: 重新序列化
    fixed_text = json.dumps(data, ensure_ascii=False, indent=2)
    return fixed_text, stats


def _fix_syntax_errors(raw_text):
    """修复场景A：JSON 语法断裂（字符串值内部的裸 " 导致解析失败）。

    策略：逐字符遍历文本，跟踪 JSON 字符串边界。
    当在字符串值内部遇到裸 " 且它破坏了 JSON 结构时，
    将其替换为适当的中文弯引号。

    引号方向采用交替策略：每个 JSON 字符串值内，
    第 1、3、5… 个裸 " → LQ（左引号），第 2、4、6… 个 → RQ（右引号）。
    """
    fixes = 0
    result = []
    i = 0
    n = len(raw_text)

    while i < n:
        ch = raw_text[i]

        # 检测 JSON 字符串的开始
        if ch == '"':
            # 找到字符串的结束位置
            string_start = i
            i += 1
            string_chars = ['"']
            quote_count = 0  # 当前 JSON 字符串值内的弯引号替换计数

            while i < n:
                c = raw_text[i]

                if c == '\\' and i + 1 < n:
                    # 转义序列，完整保留
                    string_chars.append(c)
                    string_chars.append(raw_text[i + 1])
                    i += 2
                    continue

                if c == '"':
                    # 可能是字符串结束，也可能是应替换的弯引号
                    # 检查：如果从此处作为字符串结束，后续是否是合法 JSON
                    candidate = ''.join(string_chars) + '"'
                    rest = raw_text[i + 1:]

                    if _is_valid_string_end(candidate, rest):
                        # 这是合法的字符串结束
                        string_chars.append('"')
                        i += 1
                        break
                    else:
                        # 这个 " 应该是弯引号
                        # 交替策略：奇数个→LQ，偶数个→RQ
                        quote_count += 1
                        before_text = ''.join(string_chars)
                        replacement = _determine_quote_type(before_text, rest, quote_count)
                        string_chars.append(replacement)
                        fixes += 1
                        i += 1
                        continue

                string_chars.append(c)
                i += 1

            result.append(''.join(string_chars))
        else:
            result.append(ch)
            i += 1

    return ''.join(result), fixes


def _is_valid_string_end(string_so_far, rest):
    """判断当前 " 是否为合法的字符串结束引号。

    如果作为结束引号后，后续文本看起来像合法 JSON 片段，
    则认为这是字符串结束。
    """
    # 字符串结束后应该跟：, ] } : 或空白
    rest_stripped = rest.lstrip()
    if not rest_stripped:
        return True

    valid_next_chars = [',', ']', '}', ':', '\n', '\r']
    return rest_stripped[0] in valid_next_chars


def _determine_quote_type(before_text, after_text, quote_count=None):
    """根据上下文判断应替换为左弯引号还是右弯引号。

    优先级：
    1. 交替策略（quote_count 有效时）：奇数→LQ，偶数→RQ
       - 中文引号天然成对出现，第一个必定是左引号，第二个是右引号
       - 这比任何上下文启发式都更可靠
    2. 上下文启发式（回退方案，quote_count=None 时使用）：
       - 前后都是 CJK → 左弯引号（开启引用）
       - 前面是 CJK，后面不是 → 右弯引号（关闭引用）
       - 后面是 CJK → 左弯引号
       - 默认：左弯引号
    """
    # 交替策略：优先使用（最可靠的方案）
    if quote_count is not None:
        return RQ if quote_count % 2 == 0 else LQ

    # 上下文启发式（回退方案）
    before_stripped = before_text.rstrip('"')
    after_stripped = after_text.lstrip()

    cjk_range = r'\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2000-\u206f'

    if before_stripped and re.search(f'[{cjk_range}]$', before_stripped):
        if after_stripped and re.search(f'^[{cjk_range}]', after_stripped):
            return LQ
        else:
            return RQ

    if after_stripped and re.search(f'^[{cjk_range}]', after_stripped):
        return LQ

    return LQ


def _fix_semantic_quotes(data):
    """修复场景B：JSON 语法正确但字符串值中的 ASCII " 应为中文弯引号。

    递归遍历 JSON 树，在所有字符串值中查找中文语境中的 ASCII " 对，
    替换为 U+201C/U+201D。
    """
    fixes = 0

    if isinstance(data, dict):
        for key in list(data.keys()):
            if isinstance(data[key], str):
                fixed, count = _fix_string_value(data[key])
                if count > 0:
                    data[key] = fixed
                    fixes += count
            else:
                data[key], sub_fixes = _fix_semantic_quotes(data[key])
                fixes += sub_fixes
    elif isinstance(data, list):
        for i in range(len(data)):
            if isinstance(data[i], str):
                fixed, count = _fix_string_value(data[i])
                if count > 0:
                    data[i] = fixed
                    fixes += count
            else:
                data[i], sub_fixes = _fix_semantic_quotes(data[i])
                fixes += sub_fixes

    return data, fixes


# 匹配中文语境中的 ASCII "..." 对
# 前后均有 CJK 字符或中文标点，中间为引用内容
_CJK = r'\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2000-\u206f\u2460-\u24ff'
_CURLY_QUOTE_PAIR = re.compile(
    f'([{_CJK}])'      # 前导 CJK 字符
    r'"([^"]*?)"'      # ASCII 双引号对及其内容
    f'([{_CJK}])'      # 后续 CJK 字符
)

# 边界模式：引号出现在行首、空格后、句号后、数字后等，但后面跟 CJK 字符
# 例如：1. "XXX"、A. "XXX"、"XXX"（句首）
_QUOTE_BOUNDARY = re.compile(
    r'(^|[\s.\d\\)）\]\>\:\;\,，\、])'
    r'"([^"]*?)"'
    rf'(?=[{_CJK}])'
)


def _fix_string_value(text):
    """修复单个字符串值中的语义损坏。

    检测中文语境中应为弯引号的 ASCII " 对。
    """
    if not text or '"' not in text:
        return text, 0

    fixes = 0
    prev = text

    # 第一遍：标准 CJK 包围模式
    for _ in range(10):
        new_text = _CURLY_QUOTE_PAIR.sub(
            lambda m: f'{m.group(1)}{LQ}{m.group(2)}{RQ}{m.group(3)}',
            prev
        )
        if new_text == prev:
            break
        fixes += prev.count('"') - new_text.count('"')
        prev = new_text

    # 第二遍：边界模式 —— 引号前为行首/空格/标点/数字，后跟 CJK
    for _ in range(10):
        new_text = _QUOTE_BOUNDARY.sub(
            lambda m: f'{m.group(1)}{LQ}{m.group(2)}{RQ}',
            prev
        )
        if new_text == prev:
            break
        fixes += prev.count('"') - new_text.count('"')
        prev = new_text

    # 计算实际修复数
    actual_fixes = (text.count('"') - prev.count('"')) // 2
    return prev, max(actual_fixes, 0)


def check_json(file_path):
    """仅检查文件是否有弯引号问题，不修改。"""
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    issues = []

    # 检查语法
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        issues.append(f'语法错误: {e}')
        return issues

    # 检查语义：查找中文语境中的 ASCII "
    _check_semantic_in_data(data, '', issues)

    return issues


def _check_semantic_in_data(data, path, issues):
    """递归检查数据中的语义损坏。"""
    if isinstance(data, dict):
        for key, value in data.items():
            curr_path = f'{path}.{key}' if path else key
            if isinstance(value, str):
                matches = _CURLY_QUOTE_PAIR.findall(value)
                if matches:
                    issues.append(f'{curr_path}: 发现{len(matches)}处疑似弯引号损坏: ...{value[:60]}...')
            else:
                _check_semantic_in_data(value, curr_path, issues)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            curr_path = f'{path}[{i}]'
            if isinstance(item, str):
                matches = _CURLY_QUOTE_PAIR.findall(item)
                if matches:
                    issues.append(f'{curr_path}: 发现{len(matches)}处疑似弯引号损坏: ...{item[:60]}...')
            else:
                _check_semantic_in_data(item, curr_path, issues)


def main():
    parser = argparse.ArgumentParser(
        description='JSON 文件消毒 - 修复中文弯引号损坏问题',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python sanitize_json.py --in-place structure.json
  python sanitize_json.py --input structure.json --output fixed.json
  python sanitize_json.py --check structure.json
        '''
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--in-place', '-i', metavar='FILE',
                       help='原地修复文件')
    group.add_argument('--input', metavar='FILE',
                       help='输入文件路径（需配合 --output）')
    group.add_argument('--check', '-c', metavar='FILE',
                       help='仅检查不修改')

    parser.add_argument('--output', '-o', metavar='FILE',
                        help='输出文件路径（配合 --input 使用）')

    args = parser.parse_args()

    # --check 模式
    if args.check:
        file_path = os.path.abspath(args.check)
        if not os.path.exists(file_path):
            print(f'错误: 文件不存在: {file_path}')
            sys.exit(1)

        issues = check_json(file_path)
        if issues:
            print(f'发现 {len(issues)} 个问题:')
            for issue in issues:
                print(f'  - {issue}')
            sys.exit(1)
        else:
            print('未发现弯引号问题')
            sys.exit(0)

    # 确定输入输出路径
    if args.in_place:
        input_path = os.path.abspath(args.in_place)
        output_path = input_path
    elif args.input:
        input_path = os.path.abspath(args.input)
        if not args.output:
            print('错误: 使用 --input 时必须指定 --output')
            sys.exit(1)
        output_path = os.path.abspath(args.output)
    else:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(input_path):
        print(f'错误: 文件不存在: {input_path}')
        sys.exit(1)

    # 读取输入
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # 执行消毒
    fixed_text, stats = sanitize_json(raw_text)

    if fixed_text is None:
        print(f'消毒失败: {stats.get("error", "未知错误")}')
        print('阶段:', ' → '.join(stats.get('phases', [])))
        sys.exit(1)

    # 写入输出
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(fixed_text)

    # 报告结果
    print('消毒完成:')
    for phase in stats.get('phases', []):
        print(f'  {phase}')
    if stats.get('syntax_fixes', 0) > 0:
        print(f'  语法修复: {stats["syntax_fixes"]} 处')
    if stats.get('semantic_fixes', 0) > 0:
        print(f'  语义修复: {stats["semantic_fixes"]} 处')
    if stats.get('syntax_fixes', 0) == 0 and stats.get('semantic_fixes', 0) == 0:
        print('  无需修复，文件已正常')
    print(f'输出: {output_path}')
    sys.exit(0)


if __name__ == '__main__':
    main()
