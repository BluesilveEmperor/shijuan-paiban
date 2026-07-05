# -*- coding: utf-8 -*-
"""
待识别图片处理脚本

在 clean_docx.py 运行后，无法自动识别的图片会生成 pending_images.json。
用户或 AI 识别图片内容后，在 pending_images.json 中填入 identified_text 字段，
然后运行本脚本将识别结果应用到 docx 文件中。

用法:
    python resolve_pending.py --input cleaned.docx --pending pending_images.json --output resolved.docx

工作流程:
    1. clean_docx.py 生成 pending_images.json（identified_text 为 null）
    2. 用户/AI 查看 pending_images/ 目录中的图片，识别内容
    3. 在 pending_images.json 中填入 identified_text（如 "的" 或 "."）
    4. 运行本脚本，将识别文字替换到 docx 中对应的图片位置
"""

import argparse
import json
import os
import sys

from docx import Document
from lxml import etree

# 确保能导入同目录下的 utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    qn, setup_logger, get_paragraph_text, get_run_text,
    remove_element, get_media_info, get_image_relationships,
    get_drawings, get_embed_rid
)


def resolve_pending(input_path, pending_path, output_path, log_path=None):
    """应用待识别图片的识别结果。

    Args:
        input_path: 已清洗的 docx 文件路径
        pending_path: pending_images.json 文件路径
        output_path: 输出 docx 文件路径
        log_path: 日志文件路径（可选）
    """
    input_path = os.path.abspath(input_path)
    pending_path = os.path.abspath(pending_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        print(f'错误: 输入文件不存在: {input_path}')
        return False

    if not os.path.exists(pending_path):
        print(f'错误: 待识别清单不存在: {pending_path}')
        return False

    if log_path is None:
        log_path = os.path.join(os.path.dirname(output_path), 'resolve_log.txt')

    logger = setup_logger(log_path)

    logger.info('=' * 60)
    logger.info('待识别图片处理开始')
    logger.info(f'输入文件: {input_path}')
    logger.info(f'待识别清单: {pending_path}')
    logger.info(f'输出文件: {output_path}')
    logger.info('=' * 60)

    # 读取 pending_images.json
    with open(pending_path, 'r', encoding='utf-8') as f:
        pending_data = json.load(f)

    # 筛选出已识别的图片
    resolved_items = [
        item for item in pending_data.get('pending_images', [])
        if item.get('identified_text') is not None
    ]
    unresolved_items = [
        item for item in pending_data.get('pending_images', [])
        if item.get('identified_text') is None
    ]

    logger.info(f'待识别图片总数: {pending_data.get("total", 0)}')
    logger.info(f'已识别: {len(resolved_items)} 张, 未识别: {len(unresolved_items)} 张')

    if not resolved_items:
        logger.warning('没有已识别的图片需要处理，请先在 pending_images.json 中填入 identified_text')
        return False

    # 加载文档
    doc = Document(input_path)
    logger.info(f'文档加载成功，共 {len(doc.paragraphs)} 个段落')

    # 获取媒体文件信息和关系映射
    media_info = get_media_info(input_path)
    rels = get_image_relationships(input_path)

    # 按媒体路径分组已识别项
    # 同一张图片可能在文档中出现多次（如 image6.wmf），需要通过上下文区分
    resolved_by_media = {}
    for item in resolved_items:
        media_path = item['original_media_path']
        if media_path not in resolved_by_media:
            resolved_by_media[media_path] = []
        resolved_by_media[media_path].append(item)

    replaced = 0
    body = doc.element.body

    # 遍历所有段落
    for p in body.findall(f'.//{qn("w:p")}'):
        runs = p.findall(qn('w:r'))
        if not runs:
            continue

        for i, r in enumerate(runs):
            drawings = get_drawings(r)
            if not drawings:
                continue

            for drawing in drawings:
                rid = get_embed_rid(drawing)
                if not rid:
                    continue

                media_path = rels.get(rid)
                if not media_path:
                    continue

                # 检查这张图片是否在已识别列表中
                if media_path not in resolved_by_media:
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

                # 在已识别项中查找匹配（通过上下文）
                matched_item = None
                for item in resolved_by_media[media_path]:
                    # 上下文匹配：检查 before_text 的末尾和 after_text 的开头
                    item_before = item.get('context_before', '')
                    item_after = item.get('context_after', '')

                    # 模糊匹配：只要上下文有重叠即可
                    if (item_before and item_before in before_text) or \
                       (item_after and item_after in after_text) or \
                       (not item_before and not item_after):
                        matched_item = item
                        break

                if matched_item is None:
                    # 如果只有一项，直接使用
                    if len(resolved_by_media[media_path]) == 1:
                        matched_item = resolved_by_media[media_path][0]
                    else:
                        logger.warning(f'  图片 {media_path} 上下文无法匹配，跳过')
                        continue

                identified_text = matched_item['identified_text']

                # 替换图片为文字
                new_r = etree.SubElement(p, qn('w:r'))
                new_t = etree.SubElement(new_r, qn('w:t'))
                new_t.text = identified_text
                new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

                # 将新 run 移到原 run 的位置
                p.remove(new_r)
                p.insert(list(p).index(r), new_r)

                # 删除原 run
                remove_element(r)
                replaced += 1
                logger.debug(f'  图片替换: 前文="{before_text[-10:]}" 后文="{after_text[:10]}" -> "{identified_text}"')

                # 从待处理列表中移除已匹配的项
                resolved_by_media[media_path].remove(matched_item)
                if not resolved_by_media[media_path]:
                    del resolved_by_media[media_path]

                # 重新获取 runs 列表（因为元素已修改）
                break

    logger.info(f'[图片替换] 成功: {replaced} 处')

    # 保存文档
    doc.save(output_path)
    logger.info(f'文档已保存: {output_path}')

    if unresolved_items:
        logger.info(f'仍有 {len(unresolved_items)} 张图片未识别，请继续在 pending_images.json 中填入 identified_text')

    logger.info('')
    logger.info('=' * 60)
    logger.info('处理完成！')
    logger.info('=' * 60)

    return True


def main():
    parser = argparse.ArgumentParser(
        description='待识别图片处理脚本 - 应用 AI/用户识别结果到 docx 文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python resolve_pending.py --input cleaned.docx --pending pending_images.json --output resolved.docx

工作流程:
  1. 先运行 clean_docx.py 生成 pending_images.json
  2. 查看 pending_images/ 目录中的图片，识别内容
  3. 在 pending_images.json 中填入 identified_text 字段
  4. 运行本脚本应用识别结果
        '''
    )
    parser.add_argument('--input', '-i', required=True, help='已清洗的 docx 文件路径')
    parser.add_argument('--pending', '-p', required=True, help='pending_images.json 文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出 docx 文件路径')
    parser.add_argument('--log', '-l', help='日志文件路径（默认与输出文件同目录）')

    args = parser.parse_args()

    success = resolve_pending(args.input, args.pending, args.output, args.log)

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
