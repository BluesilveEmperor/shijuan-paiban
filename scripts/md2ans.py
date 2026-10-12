#!/usr/bin/env python3
r"""Convert MinerU markdown to gaokao answer LaTeX.

Reuses the battle-tested cleaning pipeline from md2tex.py (merge guards,
% escaping, \cir flattening, stray-brace fixes, balanced $ handling). Only
the answer-specific structure parsing and marker styling live here:
  - 【答案】X        -> \daan{X}
  - 【解析】          -> \jieti
  - 【详解】          -> \xijie
  - 【小问 N 详解】   -> \xiaoI / \xiaoII / \xiaoIII
  - 题号/答案 <table> -> tabular (was previously glued into question text)
  - $$...$$ blocks   -> \[...\]
"""
import os, re, sys, argparse
from pathlib import Path

# Import the exam pipeline (same directory; scripts are invoked side by side)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2tex import clean, clean_display, fix_dollar_signs, _html_table_to_latex

TEX_HEADER = r"""\documentclass[12pt,a4paper]{ctexart}
\usepackage[top=2cm,bottom=2cm,left=2.5cm,right=2.5cm]{geometry}
\usepackage{setspace}
\onehalfspacing
\usepackage{enumitem}
\usepackage{amsmath,amssymb}
\usepackage{mathrsfs}
\usepackage{bm}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{array,booktabs,caption}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage{pifont}
\setlength{\headheight}{13.6pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{\small 参考答案}
\fancyfoot[C]{数学试题第\thepage 页（共\pageref{LastPage}页）}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}
\usepackage[hidelinks]{hyperref}
\newcommand{\daan}[1]{{\color{red}\textbf{【答案】#1}}}
\newcommand{\jieti}{\par{\color{gray!60!black}\textbf{【解析】}}}
\newcommand{\xijie}{\par{\color{blue!60!black}\textbf{【详解】}}}
\newcommand{\xiaoI}{\par{\color{blue!60!black}\textbf{【小问 1 详解】}}}
\newcommand{\xiaoII}{\par{\color{blue!60!black}\textbf{【小问 2 详解】}}}
\newcommand{\xiaoIII}{\par{\color{blue!60!black}\textbf{【小问 3 详解】}}}
\newcommand{\eqimg}[2][0.5]{\includegraphics[width=#1\textwidth,keepaspectratio]{#2}}
\newcommand{\mi}{\mathrm{i}}
\newcommand{\me}{\mathrm{e}}
\newcommand{\blank}{\underline{\hspace{2cm}}}
\newcommand{\unitII}{\ensuremath{\mathrm{II}}}
\newcommand{\cir}[1]{\mbox{\ding{\numexpr171+#1\relax}}}
\newcommand{\cirdig}[1]{\mbox{\ding{\numexpr171+#1\relax}}}
"""

_XIAO = {'1': '\\xiaoI', '2': '\\xiaoII', '3': '\\xiaoIII'}


def style_markers(text):
    """Convert 【答案】/【解析】/【详解】 markers into styled macros."""
    # 【小问 N 详解】 first (most specific)
    text = re.sub(r'【小问\s*([123])\s*详解】', lambda m: _XIAO[m.group(1)], text)
    text = text.replace('【解析】', '\\jieti ')
    text = text.replace('【详解】', '\\xijie ')
    # 【答案】<content> up to the next marker or end of string
    text = re.sub(r'【答案】\s*([^【】]+?)\s*(?=【|$)',
                  lambda m: '\\daan{' + m.group(1).strip() + '}', text)
    # bare trailing 【答案】 with no content
    text = text.replace('【答案】', '\\daan{ }')
    return text


def convert(md_path, tex_path, img_base):
    md = Path(md_path).read_text(encoding='utf-8')
    lines = md.split('\n')

    title = ''
    sections = []
    current_section = None
    current_question = None
    pending_images = []
    pending_tables = []   # section-level tables (answer keys before Q1)
    in_display = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Title
        if stripped.startswith('#') and not title:
            t = stripped.lstrip('#').strip()
            if '一、' not in t and '二、' not in t and '注意事项' not in t and not re.match(r'\d', t):
                title = re.sub(r'\s*命题.*$', '', t)
                continue

        # Section headers
        section_match = re.match(r'#{0,3}\s*([一二三四五][、．.]\s*.+)', stripped)
        if not section_match and re.match(r'[一二三四][、．.]', stripped[:10]):
            section_match = re.match(r'([一二三四五][、．.]\s*.+)', stripped)
        if section_match:
            st = section_match.group(1).strip()
            if '一、' in st or '一．' in st or '单选' in st:
                current_section = ('single', st)
            elif '二、' in st or '二．' in st or '多选' in st:
                current_section = ('multi', st)
            elif '三、' in st or '三．' in st or '填空' in st:
                current_section = ('fill', st)
            elif '四、' in st or '四．' in st or '解答' in st:
                current_section = ('solve', st)
            else:
                current_section = ('other', st)
            sections.append({'type': current_section[0], 'title': current_section[1],
                             'questions': [], 'tables': [], 'images': []})
            current_question = None
            continue

        # Default section for key-only documents
        if not sections and re.match(r'(?:#{1,3}\s*)?\d+[．.]', stripped):
            current_section = ('single', '参考答案')
            sections.append({'type': 'single', 'title': '参考答案',
                             'questions': [], 'tables': [], 'images': []})

        # Display math blocks
        if stripped == '$$':
            in_display = not in_display
            continue
        if in_display:
            if current_question is not None:
                current_question['display'].append(stripped)
            continue

        img_match = re.match(r'!\[\]\((?:images/)?([^\)]+\.(?:jpg|png|jpeg))\)', stripped, re.IGNORECASE)
        if img_match:
            if current_question is not None:
                current_question['images'].append(img_match.group(1))
            else:
                pending_images.append(img_match.group(1))
            continue

        # Figure captions like 第11题图 -> drop
        if re.match(r'^[（(]?第\s*\d+\s*题图[）)]?$', stripped):
            continue

        # HTML tables -> tabular (answer-key tables etc.)
        if '<table' in stripped:
            tab = _html_table_to_latex(stripped)
            if tab:
                if current_question is not None:
                    current_question['tables'].append(tab)
                else:
                    pending_tables.append(tab)
            continue

        # Multi-answer key line: "1. B 2. A 3. D ..." (checked BEFORE q_match).
        # Only when the line consists ENTIRELY of number/letter pairs.
        if sections and re.fullmatch(r'(?:\s*\d+[．.、]\s*[A-D]{1,4})+\s*', stripped):
            keys = re.findall(r'(\d+)[．.、]\s*([A-D]{1,4})', stripped)
            for q_num, ans in keys:
                current_question = {'num': int(q_num), 'text': f'\\daan{{{ans}}}',
                                    'images': [], 'tables': [], 'display': []}
                sections[-1]['questions'].append(current_question)
            continue

        # Question numbers: "1. D 【解析】..." / "13. 4049" / full restated question
        q_match = re.match(r'(?:#{1,3}\s*)?(\d+)[．.、]\s*', stripped)
        if q_match and sections:
            q_num = int(q_match.group(1))
            q_text = stripped[q_match.end():].strip()
            q_images = pending_images[:]
            pending_images = []
            current_question = {'num': q_num, 'text': q_text, 'images': q_images,
                                'tables': [], 'display': []}
            sections[-1]['questions'].append(current_question)
            # flush section-level pending tables once questions start
            if pending_tables:
                sections[-1]['tables'].extend(pending_tables)
                pending_tables = []
            continue

        # Continuation (【答案】/【解析】 blocks, （1） sub-explanations, etc.)
        if current_question is not None:
            current_question['text'] += ' ' + stripped
        elif sections and stripped:
            # preamble text before first question -> flush pending tables w/ text
            if pending_tables:
                sections[-1]['tables'].extend(pending_tables)
                pending_tables = []

    # Post-process: fix unbalanced $ in question text
    for sec in sections:
        for q in sec['questions']:
            q['text'] = fix_dollar_signs(q['text'])
            q['display'] = [fix_dollar_signs(d) for d in q.get('display', [])]

    # Generate LaTeX
    latex = TEX_HEADER
    latex += f'\\graphicspath{{{{{img_base}/}}}}\n\n'
    latex += '\\begin{document}\n\n'

    if title:
        latex += '\\begin{center}\n'
        latex += f'    \\large{{\\textbf{{{title}}}}}\n'
        latex += '\\end{center}\n\n'

    def _emit_blocks(latex, q, indent):
        for d in q.get('display', []):
            latex += f'{indent}\\[{clean_display(d)}\\]\n'
        for tab in q.get('tables', []):
            for ln in tab.split('\n'):
                latex += f'{indent}{ln}\n'
            latex += '\n'
        for img in q.get('images', []):
            latex += f'{indent}\\eqimg{{{img}}}\n\n'
        return latex

    single_count = multi_count = fill_count = 0

    for sec in sections:
        questions = sec['questions']
        if not questions and not sec['tables']:
            continue

        latex += f'\\section*{{{sec["title"]}}}\n\n'

        # Section-level answer-key tables
        for tab in sec['tables']:
            for ln in tab.split('\n'):
                latex += f'{ln}\n'
            latex += '\n'

        if not questions:
            continue

        if sec['type'] in ('single', 'multi', 'fill', 'other'):
            start = {'single': 1, 'multi': single_count + 1,
                     'fill': single_count + multi_count + 1, 'other': 1}[sec['type']]
            latex += f'\\begin{{enumerate}}[start={start}, itemsep=0.4em]\n'
            for q in questions:
                text = style_markers(clean(q['text']))
                latex += f'    \\item {text}\n'
                latex = _emit_blocks(latex, q, '    ')
            latex += '\\end{enumerate}\n\n'
            if sec['type'] == 'single':
                single_count = len(questions)
            elif sec['type'] == 'multi':
                multi_count = len(questions)
            elif sec['type'] == 'fill':
                fill_count = len(questions)

        elif sec['type'] == 'solve':
            solve_start = single_count + multi_count + fill_count + 1
            latex += f'\\begin{{enumerate}}[start={solve_start}, itemsep=1.2em]\n'
            for q in questions:
                text = style_markers(clean(q['text']))
                latex += f'    \\item {text}\n'
                latex = _emit_blocks(latex, q, '    ')
            latex += '\\end{enumerate}\n\n'

    latex += '\\end{document}\n'
    Path(tex_path).write_text(latex, encoding='utf-8')
    return len(sections)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('md', help='Input markdown file')
    parser.add_argument('tex', help='Output tex file')
    parser.add_argument('--img-base', required=True, help='Image directory basename')
    args = parser.parse_args()
    convert(args.md, args.tex, args.img_base)
