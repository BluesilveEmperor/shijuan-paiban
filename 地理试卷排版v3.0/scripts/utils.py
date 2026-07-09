# -*- coding: utf-8 -*-
"""
地理试卷清洗 - 公共工具函数
提供 docx XML 操作、日志记录、媒体文件信息等通用功能。
"""

import logging
import os
import re
import struct
import zipfile
from lxml import etree

# Word XML 命名空间
NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'v': 'urn:schemas-microsoft-com:vml',
    'o': 'urn:schemas-microsoft-com:office:office',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
}


def qn(tag):
    """将命名空间前缀标签转换为完整 URI 标签。
    例：qn('w:p') -> '{http://...main}p'
    """
    prefix, local = tag.split(':')
    return f'{{{NSMAP[prefix]}}}{local}'


def setup_logger(log_path):
    """创建并配置日志记录器。"""
    logger = logging.getLogger('geo_exam_clean')
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    fh = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(sh)

    return logger


def get_paragraph_text(p_element):
    """从段落 XML 元素中提取纯文本（不含标签）。
    p_element: <w:p> 的 lxml 元素
    """
    texts = []
    for t in p_element.iter(qn('w:t')):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


def get_run_text(r_element):
    """从 run XML 元素中提取纯文本。"""
    texts = []
    for t in r_element.iter(qn('w:t')):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


def remove_element(element):
    """安全删除 XML 元素（从父节点中移除）。"""
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def find_all(parent, tag):
    """在父元素下查找所有匹配标签的元素。"""
    return parent.findall(f'.//{qn(tag)}')


def get_media_info(docx_path):
    """读取 docx 中的媒体文件信息。
    返回字典: {文件路径: {size: 文件大小, ext: 扩展名}}
    """
    media = {}
    with zipfile.ZipFile(docx_path, 'r') as z:
        for name in z.namelist():
            if 'media/' in name and not name.endswith('/'):
                info = z.getinfo(name)
                ext = os.path.splitext(name)[1].lower()
                media[name] = {'size': info.file_size, 'ext': ext}
    return media


def get_image_relationships(docx_path):
    """读取 docx 中图片关系映射。
    返回字典: {rId: media文件路径}
    """
    rels = {}
    with zipfile.ZipFile(docx_path, 'r') as z:
        try:
            with z.open('word/_rels/document.xml.rels') as f:
                content = f.read()
            tree = etree.fromstring(content)
            for rel in tree:
                rid = rel.get('Id')
                target = rel.get('Target')
                if target and ('image' in target or 'media' in target):
                    if not target.startswith('word/'):
                        target = 'word/' + target
                    rels[rid] = target
        except KeyError:
            pass
    return rels


def get_image_size_by_rid(docx_path, rid):
    """根据关系ID获取图片文件大小。"""
    rels = get_image_relationships(docx_path)
    media_path = rels.get(rid)
    if not media_path:
        return 0
    with zipfile.ZipFile(docx_path, 'r') as z:
        try:
            info = z.getinfo(media_path)
            return info.file_size
        except KeyError:
            return 0


def is_hidden_run(r_element):
    """检查 run 是否设为隐藏属性。"""
    rpr = r_element.find(qn('w:rPr'))
    if rpr is not None:
        vanish = rpr.find(qn('w:vanish'))
        if vanish is not None:
            return True
    return False


def normalize_cn_en_spacing(text):
    """统一中英文间距。
    规则：
    - 中文与英文/数字之间统一加一个空格
    - 连续多个空格压缩为一个
    - 行首行尾的空格删除
    """
    if not text:
        return text

    # 中文与英文/数字之间加空格
    text = re.sub(r'([\u4e00-\u9fff])([A-Za-z0-9])', r'\1 \2', text)
    text = re.sub(r'([A-Za-z0-9])([\u4e00-\u9fff])', r'\1 \2', text)

    # 但有些情况不应该加空格（如选项"A. xxx"中的A和.之间）
    # 这里的规则是：单个字母后紧跟标点时不加空格
    # 上面正则不会匹配这种情况，因为标点不在[A-Za-z0-9]范围内

    # 压缩多个空格为一个
    text = re.sub(r' {2,}', ' ', text)

    # 删除行首行尾空格
    text = text.strip()

    return text


def normalize_special_symbols(text):
    """清理特殊地理符号间距。
    如 "29 ° 52'S" -> "29°52'S"
    """
    if not text:
        return text

    # 度分秒符号：删除符号前后的空格
    text = re.sub(r'\s*°\s*', '°', text)
    text = re.sub(r'\s*′\s*', '′', text)
    text = re.sub(r'\s*″\s*', '″', text)

    # 经纬度中的度分秒：如 "29° 52'S" -> "29°52'S"
    text = re.sub(r'°\s+(\d)', r'°\1', text)

    return text


def normalize_punctuation(text):
    """统一标点为半角。
    全角"．" -> 半角"."
    """
    if not text:
        return text

    # 全角句点转半角
    text = text.replace('．', '.')

    return text


def has_drawing(p_element):
    """检查段落中是否包含图片（drawing 或 VML 图片）。"""
    for child in p_element.iter():
        tag = child.tag
        if tag == qn('w:drawing') or tag == qn('v:imagedata') or tag == qn('v:shape'):
            return True
    return False


def get_drawings(p_element):
    """获取段落中的所有图片元素。"""
    drawings = []
    for child in p_element.iter():
        if child.tag == qn('w:drawing'):
            drawings.append(child)
        elif child.tag == qn('v:imagedata'):
            drawings.append(child)
    return drawings


def get_embed_rid(drawing_element):
    """从图片元素中获取关系ID（r:embed 或 r:id）。"""
    # inline 或 anchor 图片
    for blip in drawing_element.iter(qn('a:blip')):
        rid = blip.get(f'{{{NSMAP["r"]}}}embed')
        if rid:
            return rid
    # VML 图片
    if drawing_element.tag == qn('v:imagedata'):
        rid = drawing_element.get(f'{{{NSMAP["r"]}}}id')
        if rid:
            return rid
    return None


# =====================================================================
# docx → Markdown 转换
# =====================================================================

def docx_to_markdown(docx_path, md_path, image_manifest_path=None):
    """将 docx 文件转换为 Markdown 文本文件。

    遍历每个段落和表格，逐字处理以保留：
    - 上标：用 <sup>...</sup> 包裹
    - 下标：用 <sub>...</sub> 包裹
    - 图片位置：若提供 image_manifest.json，在对应位置插入 {{symbol:img_xxx}} 标记
    - 表格：转换为 Markdown 表格格式（|列1|列2|...|），便于后续结构识别

    Args:
        docx_path: 输入 docx 文件路径（通常为 cleaned_no_images.docx）
        md_path: 输出 Markdown 文件路径
        image_manifest_path: image_manifest.json 路径（可选），用于标记图片位置

    Returns:
        int: 输出的段落数（含表格块数）
    """
    from docx import Document
    from docx.oxml.ns import qn as docx_qn
    import json

    doc = Document(docx_path)

    # 获取文档的 body 元素，以便按 XML 顺序遍历段落和表格
    body = doc.element.body

    # 如果提供了 image_manifest，加载图片信息并按段落实例分组
    img_by_para = {}
    if image_manifest_path and os.path.exists(image_manifest_path):
        with open(image_manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        for img in manifest.get('images', []):
            para_idx = img.get('paragraph_index', -1)
            run_idx = img.get('run_index', -1)
            img_id = img.get('image_id', '')
            file_size = img.get('file_size', 0)
            if para_idx >= 0:
                if para_idx not in img_by_para:
                    img_by_para[para_idx] = []
                img_by_para[para_idx].append({
                    'run_idx': run_idx,
                    'img_id': img_id,
                    'file_size': file_size,
                })

    blocks = []  # 存储所有内容块（段落文本或表格 Markdown）
    para_count = 0  # 段落计数器（用于图片定位）
    table_count = 0  # 表格计数器

    # 遍历 body 中的所有子元素（段落和表格），保持原始顺序
    for child_idx, child in enumerate(body):
        tag = child.tag
        
        # 处理段落
        if tag == qn('w:p'):
            para_text_parts = []
            p_elem = child
            runs = p_elem.findall(qn('w:r'))
            
            # 跟踪当前 run 索引（用于图片定位）
            current_run_idx = 0
            
            for r_elem in runs:
                # 检查是否该位置有图片标记（基于 image_manifest 中的 run_index）
                if para_count in img_by_para:
                    for img_info in img_by_para[para_count]:
                        if img_info['run_idx'] == current_run_idx:
                            # 仅小图片 (< 2KB) 可能是符号截图，插入标记
                            # 大图片是正常内容图片，不在此处标记（由 Step3 tag_placeholders 处理）
                            if img_info['file_size'] < 2048:
                                para_text_parts.append(f'{{{{symbol:{img_info["img_id"]}}}}}')
                
                # 提取 run 中的文本，并检测上下标
                rpr = r_elem.find(qn('w:rPr'))
                is_superscript = False
                is_subscript = False
                if rpr is not None:
                    vertAlign = rpr.find(qn('w:vertAlign'))
                    if vertAlign is not None:
                        val = vertAlign.get(qn('w:val'))
                        if val == 'superscript':
                            is_superscript = True
                        elif val == 'subscript':
                            is_subscript = True
                
                # 提取该 run 中所有 w:t 元素的文本
                t_elements = r_elem.findall(qn('w:t'))
                run_text = ''
                for t in t_elements:
                    if t.text:
                        run_text += t.text
                
                if run_text:
                    if is_superscript:
                        para_text_parts.append(f'<sup>{run_text}</sup>')
                    elif is_subscript:
                        para_text_parts.append(f'<sub>{run_text}</sub>')
                    else:
                        para_text_parts.append(run_text)
                
                current_run_idx += 1
            
            para_text = ''.join(para_text_parts)
            if para_text is not None:
                para_text = para_text.rstrip()
            else:
                para_text = ''
            
            # 只添加非空段落（或空段落保留换行）
            blocks.append(para_text)
            para_count += 1
        
        # 处理表格
        elif tag == qn('w:tbl'):
            table_md = _table_to_markdown(child)
            if table_md:
                blocks.append(table_md)
                table_count += 1

    # 以双换行分隔段落（Markdown 标准段落分隔）
    content = '\n\n'.join(blocks)

    # 确保目录存在
    os.makedirs(os.path.dirname(md_path) or '.', exist_ok=True)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return para_count + table_count


def _table_to_markdown(tbl_element):
    """将 Word 表格元素（w:tbl）转换为 Markdown 表格格式。
    
    Args:
        tbl_element: lxml Element，代表 <w:tbl> 元素
    
    Returns:
        str: Markdown 表格文本，或空字符串（如果表格为空）
    """
    rows = []
    
    # 遍历表格中的所有行
    for tr in tbl_element.findall(qn('w:tr')):
        cells = []
        # 遍历行中的所有单元格
        for tc in tr.findall(qn('w:tc')):
            # 提取单元格中的所有段落文本
            cell_text_parts = []
            for p in tc.findall(qn('w:p')):
                # 提取段落中的所有 w:t 元素
                for t in p.findall('.//' + qn('w:t')):
                    if t.text:
                        cell_text_parts.append(t.text)
            cell_text = ' '.join(cell_text_parts).strip()
            cells.append(cell_text)
        
        if cells:
            rows.append(cells)
    
    if not rows:
        return ''
    
    # 确定列数（取最大列数）
    max_cols = max(len(row) for row in rows) if rows else 0
    
    # 构建 Markdown 表格
    md_lines = []
    
    # 表头行（第一行）
    if rows:
        header = rows[0]
        # 补齐列数
        while len(header) < max_cols:
            header.append('')
        md_lines.append('| ' + ' | '.join(header) + ' |')
        
        # 分隔线
        md_lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
        
        # 数据行（从第二行开始）
        for row in rows[1:]:
            # 补齐列数
            while len(row) < max_cols:
                row.append('')
            md_lines.append('| ' + ' | '.join(row) + ' |')
    
    return '\n'.join(md_lines)


# =====================================================================
# 未解析符号图片检测
# =====================================================================

def check_pending_symbols(cleaned_dir, content_md_path=None):
    """检查 image_manifest.json 中是否存在可能为特殊符号的小图片。

    在试卷清洗流程中，clean_docx.py 的 replace_image_punctuation() 会尝试
    提取 WMF/EMF 矢量图片中的文字（标点、符号等），无法提取的写入
    pending_images.json。extract_images.py 提取所有图片后，这些未解析的
    小图片会从正文中消失——但它们可能是经纬度符号（°′″）、化学式片段、
    教师截图插入的特殊符号等。

    本函数：
    1. 读取 pending_images.json，获取未解析的图片列表
    2. 通过 original_media_path 交叉索引 image_manifest.json
    3. 筛选 image_manifest 中 < 2KB 的图片（直接嵌入的小图）
    4. 合并两者，生成 symbols_report.md 供 AI 和人工审查

    Args:
        cleaned_dir: 清洗输出目录（含 image_manifest.json 和 pending_images.json）
        content_md_path: content.md 路径（可选），用于在正文中标记位置

    Returns:
        dict: {
            'small_images_count': int,
            'pending_count': int,
            'report_path': str,
            'warnings': [str]
        }
    """
    import json

    image_manifest_path = os.path.join(cleaned_dir, 'image_manifest.json')
    pending_path = os.path.join(cleaned_dir, 'pending_images.json')

    if not os.path.exists(image_manifest_path):
        return {
            'small_images_count': 0,
            'pending_count': 0,
            'report_path': '',
            'warnings': ['image_manifest.json 不存在，无法检查']
        }

    with open(image_manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # 加载 pending_images（通过 original_media_path 快速查找）
    pending_images = {}
    if os.path.exists(pending_path):
        with open(pending_path, 'r', encoding='utf-8') as f:
            pending_data = json.load(f)
        for p in pending_data.get('pending_images', []):
            pending_images[p.get('original_media_path', '')] = p

    # 构建疑似符号图片列表（合并两种来源）：
    #   a) image_manifest 中 < 2KB 的小图
    #   b) pending_images 中通过 original_media_path 匹配到的图片
    symbol_images = {}  # key: img_id, value: info dict

    for img in manifest.get('images', []):
        img_id = img.get('image_id', '')
        original_path = img.get('original_media_path', '')
        file_size = img.get('file_size', 0)
        context_before = img.get('context_before', '')[:30]
        context_after = img.get('context_after', '')[:30]

        is_pending = original_path in pending_images
        is_small = file_size < 2048

        if is_pending or is_small:
            symbol_images[img_id] = {
                'image_id': img_id,
                'image_file': img.get('image_file', ''),
                'file_size': file_size,
                'context_before': context_before,
                'context_after': context_after,
                'is_pending': is_pending,
                'is_small': is_small,
                'paragraph_text': img.get('paragraph_text', '')[:80],
                'paragraph_index': img.get('paragraph_index', -1),
            }

    # 生成报告
    warnings = []
    report_lines = [
        '# 符号图片检查报告',
        '',
        f'生成时间：{__import__("datetime").datetime.now().isoformat()}',
        '',
        '## 概览',
        '',
        f'- 图片总数：{manifest.get("total_images", 0)}',
        f'- 疑似符号图片：{len(symbol_images)}（其中未解析 pending: {len(pending_images)}）',
        '',
    ]

    if not symbol_images:
        report_lines.append('未发现疑似符号图片，无需关注。')
        if pending_images:
            report_lines.append('')
            report_lines.append(f'注意：`pending_images.json` 中有 {len(pending_images)} 条未解析记录，')
            report_lines.append('但这些图片可能已在清洗阶段被其他规则（如规则1.17"删除考试名称前图片"）处理，')
            report_lines.append('或在 `clean_docx` → `extract_images` 过程中被合并/重新编号，')
            report_lines.append('未在最终的 `image_manifest.json` 中出现匹配项。')
            report_lines.append('如果转换后的正文完整无缺字，可忽略此提示。')
        warnings.append('无符号图片')
    else:
        report_lines.append('## 疑似符号图片详情')
        report_lines.append('')
        report_lines.append('以下图片可能需要关注：')
        report_lines.append('')
        report_lines.append('| 图片ID | 文件 | 大小 | 上文 | 下文 | 标记 | 所在段落（片段）|')
        report_lines.append('|--------|------|------|------|------|------|------------------|')

        small_imgs_for_marking = []

        for img_id, info in symbol_images.items():
            tags = []
            if info['is_pending']:
                tags.append('未解析')
            if info['is_small']:
                tags.append('小图')
            tag_str = ' '.join(tags)

            report_lines.append(
                f'| {img_id} | {info["image_file"]} | {info["file_size"]}B | '
                f'{info["context_before"]} | {info["context_after"]} | {tag_str} | '
                f'{info["paragraph_text"]} |'
            )

            if info['is_pending']:
                warnings.append(
                    f'{img_id}: 上文="{info["context_before"]}" 下文="{info["context_after"]}" '
                    f'— 未解析的符号图片，请在转换后的正文中检查此处是否缺字'
                )
            elif info['is_small']:
                warnings.append(
                    f'{img_id}: 上文="{info["context_before"]}" 下文="{info["context_after"]}" '
                    f'— 小图片（{info["file_size"]}B），可能是符号截图'
                )

            # 收集可用于标记的图片
            if info['context_before'].strip() or info['context_after'].strip():
                small_imgs_for_marking.append({
                    'img_id': img_id,
                    'context_before': info['context_before'].strip(),
                    'context_after': info['context_after'].strip(),
                })

        report_lines.append('')
        report_lines.append('## 建议操作')
        report_lines.append('')
        report_lines.append('1. 查看上述图片的上下文，判断缺失的是什么符号/文字')
        report_lines.append('2. 打开 `images/` 目录下对应图片，人工识别符号内容')
        report_lines.append('3. 在 content.md 中将 `{{symbol:img_xxx}}` 替换为实际符号文字')
        report_lines.append('4. 如果图片确实是试卷内容图片（如地图），标记为 `非符号` 并忽略')

    # 如果提供了 content.md，尝试在正文中标记符号位置
    if content_md_path and os.path.exists(content_md_path) and symbol_images:
        _mark_symbol_positions_in_md(content_md_path, [
            {'image_id': k, 'context_before': v['context_before'], 'context_after': v['context_after']}
            for k, v in symbol_images.items()
        ])

    # 写入报告
    report_path = os.path.join(cleaned_dir, 'symbols_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    return {
        'small_images_count': len(symbol_images),
        'pending_count': len(pending_images),
        'report_path': report_path,
        'warnings': warnings
    }


def _mark_symbol_positions_in_md(content_md_path, small_images):
    """在 content.md 中用 {{symbol:img_xxx}} 标记符号图片位置。

    基于 image_manifest 中的 context_before/context_after 字段，
    在正文中定位并插入标记。

    Args:
        content_md_path: content.md 文件路径
        small_images: 小图片信息列表
    """
    # 只标记上下文信息明确的小图片（有 context_before 或 context_after）
    markable = [
        img for img in small_images
        if (img.get('context_before', '').strip() or img.get('context_after', '').strip())
    ]

    if not markable:
        return

    with open(content_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    modified = False
    for img in markable:
        img_id = img.get('image_id', '')
        context_before = img.get('context_before', '').strip()
        context_after = img.get('context_after', '').strip()

        # 策略：在 content 中查找上下文配对位置，插入标记
        # 优先用 before+after 定位
        marker = f'{{{{symbol:{img_id}}}}}'

        if context_before and context_after:
            # 同时有前后文：在两者之间插入
            search = context_before + context_after
            if search in content:
                pos = content.find(search)
                insert_pos = pos + len(context_before)
                content = content[:insert_pos] + marker + content[insert_pos:]
                modified = True
                continue

        if context_before:
            # 只有前文：在之后插入
            if context_before in content:
                pos = content.find(context_before) + len(context_before)
                # 避免重复标记
                if marker not in content[max(0, pos-50):pos+50]:
                    content = content[:pos] + marker + content[pos:]
                    modified = True
                continue

        if context_after:
            # 只有后文：在之前插入
            if context_after in content:
                pos = content.find(context_after)
                if marker not in content[max(0, pos-50):pos+len(context_after)+50]:
                    content = content[:pos] + marker + content[pos:]
                    modified = True

    if modified:
        with open(content_md_path, 'w', encoding='utf-8') as f:
            f.write(content)


def insert_text_before_element(element, text):
    """在指定元素前插入文字 run。
    创建一个 <w:r><w:t>text</w:t></w:r> 并插入到 element 之前。
    """
    parent = element.getparent()
    if parent is None:
        return

    r = etree.SubElement(parent, qn('w:r'))
    t = etree.SubElement(r, qn('w:t'))
    t.text = text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

    # 将新创建的元素移动到目标元素之前
    parent.remove(r)
    parent.insert(list(parent).index(element), r)


def count_elements(doc, tag):
    """统计文档中某类元素的数量。"""
    body = doc.element.body
    count = 0
    for el in body.iter(qn(tag)):
        count += 1
    return count


def get_section_text(section_part):
    """从页眉/页脚的 XML 元素中提取文本。"""
    texts = []
    for t in section_part.iter(qn('w:t')):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


# =====================================================================
# WMF/EMF 矢量图片文本提取
# =====================================================================

def read_media_file(docx_path, media_path):
    """从 docx ZIP 包中读取媒体文件的二进制数据。

    Args:
        docx_path: docx 文件路径
        media_path: 媒体文件在 ZIP 中的路径（如 word/media/image6.wmf）

    Returns:
        bytes: 文件二进制数据，文件不存在时返回 None
    """
    with zipfile.ZipFile(docx_path, 'r') as z:
        try:
            return z.read(media_path)
        except KeyError:
            return None


def extract_text_from_wmf(data):
    """从 WMF 二进制数据中提取嵌入的文本。

    学科网等平台下载的试卷中，标点符号和单个汉字常以 WMF 矢量图片形式
    嵌入（由 MathType 生成）。这些 WMF 文件内部包含两种可提取的文本：

    1. EXTTEXTOUT 记录（0x0A32）：包含 GBK 编码的文本数据
       - ASCII 字符（如 "."）占 1 字节
       - 中文字符（如 "的"）占 2 字节（GBK 双字节编码）
    2. 末尾嵌入的 MathML XML：<mo>（运算符）、<mi>（标识符）标签

    本函数优先使用 EXTTEXTOUT 提取（更直接），失败时回退到 MathML。

    Args:
        data: WMF 文件的二进制数据

    Returns:
        str: 提取的文本（如 "." 或 "的"）；无法提取时返回 None
    """
    if not data or len(data) < 40:
        return None

    # 方法1：解析 EXTTEXTOUT 记录
    text = _extract_wmf_exttextout(data)
    if text:
        return text

    # 方法2：搜索 MathML XML（回退方案）
    text = _extract_wmf_mathml(data)
    if text:
        return text

    return None


def _extract_wmf_exttextout(data):
    """解析 WMF 的 EXTTEXTOUT 记录，提取 GBK 编码的文本。"""
    texts = []

    # 跳过 Placeable Header（22字节，以 0x9AC6CDD7 开头）
    offset = 0
    if len(data) >= 4:
        key = struct.unpack_from('<I', data, 0)[0]
        if key == 0x9AC6CDD7:
            offset = 22

    # 跳过 WMF Header（18字节）
    offset += 18

    while offset + 6 <= len(data):
        try:
            rec_size = struct.unpack_from('<I', data, offset)[0]  # 以字（2字节）为单位
            rec_func = struct.unpack_from('<H', data, offset + 4)[0]
        except struct.error:
            break

        # 安全检查：防止异常数据导致死循环
        if rec_size == 0 or rec_size > 100000:
            break

        rec_data_start = offset + 6
        rec_data_size = (rec_size - 3) * 2  # 记录数据大小（字节）

        if rec_func == 0x0A32:  # META_EXTTEXTOUT
            # 结构: y(2) x(2) str_len(2) options(2) [rect(8)] string dx_array
            if rec_data_start + 8 <= len(data):
                str_len = struct.unpack_from('<H', data, rec_data_start + 4)[0]
                options = struct.unpack_from('<H', data, rec_data_start + 6)[0]

                str_offset = rec_data_start + 8
                # ETO_CLIPPED (0x0004) 表示有 8 字节矩形区域
                if options & 0x0004:
                    str_offset += 8

                if str_len > 0 and str_offset < len(data):
                    # 计算字符串的字节长度
                    # dx 数组大小 = str_len * 2 字节（每个 dx 条目为 int16）
                    header_bytes = str_offset - rec_data_start
                    dx_size = str_len * 2
                    string_byte_length = rec_data_size - header_bytes - dx_size

                    # 如果计算结果异常（无 dx 数组），使用剩余空间
                    if string_byte_length <= 0:
                        string_byte_length = rec_data_size - header_bytes

                    # 限制读取范围，防止越界
                    string_byte_length = min(string_byte_length, len(data) - str_offset)
                    if string_byte_length <= 0:
                        continue

                    raw_bytes = data[str_offset:str_offset + string_byte_length]

                    # 尝试 GBK 解码（GBK 兼容 ASCII，能正确处理混合内容）
                    try:
                        text = raw_bytes.decode('gbk', errors='ignore').strip('\x00').strip()
                        if text:
                            texts.append(text)
                    except Exception:
                        pass

        # 移动到下一条记录
        offset += rec_size * 2

    if texts:
        return ''.join(texts)

    return None


def _extract_wmf_mathml(data):
    """从 WMF 末尾搜索并解析 MathML XML，提取文本。"""
    try:
        # 查找 <math 标签
        math_start = data.find(b'<math')
        if math_start < 0:
            return None

        math_end = data.find(b'</math>', math_start)
        if math_end < 0:
            return None

        mathml_bytes = data[math_start:math_end + 7]
        mathml = mathml_bytes.decode('utf-8', errors='ignore')

        # 解析 MathML XML
        tree = etree.fromstring(mathml)
        math_texts = []
        for elem in tree.iter():
            # 提取 <mo>（运算符）、<mi>（标识符）、<mn>（数字）中的文本
            tag = elem.tag
            if tag.endswith('}mo') or tag.endswith('}mi') or tag.endswith('}mn'):
                if elem.text:
                    math_texts.append(elem.text)

        if math_texts:
            return ''.join(math_texts)
    except Exception:
        pass

    return None
