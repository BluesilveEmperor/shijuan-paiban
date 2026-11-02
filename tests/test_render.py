# -*- coding: utf-8 -*-
"""渲染器回归测试：排版决策必须是确定性的、可断言的。

覆盖：
1. auto_tasks_cols 的四条规则分支（TASKS-COL-001）
2. auto_itemsep 的经验值与边界（PAGE-003）
3. decide_image_layout 的四种场景（IMG-SCENE-001）
4. assign_numbers 的累计编号（ENUM-START-001）
5. 答题空间只在非末题插入（ANS-002）
6. 填空题自动补 \\blank（STRUCT-BLANK-001）
7. 同一 IR 渲染两次逐字节一致（确定性）
"""
import sys
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from render_tex import (  # noqa: E402
    auto_tasks_cols, auto_itemsep, decide_image_layout,
    assign_numbers, render_paper,
)

fails = []


def check(name, actual, expected):
    if actual == expected:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}\n  actual:   {actual!r}\n  expected: {expected!r}')


def check_true(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


# ── 1. tasks 列数 ──
short = [{'text': '$\\{0\\}$'}, {'text': '$\\{0,1,2\\}$'},
         {'text': '$\\{1,2\\}$'}, {'text': '$\\{0,1\\}$'}]
check('cols-short-formula-4', auto_tasks_cols(short), 4)

long_opts = [
    {'text': '双曲正弦函数 $\\sinh x$ 在实数集上单调递增，且为奇函数'},
    {'text': '对任意实数 $x,y$，都有 $\\tanh(x+y) = \\dfrac{\\tanh x + \\tanh y}{1 + \\tanh x \\tanh y}$'},
    {'text': '对任意实数 $x$，恒有 $\\cosh^{2} x - \\sinh^{2} x = 1$'},
    {'text': '对任意实数 $x$，恒有 $\\sinh 2x = 2\\sinh x \\cosh x$'},
]
# TASKS-COL-003：最宽选项实测 320.7pt > tasks(2) 每列 200.4pt → 必须退到 1 列。
# ⚠️ 旧期望值 2 固化了「按字符数摊算公式宽度」的 bug：该期望下编译必然溢出
# 51.46pt（route_cmp 双路线对比测试实测）。
check('cols-long-2', auto_tasks_cols(long_opts), 1)

img_opts = [{'image': 'a.png'}, {'image': 'b.png'}, {'image': 'c.png'}, {'image': 'd.png'}]
check('cols-image-4', auto_tasks_cols(img_opts), 4)

img_long = [{'image': 'a.png', 'text': '很长的说明文字' * 12}] * 4
# 图片选项退列下限是 2（TASKS-COL-002 禁止图片用 tasks(1) 竖排），
# 即使说明文字长到任何列都放不下，也保持 2 列
check('cols-image-long-2', auto_tasks_cols(img_long), 2)

check('cols-empty-default-4', auto_tasks_cols([]), 4)

# ── 1b. TASKS-COL-003 宽度兜底 ──
# 中等长度选项：实测最宽 217.6pt > tasks(2) 每列 200.4pt → 退到 1 列
medium_opts = [
    {'text': '对任意实数 $x$，恒有 $\\cosh^{2} x - \\sinh^{2} x = 1$'},
    {'text': '对任意实数 $x$，恒有 $\\sinh 2x = 2\\sinh x \\cosh x$'},
]
check('cols-medium-fallback-1', auto_tasks_cols(medium_opts), 1)

# 短选项：4 列（各列 88.2pt，$\{0\}$ 这类够短）
check('cols-short-4', auto_tasks_cols(short), 4)

# 超长单个选项：连 1 列都放不下 → 仍返回 1（下限），交由后续处理
huge_opts = [{'text': '长' * 200}, {'text': '短'}]
check('cols-huge-floor-1', auto_tasks_cols(huge_opts), 1)

# ── 2. itemsep ──
check('itemsep-5q', auto_itemsep(5, 4), '1.75cm')
check('itemsep-3q', auto_itemsep(3, 4), '2.25cm')
check('itemsep-clamp-min', auto_itemsep(20, 1), '1.20cm')
check('itemsep-clamp-max', auto_itemsep(1, 40), '2.50cm')

# ── 3. 图片场景 ──
check('layout-none', decide_image_layout({'images': []}), 'none')
# 列表内单图一律 side（wrapfigure 在列表内会静默丢图，已实测）
check('layout-side-no-subq', decide_image_layout(
    {'images': [{'file': 'a.png'}], 'subquestions': []}), 'side')
check('layout-side', decide_image_layout(
    {'images': [{'file': 'a.png'}], 'subquestions': ['x']}), 'side')
check('layout-multi', decide_image_layout(
    {'images': [{'file': 'a.png'}, {'file': 'b.png'}]}), 'multi')
check('layout-inline', decide_image_layout(
    {'images': [{'file': 'a.png'}], 'image_layout': 'inline'}), 'inline')
check('layout-wrap-explicit', decide_image_layout(
    {'images': [{'file': 'a.png'}], 'image_layout': 'wrap'}), 'wrap')

# ── 4. 编号 ──
ir = {
    'meta': {'template': 'gaokao'},
    'sections': [
        {'type': 'choice_single', 'questions': [{}, {}]},
        {'type': 'choice_multi', 'questions': [{}]},
        {'type': 'fill_blank', 'questions': [{}]},
        {'type': 'long_answer', 'questions': [{}, {}]},
    ],
}
assign_numbers(ir)
check('numbering-starts', [s['_start'] for s in ir['sections']], [1, 3, 4, 5])
check('numbering-question-nos', [q['no'] for s in ir['sections'] for q in s['questions']],
      [1, 2, 3, 4, 5, 6])

# 显式 start 优先
ir2 = {'meta': {'template': 'gaokao'}, 'sections': [
    {'type': 'choice_single', 'start': 5, 'questions': [{}]},
]}
assign_numbers(ir2)
check('numbering-explicit', ir2['sections'][0]['_start'], 5)

# ── 5 & 6 & 7. 端到端渲染 ──
BASE = {
    'meta': {'title': 'T', 'template': 'gaokao', 'total_pages': 1,
             'answer_space': 'normal'},
    'sections': [
        {'heading': '三、填空题：本题共1小题，共5分。', 'type': 'fill_blank',
         'questions': [{'stem': '则 $a=$'}]},
        {'heading': '四、解答题：本题共2小题，共24分。', 'type': 'long_answer',
         'questions': [
             {'stem': '题一', 'points': 12, 'subquestions': ['(1)', '(2)']},
             {'stem': '题二', 'points': 12, 'subquestions': ['(1)']},
         ]},
    ],
}
tex = render_paper(BASE)

check_true('blank-auto-appended', r'则 $a=$ \blank.' in tex, '未自动补 \\blank')
check('answer-space-count',
      sum(1 for ln in tex.split('\n')
          if r'\answern' in ln and 'newcommand' not in ln), 1)
# ANS-002：答题空间必须在最后一道解答题之前，不能出现在末题之后
last_as = tex.rfind(r'\answern')
last_item = tex.rfind(r'\item ')
check_true('answer-space-not-last', 0 < last_as < last_item,
           f'last_as={last_as} last_item={last_item}')

tex2 = render_paper({
    'meta': BASE['meta'],
    'sections': [
        {'heading': '三、填空题：本题共1小题，共5分。', 'type': 'fill_blank',
         'questions': [{'stem': r'则 $a=$ \blank.'}]},
        {'heading': '四、解答题：本题共2小题，共24分。', 'type': 'long_answer',
         'questions': [
             {'stem': '题一', 'points': 12, 'subquestions': ['(1)', '(2)']},
             {'stem': '题二', 'points': 12, 'subquestions': ['(1)']},
         ]},
    ],
})
check('blank-no-duplicate', tex2.count(r'\blank.'), 1)

# 确定性：同一 IR 两次渲染必须一致
a = render_paper({'meta': {'template': 'gaokao', 'title': 'X'},
                  'sections': [{'type': 'choice_single',
                                'questions': [{'stem': 's', 'options': short}]}]})
b = render_paper({'meta': {'template': 'gaokao', 'title': 'X'},
                  'sections': [{'type': 'choice_single',
                                'questions': [{'stem': 's', 'options': short}]}]})
check_true('deterministic', a == b, '两次渲染结果不一致')

# raw_tex 逃生舱
raw = render_paper({'meta': {'template': 'gaokao'},
                    'sections': [{'type': 'long_answer',
                                  'questions': [{'raw_tex': r'\item 特殊结构 $x$'}]}]})
check_true('raw-tex-passthrough', r'\item 特殊结构 $x$' in raw)

print()
if fails:
    print(f'{len(fails)} FAILED: {fails}')
    sys.exit(1)
print('ALL RENDER TESTS PASSED')
