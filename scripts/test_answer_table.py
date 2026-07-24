# -*- coding: utf-8 -*-
"""选择题答题表功能测试脚本。

验证题组识别、贪心分行、表格生成是否正确。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typeset_exam import (
    _parse_group_size,
    _identify_choice_groups,
    _greedy_layout_lines,
    _calc_target_lines,
    _auto_calc_target_per_line,
    add_choice_answer_table,
    load_template,
    setup_logger,
    PAGE_CONTENT_WIDTH_CM,
)
from docx import Document
from docx.oxml.ns import qn as docx_qn


def test_parse_group_size():
    """测试引导语解析。"""
    print('=== 测试 guide_sentence 解析 ===')
    cases = [
        ('据此完成1～3题', 3),
        ('完成下面3小题', 3),
        ('完成1-3题', 3),
        ('完成下列要求', None),
        ('据此回答2~5题', 4),
        ('完成14题', None),       # 不应匹配为14道
        ('完成下面2题', 2),
        ('', None),
        ('据此完成3小题', 3),
        ('完成1—4题', 4),
    ]
    passed = 0
    for text, expected in cases:
        result = _parse_group_size(text)
        ok = result == expected
        status = 'OK' if ok else 'FAIL'
        print(f'  [{status}] {text!r:25s} -> {result} (期望 {expected})')
        if ok:
            passed += 1
    print(f'  通过: {passed}/{len(cases)}')
    return passed == len(cases)


def test_identify_groups():
    """测试题组识别。"""
    print()
    print('=== 测试题组识别 ===')
    # 16题：1-2独立, 3-5共用材料, 6-8共用材料, 9-10共用材料, 11-13共用材料, 14-16共用材料
    questions = []
    for n in ['1', '2']:
        questions.append({'number': n, 'question_type': '选择题', 'materials': []})
    questions.append({'number': '3', 'question_type': '选择题',
                      'materials': [{'guide_sentence': '据此完成3～5题'}]})
    for n in ['4', '5']:
        questions.append({'number': n, 'question_type': '选择题', 'materials': []})
    questions.append({'number': '6', 'question_type': '选择题',
                      'materials': [{'guide_sentence': '完成下面3小题'}]})
    for n in ['7', '8']:
        questions.append({'number': n, 'question_type': '选择题', 'materials': []})
    questions.append({'number': '9', 'question_type': '选择题',
                      'materials': [{'guide_sentence': '完成下列要求'}]})
    questions.append({'number': '10', 'question_type': '选择题', 'materials': []})
    questions.append({'number': '11', 'question_type': '选择题',
                      'materials': [{'guide_sentence': '据此完成11～13题'}]})
    for n in ['12', '13']:
        questions.append({'number': n, 'question_type': '选择题', 'materials': []})
    questions.append({'number': '14', 'question_type': '选择题',
                      'materials': [{'guide_sentence': '据此完成14～16题'}]})
    for n in ['15', '16']:
        questions.append({'number': n, 'question_type': '选择题', 'materials': []})

    groups = _identify_choice_groups(questions)
    expected = [['1'], ['2'], ['3', '4', '5'], ['6', '7', '8'],
                ['9', '10'], ['11', '12', '13'], ['14', '15', '16']]
    ok = groups == expected
    print(f'  题组: {groups}')
    print(f'  期望: {expected}')
    print(f'  [{"OK" if ok else "FAIL"}]')
    return ok


def test_greedy_layout():
    """测试动态贪心分行。"""
    print()
    print('=== 测试动态贪心分行 ===')
    groups = [['1'], ['2'], ['3', '4', '5'], ['6', '7', '8'],
              ['9', '10'], ['11', '12', '13'], ['14', '15', '16']]
    total_q = sum(len(g) for g in groups)
    target_lines = _calc_target_lines(total_q)
    target_per_line, max_cols = _auto_calc_target_per_line(groups, target_lines, PAGE_CONTENT_WIDTH_CM)

    lines = _greedy_layout_lines(groups, target_per_line=target_per_line, max_physical_cols=max_cols)
    print(f'  总题数={total_q}, 目标行数={target_lines}, 每行上限={target_per_line}, {max_cols}列')
    print(f'  分行: {lines}')
    for i, line in enumerate(lines):
        q_count = sum(len(g) for g in line)
        p_count = q_count + max(0, len(line) - 1)
        print(f'  第{i+1}行: 题数={q_count}, 物理列={p_count}')
    # 16题 → 目标2行，结果应尽量接近2行
    ok = len(lines) <= target_lines
    print(f'  行数 {len(lines)} <= 目标 {target_lines}: [{"OK" if ok else "FAIL"}]')
    return ok


def test_table_generation():
    """测试表格生成（生成真实 docx 并检查结构）。"""
    print()
    print('=== 测试表格生成 ===')
    template_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'template.dotx')
    template_path = os.path.abspath(template_path)

    doc = load_template(template_path)

    # 模拟 sections
    sections = [{
        'type': '选择题',
        'questions': []
    }]
    # 16题，带题组
    for n in ['1', '2']:
        sections[0]['questions'].append({'number': n, 'question_type': '选择题', 'materials': []})
    sections[0]['questions'].append({'number': '3', 'question_type': '选择题',
                                     'materials': [{'guide_sentence': '据此完成3～5题'}]})
    for n in ['4', '5']:
        sections[0]['questions'].append({'number': n, 'question_type': '选择题', 'materials': []})
    sections[0]['questions'].append({'number': '6', 'question_type': '选择题',
                                     'materials': [{'guide_sentence': '完成下面3小题'}]})
    for n in ['7', '8']:
        sections[0]['questions'].append({'number': n, 'question_type': '选择题', 'materials': []})
    sections[0]['questions'].append({'number': '9', 'question_type': '选择题',
                                     'materials': [{'guide_sentence': '完成下列要求'}]})
    sections[0]['questions'].append({'number': '10', 'question_type': '选择题', 'materials': []})
    sections[0]['questions'].append({'number': '11', 'question_type': '选择题',
                                     'materials': [{'guide_sentence': '据此完成11～13题'}]})
    for n in ['12', '13']:
        sections[0]['questions'].append({'number': n, 'question_type': '选择题', 'materials': []})
    sections[0]['questions'].append({'number': '14', 'question_type': '选择题',
                                     'materials': [{'guide_sentence': '据此完成14～16题'}]})
    for n in ['15', '16']:
        sections[0]['questions'].append({'number': n, 'question_type': '选择题', 'materials': []})

    # 临时日志
    log_path = tempfile.mktemp(suffix='.txt')
    logger = setup_logger(log_path)

    table = add_choice_answer_table(doc, sections, logger)

    if table is None:
        print('  [FAIL] 表格未生成')
        return False

    print(f'  表格: {len(table.rows)}行 x {len(table.columns)}列')

    # 检查行数：2行/块 + 1间隔行 = 2*2 + 1 = 5行
    expected_rows = 5
    ok = len(table.rows) == expected_rows
    print(f'  行数: {len(table.rows)} (期望 {expected_rows}) [{"OK" if ok else "FAIL"}]')

    # 检查题号内容
    row0_texts = [c.text.strip() for c in table.rows[0].cells]
    row2_texts = [c.text.strip() for c in table.rows[3].cells]  # 第2块题号行
    print(f'  第1行题号: {row0_texts}')
    print(f'  第2行题号: {row2_texts}')

    # 检查边框：题号格有边框，gap/padding无边框
    def cell_has_border(cell):
        tc = cell._tc
        tcPr = tc.find(docx_qn('w:tcPr'))
        if tcPr is None:
            return False
        tcBorders = tcPr.find(docx_qn('w:tcBorders'))
        if tcBorders is None:
            return False
        top = tcBorders.find(docx_qn('w:top'))
        if top is None:
            return False
        return top.get(docx_qn('w:val')) == 'single'

    row0_borders = [cell_has_border(c) for c in table.rows[0].cells]
    print(f'  第1行边框: {row0_borders}')

    # 题号格应有边框，gap和padding不应有
    has_number = [bool(t) for t in row0_texts]
    border_ok = all(hb == hn for hb, hn in zip(row0_borders, has_number))
    print(f'  边框匹配题号: [{"OK" if border_ok else "FAIL"}]')

    # 检查间隔行（第3行）无边框
    row2_borders = [cell_has_border(c) for c in table.rows[2].cells]
    gap_ok = not any(row2_borders)
    print(f'  间隔行无边框: [{"OK" if gap_ok else "FAIL"}]')

    # 保存文档供人工检查
    output_dir = os.path.join(os.path.dirname(__file__), '..', '排版文档')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, '答题表测试.docx')
    doc.save(output_path)
    print(f'  测试文档已保存: {output_path}')

    all_ok = ok and border_ok and gap_ok
    print(f'  总体: [{"OK" if all_ok else "FAIL"}]')
    return all_ok


def test_no_choice_questions():
    """测试无选择题时不生成答题表。"""
    print()
    print('=== 测试无选择题 ===')
    template_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'template.dotx')
    template_path = os.path.abspath(template_path)
    doc = load_template(template_path)

    sections = [{'type': '非选择题', 'questions': [
        {'number': '1', 'question_type': '非选择题', 'materials': []}
    ]}]

    log_path = tempfile.mktemp(suffix='.txt')
    logger = setup_logger(log_path)

    table = add_choice_answer_table(doc, sections, logger)
    ok = table is None
    print(f'  无选择题返回 None: [{"OK" if ok else "FAIL"}]')
    return ok


def test_single_question():
    """测试只有1道选择题。"""
    print()
    print('=== 测试单题 ===')
    template_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'template.dotx')
    template_path = os.path.abspath(template_path)
    doc = load_template(template_path)

    sections = [{'type': '选择题', 'questions': [
        {'number': '1', 'question_type': '选择题', 'materials': []}
    ]}]

    log_path = tempfile.mktemp(suffix='.txt')
    logger = setup_logger(log_path)

    table = add_choice_answer_table(doc, sections, logger)
    ok = table is not None and len(table.rows) == 2 and len(table.columns) == 1
    print(f'  单题表格: {len(table.rows)}行x{len(table.columns)}列 [{"OK" if ok else "FAIL"}]')
    return ok


if __name__ == '__main__':
    results = []
    results.append(test_parse_group_size())
    results.append(test_identify_groups())
    results.append(test_greedy_layout())
    results.append(test_table_generation())
    results.append(test_no_choice_questions())
    results.append(test_single_question())

    print()
    print('=' * 50)
    passed = sum(results)
    total = len(results)
    print(f'测试结果: {passed}/{total} 通过')
    if passed == total:
        print('全部通过!')
    else:
        print('存在失败项，请检查')
    sys.exit(0 if passed == total else 1)
