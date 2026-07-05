# -*- coding: utf-8 -*-
"""
地理试卷打标 - 公共工具函数
提供段落类型识别、正则模式、图片提取等通用功能。
"""

import logging
import os
import re
import zipfile
import io
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
}


def qn(tag):
    """将命名空间前缀标签转换为完整 URI 标签。"""
    prefix, local = tag.split(':')
    return f'{{{NSMAP[prefix]}}}{local}'


def setup_logger(log_path):
    """创建并配置日志记录器。"""
    logger = logging.getLogger('geo_exam_tag')
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
    """从段落 XML 元素中提取纯文本。"""
    texts = []
    for t in p_element.iter(qn('w:t')):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


def has_drawing(p_element):
    """检查段落中是否包含图片。"""
    for child in p_element.iter():
        tag = child.tag
        if tag == qn('w:drawing') or tag == qn('v:imagedata'):
            return True
    return False


def get_drawings(p_element):
    """获取段落中的所有图片元素。"""
    drawings = []
    for child in p_element.iter():
        if child.tag == qn('w:drawing'):
            drawings.append(child)
    return drawings


def get_embed_rid(drawing_element):
    """从图片元素中获取关系ID。"""
    for blip in drawing_element.iter(qn('a:blip')):
        rid = blip.get(f'{{{NSMAP["r"]}}}embed')
        if rid:
            return rid
    return None


# =====================================================================
# 正则模式定义
# =====================================================================

# 分区标题：一、二、三、四、五、六、七、八、九、十
SECTION_PATTERN = re.compile(r'^[一二三四五六七八九十]+、')

# 非选择题分区（必须在选择题之前检查，因为"非选择题"包含"选择题"）
NON_CHOICE_SECTION_PATTERN = re.compile(r'^[一二三四五六七八九十]+、.*非选择题')

# 选择题分区（排除"非选择题"的情况：以"选"开头但不是"非选"）
CHOICE_SECTION_PATTERN = re.compile(r'^[一二三四五六七八九十]+、选.*择题')

# 填空题分区
FILL_SECTION_PATTERN = re.compile(r'^[一二三四五六七八九十]+、.*填空题')

# 题号：1. 2. 10. 16. 等（半角点号，清洗后统一为半角）
QUESTION_NUMBER_PATTERN = re.compile(r'^(\d+)\.\s*(.*)')

# 选项：A. B. C. D.（半角点号）
OPTION_PATTERN = re.compile(r'^([ABCD])\.\s*(.*)')

# 同行多选项：A.xxx B.xxx C.xxx D.xxx
MULTI_OPTION_PATTERN = re.compile(r'([ABDC])\.\s*')

# 子选项：①②③④⑤等（匹配行首，允许前导空格）
SUB_OPTION_PATTERN = re.compile(r'^\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]')

# 子选项拆分：匹配所有圈码+后续内容（到下一个圈码为止）
SUB_OPTION_SPLIT_PATTERN = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮][^①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑮]*')

# 子问题编号：（1）（2）(1)(2)
SUB_QUESTION_PATTERN = re.compile(r'^[（(]\d+[）)]\s*(.*)')

# 考试名称关键词
EXAM_KEYWORDS = ['考试', '学业水平', '高考', '招生', '统考']

# 非选择题标题关键词
NON_CHOICE_TITLE_KEYWORDS = ['阅读', '完成', '回答', '作答', '读图', '读材料']

# 引导语
INSTRUCTION_KEYWORDS = ['据此完成', '完成下面', '完成下列', '回答下列', '按要求作答']

# 非选择题子问题动词关键词（用于区分材料和子问题）
QUESTION_VERB_KEYWORDS = [
    '说明', '分析', '描述', '判断', '提出', '指出', '简述', '阐述',
    '解释', '比较', '评价', '列举', '归纳', '概括', '总结', '论证',
    '说明理由', '提出建议', '计算', '绘制', '设计', '规划', '评价',
    '分析原因', '分析影响', '说明原因', '说明影响', '分析条件',
    '分别说明', '分别分析', '分别描述', '分别判断',
]


# =====================================================================
# 段落类型判断函数
# =====================================================================

def is_section_header(text):
    """判断是否为分区标题（如"一、选择题：..."）"""
    return bool(SECTION_PATTERN.match(text))


def is_choice_section(text):
    """判断是否为选择题分区标题"""
    return bool(CHOICE_SECTION_PATTERN.match(text))


def is_non_choice_section(text):
    """判断是否为非选择题分区标题"""
    return bool(NON_CHOICE_SECTION_PATTERN.match(text))


def is_fill_section(text):
    """判断是否为填空题分区标题"""
    return bool(FILL_SECTION_PATTERN.match(text))


def is_question_stem(text):
    """判断是否为题干（以"数字."开头）"""
    return bool(QUESTION_NUMBER_PATTERN.match(text))


def is_option(text):
    """判断是否为选项（以A./B./C./D.开头）"""
    return bool(OPTION_PATTERN.match(text))


def is_sub_option(text):
    """判断是否为子选项（以①②③④开头，允许前导空格）"""
    return bool(SUB_OPTION_PATTERN.match(text))


def contains_sub_option(text):
    """判断文本中是否包含子选项标记（①②③④等）。
    
    用于检测同行多子选项的情况，如"①XXXX②XXXXX③XXXXX"。
    """
    return bool(SUB_OPTION_SPLIT_PATTERN.search(text))


def split_sub_options(text):
    """将同行多子选项拆分为列表。
    
    示例:
        "①XXXX②XXXXX③XXXXX④XXXXX⑤XXXXX"
        → ["①XXXX", "②XXXXX", "③XXXXX", "④XXXXX", "⑤XXXXX"]
    
    也处理前导有空格的情况:
        "  ①苹果②香蕉③橙子"
        → ["①苹果", "②香蕉", "③橙子"]
    """
    return SUB_OPTION_SPLIT_PATTERN.findall(text)


def is_sub_question(text):
    """判断是否为子问题（以（1）（2）开头）"""
    return bool(SUB_QUESTION_PATTERN.match(text))


def is_instruction(text):
    """判断是否为引导语（如"据此完成下面小题。"）"""
    return any(kw in text for kw in INSTRUCTION_KEYWORDS) and len(text) < 30


def extract_instruction(material_text):
    """从材料文本中提取引导语。
    
    材料末尾可能包含引导语（如"据此完成下面小题。"），
    需要将其分离出来。
    
    返回: (材料文本, 引导语) 或 (原文本, '')
    """
    for kw in INSTRUCTION_KEYWORDS:
        idx = material_text.find(kw)
        if idx >= 0:
            # 找到引导语开始位置，向后找到句号结束
            end = material_text.find('。', idx)
            if end >= 0:
                instruction = material_text[idx:end + 1]
                # 分离材料文本
                before = material_text[:idx].rstrip()
                # 去掉材料前的换行和空格
                before = before.rstrip('\n').rstrip()
                return before, instruction
            else:
                # 没有句号，取到文本末尾
                instruction = material_text[idx:].strip()
                before = material_text[:idx].rstrip()
                return before, instruction
    return material_text, ''


def is_question_text(text):
    """判断文本是否为非选择题的子问题（而非材料）。
    
    启发式规则：
    1. 以子问题编号开头（（1）（2））：是子问题
    2. 包含问题动词关键词：是子问题
    3. 其他情况：是材料
    """
    if is_sub_question(text):
        return True
    # 检查是否包含问题动词关键词
    for kw in QUESTION_VERB_KEYWORDS:
        if kw in text:
            return True
    return False


def is_exam_info(text):
    """判断是否为考试信息段落"""
    return any(kw in text for kw in EXAM_KEYWORDS)


def is_non_choice_title(text):
    """判断是否为非选择题标题（如"16.阅读图文材料，完成下列要求。"）"""
    match = QUESTION_NUMBER_PATTERN.match(text)
    if match:
        rest = match.group(2)
        return any(kw in rest for kw in NON_CHOICE_TITLE_KEYWORDS)
    return False


def get_question_number(text):
    """从题干文本中提取题号。
    返回 (题号:int, 题干内容:str) 或 None。
    """
    match = QUESTION_NUMBER_PATTERN.match(text)
    if match:
        return int(match.group(1)), match.group(2)
    return None


def parse_options(text):
    """解析选项文本，返回 {A: content, B: content, ...}。
    
    处理两种情况：
    1. 单个选项一行："A.人口年龄结构趋年轻化"
    2. 多个选项一行："A.xxx   B.xxx   C.xxx   D.xxx"
    """
    options = {}
    
    # 先尝试单选项
    match = OPTION_PATTERN.match(text)
    if match:
        letter = match.group(1)
        content = match.group(2).strip()
        # 检查内容中是否还有其他选项（如"A.xxx B.xxx"）
        # 用正则查找所有选项标记
        remaining = content
        parts = re.split(r'([ABCD])\.\s*', remaining)
        if len(parts) > 1:
            # 多个选项在同一行
            options[letter] = parts[0].strip()
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    options[parts[i]] = parts[i + 1].strip()
        else:
            options[letter] = content
        return options
    
    # 尝试多选项分割
    # 查找所有 A. B. C. D. 的位置
    matches = list(re.finditer(r'([ABCD])\.\s*', text))
    if len(matches) >= 2:
        for i, match in enumerate(matches):
            letter = match.group(1)
            start = match.end()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)
            content = text[start:end].strip()
            options[letter] = content
        return options
    
    return None


def extract_exam_info(text):
    """从第一段文字中提取考试名称和科目。
    
    示例输入："2025年海南省普通高中学业水平选择性考试地理"
    返回：("2025年海南省普通高中学业水平选择性考试", "地理")
    """
    # 尝试匹配"考试"后的科目
    # 科目可能是"地理"或"地 理"（带空格）
    exam_name = text
    subject = '地理'
    
    # 查找"考试"关键词位置
    exam_pos = text.find('考试')
    if exam_pos >= 0:
        # 考试名称到"考试"结束
        exam_name = text[:exam_pos + 2]
        # 科目是"考试"之后的内容
        subject_part = text[exam_pos + 2:].strip()
        if subject_part:
            # 去除空格
            subject = subject_part.replace(' ', '')
    
    return exam_name, subject


def read_media_file(docx_path, media_path):
    """从 docx ZIP 包中读取媒体文件的二进制数据。"""
    with zipfile.ZipFile(docx_path, 'r') as z:
        try:
            return z.read(media_path)
        except KeyError:
            return None


def get_image_relationships(docx_path):
    """读取 docx 中图片关系映射。返回 {rId: media文件路径}。"""
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


def get_media_info(docx_path):
    """读取 docx 中的媒体文件信息。
    
    返回 {文件路径: {size, ext, width_px, height_px, width_cm, height_cm}}。
    图片尺寸通过PIL读取像素尺寸并换算为厘米（默认96dpi）。
    """
    media = {}
    try:
        from PIL import Image as PILImage
        has_pil = True
    except ImportError:
        has_pil = False
    
    with zipfile.ZipFile(docx_path, 'r') as z:
        for name in z.namelist():
            if 'media/' in name and not name.endswith('/'):
                info = z.getinfo(name)
                ext = os.path.splitext(name)[1].lower()
                item = {'size': info.file_size, 'ext': ext}
                
                # 读取图片尺寸
                if has_pil and ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.wmf', '.emf']:
                    try:
                        data = z.read(name)
                        with PILImage.open(io.BytesIO(data)) as im:
                            px_w, px_h = im.size
                            dpi = im.info.get('dpi', (96, 96))
                            dpi_x = dpi[0] if dpi[0] else 96
                            dpi_y = dpi[1] if dpi[1] else 96
                            w_cm = px_w / dpi_x * 2.54
                            h_cm = px_h / dpi_y * 2.54
                            item['width_px'] = px_w
                            item['height_px'] = px_h
                            item['width_cm'] = round(w_cm, 2)
                            item['height_cm'] = round(h_cm, 2)
                    except Exception:
                        pass
                
                media[name] = item
    return media


def table_to_dict(table):
    """将 python-docx 的 Table 对象转换为字典表示。"""
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cells.append(cell.text.strip())
        rows.append(cells)
    
    return {
        'rows': len(rows),
        'cols': len(rows[0]) if rows else 0,
        'data': rows,
        'header': rows[0] if rows else [],
    }
