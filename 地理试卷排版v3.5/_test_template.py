# -*- coding: utf-8 -*-
"""检查模板中「选项」样式的缩进和制表位设置（直接读取 ZIP 内 XML）"""
import zipfile
import os
from lxml import etree

tpl_path = os.path.join(os.path.dirname(__file__), 'assets', 'template.dotx')

# .dotx 本质是 zip，直接读 styles.xml
with zipfile.ZipFile(tpl_path, 'r') as z:
    styles_xml = z.read('word/styles.xml')

root = etree.fromstring(styles_xml)
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# 找所有样式
for style in root.findall('.//w:style', ns):
    name_elem = style.find('w:name', ns)
    if name_elem is not None:
        name = name_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
        if '选项' in name or 'option' in name.lower() or name == 'Normal':
            print(f'=== 样式: {name} (type={style.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type")}) ===')
            
            pPr = style.find('w:pPr', ns)
            if pPr is not None:
                # 缩进
                ind = pPr.find('w:ind', ns)
                if ind is not None:
                    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                    first_line = ind.get(f'{w}firstLine')
                    hanging = ind.get(f'{w}hanging')
                    left = ind.get(f'{w}left')
                    right = ind.get(f'{w}right')
                    first_line_chars = ind.get(f'{w}firstLineChars')
                    print(f'  缩进: firstLine={first_line}, hanging={hanging}, left={left}, right={right}, firstLineChars={first_line_chars}')
                else:
                    print(f'  缩进: 无')
                
                # 制表位
                tabs = pPr.find('w:tabs', ns)
                if tabs is not None:
                    tab_list = []
                    for tab in tabs.findall('w:tab', ns):
                        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                        pos = tab.get(f'{w}pos')
                        val = tab.get(f'{w}val')
                        if pos:
                            pos_cm = int(pos) * 635 / 360000
                            tab_list.append(f'{pos_cm:.2f}cm({val})')
                        else:
                            tab_list.append(f'(无pos,{val})')
                    print(f'  制表位: [{", ".join(tab_list)}]')
                else:
                    print(f'  制表位: 无')
                
                # 对齐
                jc = pPr.find('w:jc', ns)
                if jc is not None:
                    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                    print(f'  对齐: {jc.get(f"{w}val")}')
            else:
                print(f'  pPr: 无')
            
            # 字体
            rPr = style.find('w:rPr', ns)
            if rPr is not None:
                w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                rFonts = rPr.find('w:rFonts', ns)
                if rFonts is not None:
                    print(f'  字体: ascii={rFonts.get(f"{w}ascii")}, eastAsia={rFonts.get(f"{w}eastAsia")}')
                sz = rPr.find('w:sz', ns)
                if sz is not None:
                    half_pt = int(sz.get(f'{w}val'))
                    print(f'  字号: {half_pt/2}pt ({half_pt} half-pt)')
            print()
