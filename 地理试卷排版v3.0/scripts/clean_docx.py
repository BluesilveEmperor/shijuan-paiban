# -*- coding: utf-8 -*-
"""
地理试卷清洗脚本
对从学科网等平台下载的地理高考真题 Word 文档进行清洗。

用法:
    python clean_docx.py --input "原始试卷.docx" --output "cleaned.docx"

规则编号对照:
    1.1  删除页眉页脚品牌信息（保留页码）
    1.2  删除域代码（保留页码文字）
    1.3  删除超链接（保留显示文字）
    1.4  删除修订标记和批注
    1.5  删除隐藏文字
    1.6  删除文本框内容
    1.7  矢量图片处理
    1.8  处理自动编号
    1.9  清理特殊地理符号间距
    1.10 统一中英文间距
    1.11 清除原段落格式
    1.12 删除分页符和分节符
    1.13 删除空段落和多余换行
    1.14 清理文档属性
    1.15 统一选项标点（全角→半角）
    1.16 统一题号标点（全角→半角）
    1.17 删除考试名称前图片
    1.18 图片文字替换（WMF 直接提取 + 上下文推断 + 待识别清单）
"""

import argparse
import json
import os
import re
import sys
import shutil
import tempfile
import zipfile
from datetime import datetime
from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn as docx_qn
from lxml import etree

# 确保能导入同目录下的 utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    NSMAP, qn, setup_logger, get_paragraph_text, get_run_text,
    remove_element, find_all, get_media_info, get_image_relationships,
    is_hidden_run, normalize_cn_en_spacing, normalize_special_symbols,
    normalize_punctuation, has_drawing, get_drawings, get_embed_rid,
    insert_text_before_element, get_section_text,
    read_media_file, extract_text_from_wmf
)

# 品牌关键词（出现这些词的页眉页脚段落需要删除）
BRAND_KEYWORDS = ['学科网', '组卷网', '百度文库', '道客巴巴', '豆丁网']


# =====================================================================
# 阶段一：结构性内容清理
# =====================================================================

def rule_1_4_remove_revisions(doc, logger):
    """1.4 删除修订标记和批注"""
    count = 0
    body = doc.element.body

    # 删除 w:ins（插入修订）和 w:del（删除修订），保留其内容
    for tag in ['w:ins', 'w:del']:
        for el in body.findall(f'.//{qn(tag)}'):
            # 将子元素移到父元素中，然后删除容器
            parent = el.getparent()
            if parent is not None:
                for child in list(el):
                    parent.insert(list(parent).index(el), child)
                parent.remove(el)
                count += 1

    # 删除 w:move-from 和 w:move-to
    for tag in ['w:moveFrom', 'w:moveTo']:
        for el in body.findall(f'.//{qn(tag)}'):
            parent = el.getparent()
            if parent is not None:
                for child in list(el):
                    parent.insert(list(parent).index(el), child)
                parent.remove(el)
                count += 1

    logger.info(f'[1.4] 删除修订标记: {count} 处')


def rule_1_6_remove_text_boxes(doc, logger):
    """1.6 删除文本框内容"""
    count = 0
    body = doc.element.body

    # 删除 mc:AlternateContent 中包含文本框的部分
    for ac in body.findall(f'.//{qn("mc:AlternateContent")}'):
        # 检查是否包含文本框
        has_textbox = False
        for txbx in ac.iter(qn('w:txbxContent')):
            has_textbox = True
            break
        if has_textbox:
            remove_element(ac)
            count += 1

    # 删除独立的 w:txbxContent
    for txbx in body.findall(f'.//{qn("w:txbxContent")}'):
        parent = txbx.getparent()
        while parent is not None and parent.tag != qn('w:p'):
            parent = parent.getparent()
        if parent is not None:
            # 文本框通常在一个段落中，删除整个段落
            remove_element(parent)
            count += 1

    # 删除 VML 形状中的文本框
    for shape in body.findall(f'.//{qn("v:shape")}'):
        style = shape.get('style', '')
        if 'textbox' in style.lower() or shape.find(qn('v:textbox')) is not None:
            # 找到包含这个形状的段落并删除
            parent = shape.getparent()
            while parent is not None and parent.tag != qn('w:p'):
                parent = parent.getparent()
            if parent is not None:
                remove_element(parent)
                count += 1

    logger.info(f'[1.6] 删除文本框: {count} 处')


def rule_1_5_remove_hidden_text(doc, logger):
    """1.5 删除隐藏文字"""
    count = 0
    body = doc.element.body

    for r in body.findall(f'.//{qn("w:r")}'):
        if is_hidden_run(r):
            remove_element(r)
            count += 1

    logger.info(f'[1.5] 删除隐藏文字 run: {count} 处')


# =====================================================================
# 阶段二：图片处理
# =====================================================================

def replace_image_punctuation(doc, docx_path, logger, output_dir=None):
    """图片文字替换（WMF 直接提取 + 上下文推断 + 待识别清单）

    处理流程：
    1. WMF/EMF 矢量图片：直接从二进制数据中提取嵌入文本（100% 准确）
       - MathType 生成的 WMF 包含 EXTTEXTOUT 记录和 MathML XML
       - 可提取标点（如 "."）和汉字（如 "的"）
    2. PNG/JPG 小图片（< 2KB）：尝试上下文推断
       - 推断成功：直接替换
       - 推断失败：加入待识别清单（pending_images.json）
    3. 大图片（>= 2KB）：跳过（为试卷内容图片）
    
    Args:
        doc: python-docx Document 对象
        docx_path: 输入 docx 路径（用于读取媒体文件）
        logger: 日志记录器
        output_dir: pending_images.json 和 pending_images/ 的输出目录（默认为输入文件所在目录）
    """
    replaced = 0
    uncertain = 0
    pending_list = []
    body = doc.element.body

    # 获取媒体文件信息和关系映射
    media_info = get_media_info(docx_path)
    rels = get_image_relationships(docx_path)

    # 遍历所有段落
    for p in body.findall(f'.//{qn("w:p")}'):
        # 获取段落中所有 run（直接子元素）
        runs = p.findall(qn('w:r'))
        if not runs:
            continue

        for i, r in enumerate(runs):
            # 检查这个 run 是否包含图片
            drawings = get_drawings(r)
            if not drawings:
                continue

            for drawing in drawings:
                rid = get_embed_rid(drawing)
                if not rid:
                    continue

                # 查找图片文件信息
                media_path = rels.get(rid)
                if not media_path:
                    continue

                info = media_info.get(media_path, {})
                file_size = info.get('size', 0)
                file_ext = info.get('ext', '')

                # 判断是否为疑似文字图片（小于2KB 或 WMF/EMF格式）
                is_likely_text_image = file_size < 2048 or file_ext in ['.wmf', '.emf']

                if not is_likely_text_image:
                    continue

                # 获取上下文文字
                before_text = ''
                for j in range(i):
                    before_text += get_run_text(runs[j])

                after_text = ''
                for j in range(i + 1, len(runs)):
                    after_text += get_run_text(runs[j])

                before_text = before_text.strip()
                after_text = after_text.strip()

                extracted_text = None
                extraction_method = None

                # 策略1：WMF/EMF 直接提取文本
                if file_ext in ['.wmf', '.emf']:
                    wmf_data = read_media_file(docx_path, media_path)
                    if wmf_data:
                        extracted_text = extract_text_from_wmf(wmf_data)
                        if extracted_text:
                            extraction_method = 'WMF提取'

                # 策略2：上下文推断（适用于 PNG/JPG 或 WMF 提取失败时）
                if extracted_text is None:
                    inferred = _infer_punctuation(before_text, after_text)
                    if inferred is not None:
                        extracted_text = inferred
                        extraction_method = '上下文推断'

                if extracted_text is not None:
                    # 替换：在图片位置插入文字，然后删除图片
                    new_r = etree.SubElement(p, qn('w:r'))
                    new_t = etree.SubElement(new_r, qn('w:t'))
                    new_t.text = extracted_text
                    new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

                    # 将新 run 移到原 run 的位置
                    p.remove(new_r)
                    p.insert(list(p).index(r), new_r)

                    # 删除原 run（包含图片的 run）
                    remove_element(r)
                    replaced += 1
                    logger.debug(f'  图片文字替换({extraction_method}): 前文="{before_text[-10:]}" 后文="{after_text[:10]}" -> "{extracted_text}"')
                else:
                    # 无法识别，加入待识别清单
                    uncertain += 1
                    pending_list.append({
                        'media_path': media_path,
                        'file_size': file_size,
                        'file_ext': file_ext,
                        'before_text': before_text[-30:],
                        'after_text': after_text[:30],
                        'paragraph_text': get_paragraph_text(p).strip()[:100],
                    })
                    logger.warning(f'  [待识别] 图片文字无法判断: 前文="{before_text[-20:]}" 后文="{after_text[:20]}" 图片={media_path}({file_size}字节)')

    # 保存待识别清单（使用 output_dir 或回退到输入文件目录）
    if pending_list:
        save_dir = output_dir if output_dir else (os.path.dirname(docx_path) or '.')
        pending_path = os.path.join(save_dir, 'pending_images.json')
        _save_pending_images(docx_path, pending_list, pending_path, logger)
    else:
        logger.info('[图片文字] 无待识别图片')

    logger.info(f'[图片文字] 替换: {replaced} 处, 待识别: {uncertain} 处')


def _infer_punctuation(before_text, after_text):
    """根据上下文推断图片标点类型。
    返回标点字符串，无法判断时返回 None。
    """
    if not before_text:
        return None

    # 情况1：选项编号后的点号
    # 前文以 A/B/C/D 结尾，后文是选项文字
    if re.search(r'[ABCD]$', before_text):
        # 检查前文是否已有标点（如"A."已经有点了）
        if not re.search(r'[ABCD][.．]$', before_text):
            return '.'

    # 情况2：题号后的点号
    # 前文以数字结尾（如"1""2""17"），后文是文字
    if re.search(r'\d+$', before_text):
        if not re.search(r'\d+[.．]$', before_text):
            # 但要排除数字中间的情况（如"2025年"）
            # 只有当后文不是数字时才判断为题号标点
            if after_text and not re.match(r'^\d', after_text):
                return '.'

    # 情况3：子问题编号后的点号
    # 前文以"（1）""（2）"等结尾
    if re.search(r'[）)]\d*[）)]?$', before_text) or re.search(r'\(\d+\)$', before_text):
        return '.'

    # 情况4：句子结尾的句号
    # 前文以中文或标点结尾，且后文为空或是新段落开始
    if not after_text and re.search(r'[\u4e00-\u9fff]$', before_text):
        return '。'

    # 情况5：数字间的负号或小数点
    # 前文以数字结尾，后文以数字开头
    if re.search(r'\d$', before_text) and re.match(r'^\d', after_text):
        # 可能是负号或小数点，默认为小数点
        return '.'

    return None


def _save_pending_images(docx_path, pending_list, pending_path, logger):
    """保存待识别图片清单到 JSON 文件，同时提取图片到临时目录。

    生成的 pending_images.json 供 resolve_pending.py 使用，
    由 AI 或用户识别图片内容后填入 identified_text 字段。
    """
    # 提取图片到临时目录
    pending_dir = os.path.join(os.path.dirname(pending_path), 'pending_images')
    os.makedirs(pending_dir, exist_ok=True)

    pending_data = {
        'source_docx': os.path.basename(docx_path),
        'total': len(pending_list),
        'pending_images': []
    }

    for idx, item in enumerate(pending_list):
        media_path = item['media_path']
        ext = item['file_ext'] or '.png'
        img_id = f'img_{idx + 1:03d}'
        img_filename = f'{img_id}{ext}'
        img_path = os.path.join(pending_dir, img_filename)

        # 从 docx 中提取图片文件
        img_data = read_media_file(docx_path, media_path)
        if img_data:
            with open(img_path, 'wb') as f:
                f.write(img_data)

        pending_data['pending_images'].append({
            'image_id': img_id,
            'image_file': img_filename,
            'image_path': os.path.abspath(img_path),
            'original_media_path': media_path,
            'file_size': item['file_size'],
            'file_ext': item['file_ext'],
            'context_before': item['before_text'],
            'context_after': item['after_text'],
            'paragraph_text': item['paragraph_text'],
            'identified_text': None,  # 待 AI/用户填入
        })

    with open(pending_path, 'w', encoding='utf-8') as f:
        json.dump(pending_data, f, ensure_ascii=False, indent=2)

    logger.info(f'[图片文字] 待识别清单已保存: {pending_path}（{len(pending_list)} 张图片）')


def rule_1_17_remove_exam_name_images(doc, logger):
    """1.17 删除考试名称前的图片"""
    count = 0
    body = doc.element.body
    paragraphs = body.findall(qn('w:p'))

    # 考试名称通常在前5个段落中
    for p in paragraphs[:5]:
        text = get_paragraph_text(p).strip()
        # 检查是否是考试名称段落
        if any(kw in text for kw in ('考试', '学业水平', '高考', '招生', '检测', '期末', '期中', '模拟', '联考', '诊断')):
            # 删除这个段落中的所有图片
            for r in p.findall(qn('w:r')):
                drawings = get_drawings(r)
                if drawings:
                    remove_element(r)
                    count += 1
            if count > 0:
                logger.debug(f'  考试名称段落: "{text[:30]}" 删除 {count} 张图片')
            break

    logger.info(f'[1.17] 删除考试名称前图片: {count} 处')


def rule_1_7_vector_images(doc, logger):
    """1.7 矢量图片处理
    WMF/EMF 标点已在图片标点替换中处理。
    此处仅记录剩余的矢量图片信息。
    """
    count = 0
    body = doc.element.body

    for drawing in body.findall(f'.//{qn("w:drawing")}'):
        # 检查是否为矢量图片（通过扩展名判断）
        rid = get_embed_rid(drawing)
        if rid:
            count += 1

    logger.info(f'[1.7] 矢量图片检查完成，剩余图片: {count} 张（标点类已在上一步替换）')


def rule_1_19_convert_floating_images(doc, logger):
    """1.19 将浮动图片转换为嵌入式，并清除绝对定位属性

    Word 中的图片可以是嵌入式（inline，随文字流动）或浮动式（anchor，
    可浮于文字上方/衬于文字下方等）。浮动图片可能导致排版位置不可控，
    本规则将所有浮动图片转换为嵌入式，确保排版阶段图片位置可控。
    """
    count = 0
    roots = [doc.element.body]
    for section in doc.sections:
        for part in [section.header, section.footer,
                      section.first_page_header, section.first_page_footer,
                      section.even_page_header, section.even_page_footer]:
            if part is not None:
                roots.append(part._element)

    skip_tags = {
        qn('wp:simplePos'), qn('wp:positionH'), qn('wp:positionV'),
        qn('wp:wrapNone'), qn('wp:wrapSquare'), qn('wp:wrapTight'),
        qn('wp:wrapThrough'), qn('wp:wrapTopAndBottom'),
    }

    for root in roots:
        for drawing in root.findall(f'.//{qn("w:drawing")}'):
            for anchor in list(drawing.findall(qn('wp:anchor'))):
                # 创建 wp:inline
                inline = etree.SubElement(drawing, qn('wp:inline'))
                inline.set('distT', '0')
                inline.set('distB', '0')
                inline.set('distL', '0')
                inline.set('distR', '0')

                # 移动子元素（跳过定位相关的）
                for child in list(anchor):
                    if child.tag not in skip_tags:
                        inline.append(child)

                drawing.remove(anchor)
                count += 1

    logger.info(f'[1.19] 浮动图片转嵌入式: {count} 处')


# =====================================================================
# 阶段三：文本内容清理
# =====================================================================

def rule_1_3_remove_hyperlinks(doc, logger):
    """1.3 删除超链接，保留显示文字"""
    count = 0
    body = doc.element.body

    for hyperlink in body.findall(f'.//{qn("w:hyperlink")}'):
        parent = hyperlink.getparent()
        if parent is None:
            continue

        # 提取超链接中的所有 run
        runs = hyperlink.findall(qn('w:r'))
        insert_pos = list(parent).index(hyperlink)

        # 将 run 移到超链接外面
        for r in runs:
            parent.insert(insert_pos, r)
            insert_pos += 1

        # 删除超链接容器
        parent.remove(hyperlink)
        count += 1

    logger.info(f'[1.3] 删除超链接: {count} 处')


def rule_1_2_remove_field_codes(doc, logger):
    """1.2 删除域代码，保留页码等显示文字
    同时处理正文和页眉页脚中的域代码。
    """
    count = 0
    instr_count = 0
    fldchar_count = 0

    # 收集所有需要搜索的 XML 根元素（正文 + 页眉页脚）
    roots = [doc.element.body]
    for section in doc.sections:
        for part in [section.header, section.footer,
                      section.first_page_header, section.first_page_footer,
                      section.even_page_header, section.even_page_footer]:
            if part is not None:
                roots.append(part._element)

    for root in roots:
        # 删除简单域 w:fldSimple（保留其内部的文字 run）
        for fld in root.findall(f'.//{qn("w:fldSimple")}'):
            parent = fld.getparent()
            if parent is None:
                continue
            runs = fld.findall(qn('w:r'))
            insert_pos = list(parent).index(fld)
            for r in runs:
                parent.insert(insert_pos, r)
                insert_pos += 1
            parent.remove(fld)
            count += 1

        # 删除复杂域（w:fldChar + w:instrText 组合）
        for instr in root.findall(f'.//{qn("w:instrText")}'):
            remove_element(instr)
            instr_count += 1

        for fldchar in root.findall(f'.//{qn("w:fldChar")}'):
            remove_element(fldchar)
            fldchar_count += 1

    count += instr_count + fldchar_count

    logger.info(f'[1.2] 删除域代码: {count} 处 (instrText: {instr_count}, fldChar: {fldchar_count})')


def rule_1_15_16_normalize_punctuation(doc, logger):
    """1.15/1.16 统一标点为半角"""
    count = 0
    body = doc.element.body

    for t in body.findall(f'.//{qn("w:t")}'):
        if t.text and '．' in t.text:
            old = t.text
            t.text = normalize_punctuation(t.text)
            if old != t.text:
                count += 1

    logger.info(f'[1.15/1.16] 标点统一（全角→半角）: {count} 处')


def rule_1_9_normalize_special_symbols(doc, logger):
    """1.9 清理特殊地理符号间距"""
    count = 0
    body = doc.element.body

    for t in body.findall(f'.//{qn("w:t")}'):
        if t.text:
            old = t.text
            t.text = normalize_special_symbols(t.text)
            if old != t.text:
                count += 1

    logger.info(f'[1.9] 清理特殊符号间距: {count} 处')


def rule_1_10_normalize_spacing(doc, logger):
    """1.10 统一中英文间距"""
    count = 0
    body = doc.element.body

    for t in body.findall(f'.//{qn("w:t")}'):
        if t.text:
            old = t.text
            t.text = normalize_cn_en_spacing(t.text)
            if old != t.text:
                count += 1

    logger.info(f'[1.10] 统一中英文间距: {count} 处')


# =====================================================================
# 阶段四：格式和结构清理
# =====================================================================

def rule_1_11_clear_format(doc, logger):
    """1.11 清除段落格式和Run级字体/字号，选择性保留格式标记

    段落级：清除所有格式属性（保留 pStyle 样式引用）
    Run级：清除字体(rFonts)、字号(sz/szCs)、颜色(color)、删除线(strike)
           保留加粗(b)、下划线(u)、着重号(em)、斜体(i)、上下标(vertAlign)
    """
    para_count = 0
    run_count = 0
    body = doc.element.body

    # Run级需要删除的格式属性标签
    RUN_FORMAT_TAGS_TO_REMOVE = ['w:rFonts', 'w:sz', 'w:szCs', 'w:color', 'w:strike',
                                 'w:highlight', 'w:shd', 'w:spacing', 'w:w',
                                 'w:kern', 'w:position', 'w:outlineLvl']

    for p in body.findall(f'.//{qn("w:p")}'):
        # 清除段落格式属性（保留样式引用）
        ppr = p.find(qn('w:pPr'))
        if ppr is not None:
            # 保留 pStyle，删除其他格式
            pstyle = ppr.find(qn('w:pStyle'))
            # 清除所有子元素
            for child in list(ppr):
                ppr.remove(child)
            # 恢复保留的元素
            if pstyle is not None:
                ppr.append(pstyle)
            para_count += 1

        # Run级：选择性删除格式属性
        for r in p.findall(qn('w:r')):
            rpr = r.find(qn('w:rPr'))
            if rpr is not None:
                # 删除指定的格式属性标签
                for tag in RUN_FORMAT_TAGS_TO_REMOVE:
                    for el in rpr.findall(qn(tag)):
                        rpr.remove(el)
                run_count += 1

    logger.info(f'[1.11] 清除段落格式: {para_count} 段, 清除run字体/字号: {run_count} 处(保留加粗/下划线/着重号)')


def rule_1_12_remove_page_breaks(doc, logger):
    """1.12 删除分页符和分节符"""
    br_count = 0
    body = doc.element.body

    # 删除分页符 w:br type="page"
    for br in body.findall(f'.//{qn("w:br")}'):
        br_type = br.get(qn('w:type'))
        if br_type == 'page':
            remove_element(br)
            br_count += 1

    # 删除分栏符 w:br type="column"
    for br in body.findall(f'.//{qn("w:br")}'):
        br_type = br.get(qn('w:type'))
        if br_type == 'column':
            remove_element(br)
            br_count += 1

    # 删除分节符中的分页设置（不删除分节符本身，但清除其分页属性）
    sect_count = 0
    for sectPr in body.findall(f'.//{qn("w:sectPr")}'):
        # 删除 type 属性中的 nextPage 等
        sect_type = sectPr.find(qn('w:type'))
        if sect_type is not None:
            remove_element(sect_type)
            sect_count += 1

    logger.info(f'[1.12] 删除分页符: {br_count} 处, 清除分节符分页设置: {sect_count} 处')


def rule_1_13_remove_empty_paragraphs(doc, logger):
    """1.13 删除空段落和多余换行"""
    removed = 0
    body = doc.element.body

    paragraphs = body.findall(qn('w:p'))

    # 第一轮：删除完全空的段落（无文字、无图片）
    for p in paragraphs:
        text = get_paragraph_text(p).strip()
        has_img = has_drawing(p)

        if not text and not has_img:
            # 检查是否包含表格
            has_table = p.find(qn('w:tbl')) is not None
            if not has_table:
                remove_element(p)
                removed += 1

    # 第二轮：压缩连续空行（最多保留一个空行）
    # 重新获取段落列表
    paragraphs = body.findall(qn('w:p'))
    prev_empty = False
    for p in paragraphs:
        text = get_paragraph_text(p).strip()
        has_img = has_drawing(p)

        if not text and not has_img:
            if prev_empty:
                remove_element(p)
                removed += 1
            else:
                prev_empty = True
        else:
            prev_empty = False

    logger.info(f'[1.13] 删除空段落: {removed} 处')


def rule_1_8_handle_numbering(doc, logger):
    """1.8 处理自动编号（标记为手动输入，不做转换）"""
    count = 0
    body = doc.element.body

    # 删除段落中的 numPr（编号引用），使编号变为手动输入
    for p in body.findall(f'.//{qn("w:p")}'):
        ppr = p.find(qn('w:pPr'))
        if ppr is not None:
            numpr = ppr.find(qn('w:numPr'))
            if numpr is not None:
                ppr.remove(numpr)
                count += 1

    logger.info(f'[1.8] 移除自动编号引用: {count} 处')


# =====================================================================
# 阶段五：元数据清理
# =====================================================================

def rule_1_1_clean_headers_footers(doc, logger):
    """1.1 完全清空页眉页脚内容

    不再依赖品牌关键词匹配，而是清空所有页眉页脚的全部内容
   （段落、表格、图片等）。页码由排版模板（template.dotx）重新生成。

    这样可以彻底消除所有平台来源的水印/logo/广告，
    无需知道试卷来自哪个平台。
    """
    removed = 0
    for section in doc.sections:
        for part_name, part in [('页眉', section.header), ('首页页眉', section.first_page_header),
                                 ('偶数页眉', section.even_page_header),
                                 ('页脚', section.footer), ('首页页脚', section.first_page_footer),
                                 ('偶数页脚', section.even_page_footer)]:
            if part is None:
                continue
            elem = part._element

            # 删除所有段落（w:p）和表格（w:tbl）
            for child in list(elem):
                tag = child.tag
                if tag == qn('w:p') or tag == qn('w:tbl'):
                    elem.remove(child)
                    removed += 1

    logger.info(f'[1.1] 完全清空页眉页脚: 删除{removed}个段落/表格')


def rule_1_14_clean_doc_properties(docx_path, output_path, logger):
    """1.14 清理文档属性中的平台标识信息"""
    # 这个规则需要在保存后对 ZIP 包进行后处理
    # 因为 python-docx 对文档属性的支持有限
    logger.info('[1.14] 文档属性清理将在保存后处理')


def clean_image_descriptions(doc, logger):
    """清理正文中图片描述属性（descr/name）中的品牌关键词。
    这些属性虽然不影响显示，但可能泄露来源信息。
    """
    count = 0
    body = doc.element.body

    for docpr in body.iter(qn('wp:docPr')):
        descr = docpr.get('descr', '') or ''
        name = docpr.get('name', '') or ''
        changed = False

        if any(kw in descr for kw in BRAND_KEYWORDS):
            docpr.set('descr', '')
            changed = True
        if any(kw in name for kw in BRAND_KEYWORDS):
            docpr.set('name', '')
            changed = True

        if changed:
            count += 1

    # 也清理 VML 图片的 alt 属性
    for shape in body.iter(qn('v:shape')):
        alt = shape.get('alt', '') or ''
        if any(kw in alt for kw in BRAND_KEYWORDS):
            shape.set('alt', '')
            count += 1

    if count > 0:
        logger.info(f'[图片描述] 清理品牌关键词: {count} 处')


def clean_docx_properties(docx_path, logger):
    """在 docx 保存后清理文档属性（直接操作 ZIP）"""
    temp_path = docx_path + '.tmp'

    with zipfile.ZipFile(docx_path, 'r') as zin:
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)

                # 清理 core.xml
                if item == 'docProps/core.xml':
                    data = _clean_core_xml(data, logger)
                # 清理 app.xml
                elif item == 'docProps/app.xml':
                    data = _clean_app_xml(data, logger)
                # 清空 comments.xml（保留文件但清空内容，避免关系引用断裂）
                elif 'comments' in item and item.endswith('.xml') and not '_rels' in item:
                    data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
                    logger.info(f'  清空批注文件: {item}')
                # 清空 custom.xml（保留文件但清空内容，避免关系引用断裂）
                elif item == 'docProps/custom.xml':
                    data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/customProperties"/>'
                    logger.info(f'  清空自定义属性: {item}')

                zout.writestr(item, data)

    # 替换原文件
    shutil.move(temp_path, docx_path)


def _clean_core_xml(data, logger):
    """清理 core.xml 中的敏感信息（遍历所有文本节点）"""
    try:
        tree = etree.fromstring(data)
        changed = False

        # 遍历所有元素，清除包含品牌关键词的文本
        for el in tree.iter():
            if el.text and any(kw in el.text for kw in BRAND_KEYWORDS):
                el.text = ''
                changed = True
            # 也检查属性
            for attr_name, attr_val in list(el.attrib.items()):
                if attr_val and any(kw in attr_val for kw in BRAND_KEYWORDS):
                    el.attrib[attr_name] = ''
                    changed = True

        if changed:
            logger.info(f'  清理 core.xml 中的平台标识')
            return etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    except Exception as e:
        logger.warning(f'  清理 core.xml 失败: {e}')

    return data


def _clean_app_xml(data, logger):
    """清理 app.xml 中的敏感信息（遍历所有文本节点）"""
    try:
        tree = etree.fromstring(data)
        changed = False

        for el in tree.iter():
            if el.text and any(kw in el.text for kw in BRAND_KEYWORDS):
                el.text = ''
                changed = True
            for attr_name, attr_val in list(el.attrib.items()):
                if attr_val and any(kw in attr_val for kw in BRAND_KEYWORDS):
                    el.attrib[attr_name] = ''
                    changed = True

        if changed:
            logger.info(f'  清理 app.xml 中的平台标识')
            return etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    except Exception as e:
        logger.warning(f'  清理 app.xml 失败: {e}')

    return data


# =====================================================================
# 主函数
# =====================================================================

def clean_docx(input_path, output_path, log_path=None, rules=None, pending_output_dir=None):
    """执行试卷清洗。

    Args:
        input_path: 输入 docx 文件路径
        output_path: 输出 docx 文件路径
        log_path: 日志文件路径（可选）
        rules: 要执行的规则列表（可选，如 ['1.1', '1.2']，默认全部）
        pending_output_dir: pending_images.json和pending_images文件夹的输出目录（可选）
                           默认使用output_path所在目录，避免在源文件夹生成临时文件
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        print(f'错误: 输入文件不存在: {input_path}')
        return False

    if log_path is None:
        log_path = os.path.join(os.path.dirname(output_path), 'clean_log.txt')

    logger = setup_logger(log_path)

    logger.info('=' * 60)
    logger.info('地理试卷清洗开始')
    logger.info(f'输入文件: {input_path}')
    logger.info(f'输出文件: {output_path}')
    logger.info(f'日志文件: {log_path}')
    logger.info('=' * 60)

    # 判断是否执行全部规则
    run_all = rules is None or len(rules) == 0

    def should_run(rule_id):
        return run_all or rule_id in rules

    try:
        # 加载文档
        doc = Document(input_path)
        logger.info(f'文档加载成功，共 {len(doc.paragraphs)} 个段落')

        # ========== 阶段一：结构性内容清理 ==========
        logger.info('')
        logger.info('--- 阶段一：结构性内容清理 ---')

        if should_run('1.4'):
            rule_1_4_remove_revisions(doc, logger)
        if should_run('1.6'):
            rule_1_6_remove_text_boxes(doc, logger)
        if should_run('1.5'):
            rule_1_5_remove_hidden_text(doc, logger)

        # ========== 阶段二：图片处理 ==========
        logger.info('')
        logger.info('--- 阶段二：图片处理 ---')

        if should_run('1.18'):
            # 优先使用pending_output_dir，否则使用output_path所在目录
            pending_dir = pending_output_dir if pending_output_dir else (os.path.dirname(output_path) or '.')
            replace_image_punctuation(doc, input_path, logger,
                                      output_dir=pending_dir)
        if should_run('1.17'):
            rule_1_17_remove_exam_name_images(doc, logger)
        if should_run('1.7'):
            rule_1_7_vector_images(doc, logger)
        if should_run('1.19'):
            rule_1_19_convert_floating_images(doc, logger)

        # ========== 阶段三：文本内容清理 ==========
        logger.info('')
        logger.info('--- 阶段三：文本内容清理 ---')

        if should_run('1.3'):
            rule_1_3_remove_hyperlinks(doc, logger)
        if should_run('1.2'):
            rule_1_2_remove_field_codes(doc, logger)
        if should_run('1.15') or should_run('1.16'):
            rule_1_15_16_normalize_punctuation(doc, logger)
        if should_run('1.9'):
            rule_1_9_normalize_special_symbols(doc, logger)
        if should_run('1.10'):
            rule_1_10_normalize_spacing(doc, logger)

        # ========== 阶段四：格式和结构清理 ==========
        logger.info('')
        logger.info('--- 阶段四：格式和结构清理 ---')

        if should_run('1.11'):
            rule_1_11_clear_format(doc, logger)
        if should_run('1.12'):
            rule_1_12_remove_page_breaks(doc, logger)
        if should_run('1.13'):
            rule_1_13_remove_empty_paragraphs(doc, logger)
        if should_run('1.8'):
            rule_1_8_handle_numbering(doc, logger)

        # ========== 阶段五：元数据清理 ==========
        logger.info('')
        logger.info('--- 阶段五：元数据清理 ---')

        # 清理图片描述属性中的品牌关键词
        clean_image_descriptions(doc, logger)

        if should_run('1.1'):
            rule_1_1_clean_headers_footers(doc, logger)

        # 保存文档
        logger.info('')
        logger.info('--- 保存文档 ---')
        doc.save(output_path)
        logger.info(f'文档已保存: {output_path}')

        # 后处理：清理文档属性
        if should_run('1.14'):
            clean_docx_properties(output_path, logger)

        logger.info('')
        logger.info('=' * 60)
        logger.info('清洗完成！')
        logger.info(f'输出文件: {output_path}')
        logger.info(f'日志文件: {log_path}')
        logger.info('=' * 60)

        return True

    except Exception as e:
        logger.error(f'清洗过程中出错: {e}', exc_info=True)
        print(f'错误: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='地理试卷清洗脚本 - 清理从学科网等平台下载的试卷文档',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python clean_docx.py --input "试卷.docx" --output "cleaned.docx"
  python clean_docx.py --input "试卷.docx" --output "cleaned.docx" --rules 1.15,1.16
        '''
    )
    parser.add_argument('--input', '-i', required=True, help='输入 docx 文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出 docx 文件路径')
    parser.add_argument('--log', '-l', help='日志文件路径（默认与输出文件同目录）')
    parser.add_argument('--rules', '-r', help='指定规则编号（逗号分隔，如 1.1,1.2,1.15）')
    parser.add_argument('--pending-dir', '-p', help='pending_images.json输出目录（可选，默认与输出文件同目录）')

    args = parser.parse_args()

    rules = args.rules.split(',') if args.rules else None

    success = clean_docx(args.input, args.output, args.log, rules, args.pending_dir)

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
