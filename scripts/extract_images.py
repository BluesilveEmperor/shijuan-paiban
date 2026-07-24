# -*- coding: utf-8 -*-
"""
地理试卷图片提取脚本
从 cleaned.docx 中提取所有图片，记录位置信息，并删除图片元素。

用法:
    python extract_images.py --input "cleaned.docx" --output "初步清理.docx"

功能:
    1. 提取所有图片（嵌入式 wp:inline + 浮动式 wp:anchor）
    2. 保存图片到 images 文件夹（img_001.png、img_002.png 等）
    3. 删除文档中所有图片元素，保存为"初步清理.docx"
    4. 输出 image_manifest.json（记录图片原始位置信息）
"""

import argparse
import json
import os
import sys
import zipfile
from datetime import datetime

from docx import Document
from lxml import etree

# 确保能导入同目录下的 utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    NSMAP, qn, setup_logger, get_paragraph_text, get_run_text,
    remove_element, get_media_info, get_image_relationships,
    has_drawing, get_drawings, get_embed_rid, read_media_file
)


# =====================================================================
# 图片提取核心函数
# =====================================================================

def extract_all_images(doc, docx_path, output_dir, logger):
    """从文档中提取所有图片并记录位置信息。

    Args:
        doc: python-docx Document 对象
        docx_path: 原始 docx 文件路径
        output_dir: 图片输出目录
        logger: 日志记录器

    Returns:
        tuple: (manifest_data, drawings_to_remove)
            manifest_data: 图片清单数据（用于生成 JSON）
            drawings_to_remove: 需要删除的图片元素列表
    """
    # 创建 images 目录
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    # 获取媒体文件信息和关系映射
    media_info = get_media_info(docx_path)
    rels = get_image_relationships(docx_path)

    # 图片清单数据
    manifest_data = {
        'source_docx': os.path.basename(docx_path),
        'extract_time': datetime.now().isoformat(),
        'total_images': 0,
        'images': []
    }

    # 需要删除的图片元素列表
    drawings_to_remove = []

    # 图片计数器
    img_counter = 0

    # 遍历所有段落（递归查找，包括表格内的段落）
    body = doc.element.body
    paragraphs = body.findall(f'.//{qn("w:p")}')

    for para_idx, p in enumerate(paragraphs):
        # 获取段落全文
        para_text = get_paragraph_text(p).strip()

        # 获取段落中所有 run（直接子元素）
        runs = p.findall(qn('w:r'))
        if not runs:
            continue

        for run_idx, r in enumerate(runs):
            # 检查这个 run 是否包含图片
            drawings = get_drawings(r)
            if not drawings:
                continue

            for drawing in drawings:
                # 获取图片类型（inline/anchor/vml）
                img_type = _get_image_type(drawing)

                # 获取关系ID
                rid = get_embed_rid(drawing)
                if not rid:
                    logger.warning(f'  图片无关系ID: 段落{para_idx} run{run_idx}')
                    continue

                # 查找图片文件信息
                media_path = rels.get(rid)
                if not media_path:
                    logger.warning(f'  图片无媒体路径: rId={rid}')
                    continue

                info = media_info.get(media_path, {})
                file_size = info.get('size', 0)
                file_ext = info.get('ext', '.png')

                # 如果扩展名为空或不是图片格式，默认使用 png
                if not file_ext or file_ext not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.wmf', '.emf', '.tiff']:
                    file_ext = '.png'

                # 获取上下文文字
                before_text = ''
                for j in range(run_idx):
                    before_text += get_run_text(runs[j])

                after_text = ''
                for j in range(run_idx + 1, len(runs)):
                    after_text += get_run_text(runs[j])

                # 提取图片文件
                img_counter += 1
                img_id = f'img_{img_counter:03d}'
                img_filename = f'{img_id}{file_ext}'
                img_path = os.path.join(images_dir, img_filename)

                # 从 docx 中提取图片二进制数据
                img_data = read_media_file(docx_path, media_path)
                if img_data:
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    logger.debug(f'  提取图片: {img_filename} ({file_size} bytes, {img_type})')
                else:
                    logger.warning(f'  图片数据提取失败: {media_path}')

                # 记录图片信息
                manifest_data['images'].append({
                    'image_id': img_id,
                    'image_file': img_filename,
                    'image_path': os.path.abspath(img_path),
                    'original_media_path': media_path,
                    'relationship_id': rid,
                    'file_size': file_size,
                    'file_ext': file_ext,
                    'image_type': img_type,
                    'paragraph_index': para_idx,
                    'run_index': run_idx,
                    'paragraph_text': para_text[:100] if para_text else '',
                    'context_before': before_text.strip()[-50:] if before_text else '',
                    'context_after': after_text.strip()[:50] if after_text else '',
                })

                # 记录需要删除的图片元素
                drawings_to_remove.append({
                    'drawing': drawing,
                    'run': r,
                    'para_idx': para_idx,
                    'run_idx': run_idx,
                })

    manifest_data['total_images'] = img_counter

    logger.info(f'[图片提取] 共提取 {img_counter} 张图片，保存至: {images_dir}')

    return manifest_data, drawings_to_remove


def _get_image_type(drawing_element):
    """判断图片类型（inline/anchor/vml）。

    Args:
        drawing_element: 图片 XML 元素

    Returns:
        str: 'inline' | 'anchor' | 'vml'
    """
    tag = drawing_element.tag

    if tag == qn('w:drawing'):
        # 检查子元素
        for child in drawing_element:
            if child.tag == qn('wp:inline'):
                return 'inline'
            elif child.tag == qn('wp:anchor'):
                return 'anchor'
        return 'unknown'

    elif tag == qn('v:imagedata'):
        return 'vml'

    elif tag == qn('v:shape'):
        return 'vml'

    return 'unknown'


def remove_all_images(doc, drawings_to_remove, logger):
    """删除文档中所有图片元素。

    Args:
        doc: python-docx Document 对象
        drawings_to_remove: 需要删除的图片元素列表
        logger: 日志记录器
    """
    removed_count = 0
    removed_runs = 0

    # 按段落索引和run索引分组
    # 这样可以避免同一个run被多次删除
    runs_to_remove = set()

    for item in drawings_to_remove:
        r = item['run']
        drawing = item['drawing']

        # 先删除 drawing 元素
        remove_element(drawing)
        removed_count += 1

        # 检查 run 是否还有其他内容（文字等）
        # 如果 run 为空（只有图片），则删除整个 run
        run_text = get_run_text(r)
        if not run_text.strip():
            # 使用元组标识唯一的 run
            para_idx = item['para_idx']
            run_idx = item['run_idx']
            run_key = (para_idx, run_idx)
            runs_to_remove.add(run_key)

    # 删除空的 run
    body = doc.element.body
    paragraphs = body.findall(qn('w:p'))

    for para_idx, p in enumerate(paragraphs):
        runs = p.findall(qn('w:r'))
        for run_idx, r in enumerate(runs):
            if (para_idx, run_idx) in runs_to_remove:
                # 再次确认 run 是否真的空了
                run_text = get_run_text(r)
                remaining_drawings = get_drawings(r)
                if not run_text.strip() and not remaining_drawings:
                    remove_element(r)
                    removed_runs += 1

    logger.info(f'[图片删除] 删除图片元素: {removed_count} 处, 删除空run: {removed_runs} 处')


def _merge_original_types(manifest_data, output_dir, logger):
    """v3.5: 读取 _original_image_types.json，将 original_type 合并到 manifest。

    clean_docx.py 的 record_original_image_types() 在 rule_1_19 之前记录了
    每张图片的原始类型（inline/anchor），本函数将该信息按 relationship_id
    匹配到 image_manifest.json 的每条记录中。

    Args:
        manifest_data: extract_all_images() 产出的图片清单数据
        output_dir: 输出目录（_original_image_types.json 所在目录）
        logger: 日志记录器
    """
    import json as _json

    types_path = os.path.join(output_dir, '_original_image_types.json')
    if not os.path.exists(types_path):
        logger.warning('[original_type] _original_image_types.json 不存在，所有图片将标记为 unknown')
        for img in manifest_data.get('images', []):
            img['original_type'] = 'unknown'
        return

    try:
        with open(types_path, 'r', encoding='utf-8') as f:
            original_types = _json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        logger.warning(f'[original_type] 读取失败: {e}，所有图片将标记为 unknown')
        for img in manifest_data.get('images', []):
            img['original_type'] = 'unknown'
        return

    inline_count = 0
    anchor_count = 0
    unknown_count = 0

    for img in manifest_data.get('images', []):
        rid = img.get('relationship_id', '')
        orig_type = original_types.get(rid, 'unknown')
        img['original_type'] = orig_type

        if orig_type == 'inline':
            inline_count += 1
        elif orig_type == 'anchor':
            anchor_count += 1
        else:
            unknown_count += 1

    logger.info(f'[original_type] 合并完成: inline={inline_count}, anchor={anchor_count}, unknown={unknown_count}')


def save_manifest(manifest_data, output_path, logger):
    """保存图片清单到 JSON 文件。

    Args:
        manifest_data: 图片清单数据
        output_path: JSON 文件输出路径
        logger: 日志记录器
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    logger.info(f'[图片清单] 已保存: {output_path}')


# =====================================================================
# 主函数
# =====================================================================

def extract_images(input_path, output_path, log_path=None):
    """执行图片提取和删除。

    Args:
        input_path: 输入 docx 文件路径（如 cleaned.docx）
        output_path: 输出 docx 文件路径（如 初步清理.docx）
        log_path: 日志文件路径（可选）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        print(f'错误: 输入文件不存在: {input_path}')
        return False

    if log_path is None:
        log_path = os.path.join(os.path.dirname(output_path), 'extract_images_log.txt')

    logger = setup_logger(log_path)

    logger.info('=' * 60)
    logger.info('地理试卷图片提取开始')
    logger.info(f'输入文件: {input_path}')
    logger.info(f'输出文件: {output_path}')
    logger.info(f'日志文件: {log_path}')
    logger.info('=' * 60)

    try:
        # 加载文档
        doc = Document(input_path)
        logger.info(f'文档加载成功，共 {len(doc.paragraphs)} 个段落')

        # 输出目录
        output_dir = os.path.dirname(output_path) or '.'

        # 阶段一：提取所有图片
        logger.info('')
        logger.info('--- 阶段一：提取图片 ---')
        manifest_data, drawings_to_remove = extract_all_images(
            doc, input_path, output_dir, logger
        )

        # v3.5: 合并原始图片类型（支撑双轨分流）
        _merge_original_types(manifest_data, output_dir, logger)

        # 阶段二：删除图片元素
        logger.info('')
        logger.info('--- 阶段二：删除图片元素 ---')
        remove_all_images(doc, drawings_to_remove, logger)

        # 保存文档
        logger.info('')
        logger.info('--- 保存文档 ---')
        doc.save(output_path)
        logger.info(f'文档已保存: {output_path}')

        # 保存图片清单
        manifest_path = os.path.join(output_dir, 'image_manifest.json')
        save_manifest(manifest_data, manifest_path, logger)

        logger.info('')
        logger.info('=' * 60)
        logger.info('图片提取完成！')
        logger.info(f'输出文件: {output_path}')
        logger.info(f'图片目录: {os.path.join(output_dir, "images")}')
        logger.info(f'图片清单: {manifest_path}')
        logger.info(f'日志文件: {log_path}')
        logger.info('=' * 60)

        return True

    except Exception as e:
        logger.error(f'图片提取过程中出错: {e}', exc_info=True)
        print(f'错误: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='地理试卷图片提取脚本 - 提取图片并记录位置信息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python extract_images.py --input "cleaned.docx" --output "初步清理.docx"
  python extract_images.py -i "cleaned.docx" -o "初步清理.docx" -l "extract.log"
        '''
    )
    parser.add_argument('--input', '-i', required=True,
                        help='输入 docx 文件路径（如 cleaned.docx）')
    parser.add_argument('--output', '-o', required=True,
                        help='输出 docx 文件路径（如 初步清理.docx）')
    parser.add_argument('--log', '-l',
                        help='日志文件路径（默认与输出文件同目录）')

    args = parser.parse_args()

    success = extract_images(args.input, args.output, args.log)

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()