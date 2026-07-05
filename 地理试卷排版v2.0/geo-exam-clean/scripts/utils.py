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
