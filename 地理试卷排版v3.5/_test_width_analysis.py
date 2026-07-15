# -*- coding: utf-8 -*-
"""分析真实试卷中选项宽度分布，诊断2x2为何不触发"""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from typeset_exam import measure_text_width_cm, _select_option_rule

json_path = os.path.join(os.path.dirname(__file__),
    'output/【试卷】吉林省松原市吉林油田高级中学2025-2026学年高二下学期期末地理试卷/试卷数据/final_exam.json')

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 各题选项宽度分析 ===')
print('版心宽=17.2cm, 1x4槽位=[4.54,4.44,4.45,3.77], 2x2右列限制=3.62cm')
print()

questions = data.get('sections', [{}])[0].get('questions', [])
if not questions:
    for sec in data.get('sections', []):
        questions.extend(sec.get('questions', []))

for q in questions:
    if q.get('question_type') != '选择题':
        continue
    qnum = q.get('number', '?')
    options = q.get('options', [])
    if isinstance(options, list):
        opt_dict = {}
        for opt in options:
            label = opt.get('label', '')
            text = opt.get('text', '')
            if label:
                opt_dict[label] = text
        options = opt_dict
    if not options:
        continue

    rule = _select_option_rule(options)
    rule_names = {1: '1x4', 2: '2x2', 3: '4x1'}
    
    # 计算各选项宽度
    import re
    from typeset_exam import PLACEHOLDER_TOKEN_PATTERN, FORMAT_TAG_PATTERN
    widths = {}
    for label, text in options.items():
        clean = PLACEHOLDER_TOKEN_PATTERN.sub('', f'{label}. {text}')
        clean = FORMAT_TAG_PATTERN.sub('', clean)
        widths[label] = measure_text_width_cm(clean)
    
    w_str = ', '.join(f'{l}={widths[l]:.2f}cm' for l in sorted(widths.keys()))
    print(f'题{qnum}: 规则{rule}({rule_names[rule]}) | {w_str}')
    
    # 分析2x2为何失败
    if rule != 2:
        b_w = widths.get('B', 0)
        d_w = widths.get('D', 0)
        right_max = max(b_w, d_w)
        if right_max > 3.62:
            print(f'       → 2x2失败原因: 右列(B/D)最大={right_max:.2f}cm > 3.62cm (差{right_max-3.62:.2f}cm)')
        a_w = widths.get('A', 0)
        c_w = widths.get('C', 0)
        left_max = max(a_w, c_w)
        if left_max > 8.83:
            print(f'       → 2x2失败原因: 左列(A/C)最大={left_max:.2f}cm > 8.83cm')
