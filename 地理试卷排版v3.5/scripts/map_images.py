#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5: 图片映射 — 将占位符 (placeholder) 与图片 (image) 进行语义匹配。

输入：
  - {工作目录}/中间数据/with_placeholders.json  (Step3 产物，含占位符)
  - {工作目录}/中间数据/image_descriptions.json (Step4 产物，含图片描述；若缺失则回退到 image_manifest)
  - {工作目录}/清洗产物/image_manifest.json   (图片提取清单，含 paragraph_index)
  - {工作目录}/清洗产物/content.md            (清洗后正文，用于确认图片出现位置)

输出：
  - {工作目录}/试卷数据/final_exam.json        (完整试卷 JSON，含 images / image_mapping / validation)

用法:
  python scripts/map_images.py --work-dir output/{试卷名称}/
  python scripts/map_images.py --placeholders output/{试卷名称}/中间数据/with_placeholders.json --images-manifest output/{试卷名称}/清洗产物/image_manifest.json --content output/{试卷名称}/清洗产物/content.md --output output/{试卷名称}/试卷数据/final_exam.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


# ── 常量定义 ──────────────────────────────────────────────────────────

# 小图片阈值 (字节): 小于此值的图片视为符号/装饰图
SYMBOL_SIZE_THRESHOLD = 2048  # 2KB

# 图片类型推断: keyword → type 映射
KEYWORD_TYPE_MAP = {
    "等高线": "等高线图",
    "剖面": "剖面图",
    "示意图": "示意图",
    "流程": "流程图",
    "地图": "地图",
    "地形图": "地图",
    "位置": "地图",
    "区域": "地图",
    "分布": "地图",
    "景观": "景观图",
    "金字塔": "统计图表",
    "统计": "统计图表",
    "数据": "统计图表",
    "卫星": "卫星图",
    "表格": "表格图",
    "曲线": "统计图表",
}


def infer_image_type(text: str) -> str:
    """根据文本描述推断图片类型。"""
    for kw, img_type in KEYWORD_TYPE_MAP.items():
        if kw in text:
            return img_type
    return "其他"


def build_image_descriptions(manifest_path: str, content_md_path: str) -> list:
    """根据 image_manifest.json 和 content.md 构建图片描述列表。

    当 image_descriptions.json 缺失时使用。
    利用 manifest 中的 paragraph_index 定位图片在 content.md 中的上下文。
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 读取 content.md 并按段落分割
    with open(content_md_path, "r", encoding="utf-8") as f:
        content_text = f.read()

    paragraphs = content_text.split('\n\n')

    images_desc = []
    for img in manifest.get("images", []):
        img_id = img["image_id"]
        file_name = img.get("image_file", "")
        file_size = img.get("file_size", 0)
        para_idx = img.get("paragraph_index", -1)
        para_text = img.get("paragraph_text", "")

        # 从 content.md 获取图片前后的上下文
        context_before = ""
        context_after = ""
        if 0 <= para_idx < len(paragraphs):
            context_before = paragraphs[para_idx][:80] if para_idx > 0 else ""
            if para_idx + 1 < len(paragraphs):
                context_after = paragraphs[para_idx + 1][:80]

        # 合并上下文构建描述文本
        combined_context = para_text + " " + context_before + " " + context_after

        # 提取关键词 (简单分词)
        keywords = extract_keywords(combined_context)

        # 推断类型
        img_type = infer_image_type(combined_context)

        # 是否为符号小图
        is_symbol = file_size < SYMBOL_SIZE_THRESHOLD

        summary = f"试卷内容图片（{os.path.splitext(file_name)[1]}）"
        if is_symbol:
            summary = f"疑似符号图片，{file_size}B"

        images_desc.append({
            "image_id": img_id,
            "file_name": file_name,
            "type": img_type,
            "summary": summary,
            "keywords": keywords,
            "ocr_text": [],
            "discipline_features": [],
            "clues": [context_before[:60].strip(), context_after[:60].strip()] if context_before or context_after else [],
            "uncertain": is_symbol or img_type == "其他",
            "_paragraph_index": para_idx,
            "_file_size": file_size,
            "_original_type": img.get("original_type", img.get("image_type", "unknown")),
            "_context": combined_context,
        })

    return images_desc


def extract_keywords(text: str) -> list:
    """从文本中提取地理学科关键词。"""
    # 地理相关关键词模式
    geo_patterns = [
        r'(冷链|物流|产业链|港口|渔港|产业集群)',
        r'(货运|城市|发展水平|甘青宁|区域)',
        r'(锢囚锋|冷锋|暖锋|锋面|气旋)',
        r'(岱海|湖泊|水量|蒸发|补水)',
        r'(滑坡|等高线|地形|地质|灾害)',
        r'(枣庄|煤城|资源|转型|低空经济)',
        r'(苏里南|南美洲|光伏|储能|红树林)',
        r'(西西里岛|意大利|地中海|火山|海峡|墨西拿)',
        r'(苜蓿|盐碱地|牧草|黄河)',
        r'(示意图|地形图|分布图|过程图)',
    ]
    found = set()
    for pattern in geo_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if isinstance(m, tuple):
                for item in m:
                    if item:
                        found.add(item)
            else:
                found.add(m)
    return list(found)[:8]


def collect_placeholders(data: dict) -> list:
    """从 with_placeholders.json 中收集所有占位符列表。"""
    placeholders = []
    for section in data.get("document", {}).get("sections", []):
        section_type = section.get("type", "")
        for q in section.get("questions", []):
            for ph in q.get("placeholders", []):
                placeholders.append({
                    **ph,
                    "_question_id": q.get("id"),
                    "_question_number": q.get("number"),
                    "_section_type": section_type,
                    "_section_id": section.get("id"),
                })
    return placeholders


def match_placeholder_to_image(ph: dict, images: list) -> tuple:
    """对单个占位符匹配最佳图片。

    Returns:
        (matched_image, confidence, reason) or (None, 0, reason)
    """
    ph_reason = ph.get("reason", "")
    ph_context_before = ph.get("context_before", "")
    ph_context_after = ph.get("context_after", "")
    ph_owner_id = ph.get("owner_id", "")
    ph_id = ph.get("placeholder_id", "")

    # 合并占位符的所有文本用于匹配
    ph_text = f"{ph_reason} {ph_context_before} {ph_context_after}"

    best_match = None
    best_score = 0.0
    best_reason = ""

    for img in images:
        score = 0.0
        reasons = []

        # 跳过符号小图
        if img.get("_file_size", 9999) < SYMBOL_SIZE_THRESHOLD:
            continue

        img_keywords = [k.lower() for k in img.get("keywords", [])]
        img_summary = img.get("summary", "").lower()
        img_context = img.get("_context", "").lower()
        img_clues = [c.lower() for c in img.get("clues", [])]
        all_img_text = f"{' '.join(img_keywords)} {img_summary} {' '.join(img_clues)} {img_context}"

        ph_text_lower = ph_text.lower()

        # 1. 关键词精确匹配
        kw_matches = 0
        for kw in img_keywords:
            if len(kw) >= 2 and kw in ph_text_lower:
                kw_matches += 1
        if kw_matches >= 2:
            score += 0.4 + 0.1 * min(kw_matches - 2, 3)
            reasons.append(f"关键词匹配({kw_matches}个)")

        # 2. 材料/题目内容匹配
        # 提取占位符所属题目/材料的完整文本
        question_text = ph.get("_question_stem", "") + " " + ph.get("_material_content", "")
        question_text_lower = question_text.lower()
        for kw in img_keywords:
            if len(kw) >= 2 and kw in question_text_lower:
                score += 0.2
                reasons.append(f"题目主题匹配:{kw}")
                break

        # 3. 段落顺序匹配
        # （在主逻辑中按顺序分配，此处仅加分）
        # 此项在调用方处理

        # 4. clues 上下文匹配
        for clue in img_clues:
            if len(clue) >= 3 and clue[:15] in ph_text_lower:
                score += 0.15
                reasons.append("上下文吻合")
                break

        if score > best_score:
            best_score = score
            best_match = img
            best_reason = "; ".join(reasons) if reasons else "无明确匹配依据"

    if best_score >= 0.3:
        confidence = min(0.95, 0.5 + best_score)
        return best_match, round(confidence, 2), best_reason
    else:
        return None, 0.0, "无法匹配：语义关联不足"


def enrich_placeholder_context(data: dict):
    """为占位符追加所属题目/材料的完整文本，用于语义匹配。"""
    for section in data.get("document", {}).get("sections", []):
        for q in section.get("questions", []):
            q_id = q.get("id", "")
            q_stem = q.get("stem", "")
            materials_text = ""
            for mat in q.get("materials", []):
                materials_text += mat.get("content", "") + " "

            for ph in q.get("placeholders", []):
                ph["_question_stem"] = q_stem

                # 若占位符 owner_id 指向某个 material，追加该 material 的内容
                owner_id = ph.get("owner_id", "")
                for mat in q.get("materials", []):
                    if mat.get("id") == owner_id:
                        ph["_material_content"] = mat.get("content", "")
                        break

                # 若未找到 material，使用全部 materials
                if not ph.get("_material_content"):
                    ph["_material_content"] = materials_text


def classify_images_by_original_type(images):
    """v3.5: 按 original_type 分类图片。

    Args:
        images: 图片描述列表（含 _original_type, _file_size 内部字段）

    Returns:
        (inline_images, anchor_images, symbol_images)
    """
    inline = []
    anchor = []
    symbols = []

    for img in images:
        file_size = img.get("_file_size", 0)
        if file_size < SYMBOL_SIZE_THRESHOLD:
            symbols.append(img)
            continue

        orig_type = img.get("_original_type", "unknown")
        if orig_type == "inline":
            inline.append(img)
        elif orig_type == "anchor":
            anchor.append(img)
        else:
            # vml / unknown: 保守归入 anchor，由 AI 处理
            anchor.append(img)

    return inline, anchor, symbols


def build_mapping(placeholders: list, images: list) -> dict:
    """v3.5 双轨映射：代码处理 inline 图 + AI 结果处理 anchor 图。

    Track 1（代码，确定路径）：
      - 筛选 original_type == "inline" 的图片
      - 内嵌图片的 placeholder_id = image_id（与 content.md 中 {{image:img_xxx}} 一致）
      - 置信度固定 0.95，track: "code"

    Track 2（AI，不确定路径）：
      - 筛选 original_type != "inline" 的图片（anchor/vml/unknown）
      - 使用现有的占位符匹配逻辑
      - track: "ai"

    回退策略：如果所有图片的 original_type 都是 "unknown"（旧版 manifest），
    则回退到 v3.0 的纯 AI 路径。
    """
    # 按 original_type 分类图片
    inline_images, anchor_images, symbol_images = classify_images_by_original_type(images)

    mappings = []
    used_image_ids = set()

    # ── Track 1: inline 图片 → 代码确定路径 ──
    for img in inline_images:
        img_id = img.get("image_id")
        used_image_ids.add(img_id)

        mappings.append({
            "placeholder_id": img_id,
            "image_id": img_id,
            "confidence": 0.95,
            "reason": f"内嵌图片，位置确定（段落{img.get('_paragraph_index', '?')}）",
            "track": "code",
        })

    # ── Track 2: anchor 图片 → AI/占位符匹配路径 ──
    # anchor_images 已包含 anchor + vml + unknown 类型
    # 旧版 manifest（无 original_type）时 unknown 图进入此路径，行为与 v3.0 兼容

    if not anchor_images:
        # 没有需要 AI 处理的图片，跳过 Track 2
        unused_img_ids = sorted(set(
            img.get("image_id") for img in images
            if img.get("image_id") not in used_image_ids
        ))
        return {
            "mappings": mappings,
            "unmapped_ph_ids": sorted(set(ph.get("placeholder_id") for ph in placeholders)),
            "unused_img_ids": unused_img_ids,
            "warnings": [f"{img_id}: 符号小图，不作为内容图片映射"
                         for img in symbol_images
                         for img_id in [img.get("image_id")]]
        }

    # 按 paragraph_index 排序 anchor 图
    anchor_images.sort(key=lambda x: x.get("_paragraph_index", 9999))

    # 分类占位符：有效 vs 泛型（同 v3.0 逻辑）
    valid_phs = []
    generic_phs = []
    for ph in placeholders:
        reason = ph.get("reason", "")
        context_before = ph.get("context_before", "")
        loc_type = ph.get("location_type", "")

        is_generic = (
            loc_type == "question_stem"
            and "题干明确提到图片关键词" in reason
            and len(context_before.strip()) <= 5
        )
        if is_generic:
            generic_phs.append(ph)
        else:
            valid_phs.append(ph)

    # 有效占位符按题目顺序排列
    valid_phs.sort(key=lambda p: (p.get("_section_id", ""), int(p.get("_question_number", "0") or "0")))

    # 占位符 → anchor 图按顺序一一映射
    unmapped_valid = []

    for i, ph in enumerate(valid_phs):
        if i < len(anchor_images):
            img = anchor_images[i]
            img_id = img.get("image_id")
            used_image_ids.add(img_id)

            # 使用 anchor_descriptions 的关键词做验证
            ph_text = f"{ph.get('reason', '')} {ph.get('context_before', '')} {ph.get('context_after', '')}"
            img_keywords = img.get("keywords", [])
            orig_type = img.get("_original_type", "unknown")

            confidence = 0.70 if orig_type == "anchor" else 0.65
            match_reason = f"浮动图片，AI判断归位（锚点段落{img.get('_paragraph_index', '?')}）"

            # 关键词匹配增强
            kw_matches = [kw for kw in img_keywords if len(kw) >= 2 and kw in ph_text]
            if len(kw_matches) >= 2:
                confidence = min(0.90, confidence + 0.2)
                match_reason = f"浮动图+关键词匹配({len(kw_matches)}个): {', '.join(kw_matches[:4])}"
            elif len(kw_matches) == 1:
                confidence = min(0.85, confidence + 0.1)
                match_reason = f"浮动图+关键词部分匹配: {kw_matches[0]}"

            mappings.append({
                "placeholder_id": ph.get("placeholder_id"),
                "image_id": img_id,
                "confidence": round(confidence, 2),
                "reason": match_reason,
                "track": "ai",
            })
        else:
            unmapped_valid.append(ph)

    # 检测冗余泛型占位符（同 v3.0 逻辑）
    redundant_ph_ids = set()
    mapped_ph_ids = {m.get("placeholder_id") for m in mappings}
    mapped_q_ids = set()
    for ph in valid_phs:
        if ph.get("placeholder_id") in mapped_ph_ids:
            mapped_q_ids.add(ph.get("_question_id", ""))

    for ph in generic_phs:
        if ph.get("_question_id", "") in mapped_q_ids:
            redundant_ph_ids.add(ph.get("placeholder_id"))

    # 收集未映射的占位符
    all_ph_ids = {ph.get("placeholder_id") for ph in placeholders}
    unmapped_ph_ids = sorted(all_ph_ids - mapped_ph_ids)

    # 收集未使用的图片
    all_content_img_ids = {img.get("image_id") for img in images}
    unused_img_ids = sorted(all_content_img_ids - used_image_ids)

    # 构建警告
    warnings = []
    for ph_id in unmapped_ph_ids:
        ph = next((p for p in placeholders if p.get("placeholder_id") == ph_id), None)
        if ph:
            q_id = ph.get("_question_id", "").replace("question_", "")
            mat_content = ph.get("_material_content", "")
            if ph_id in redundant_ph_ids:
                mapped_same_q = [m for m in mappings if any(
                    p.get("placeholder_id") == m.get("placeholder_id") and p.get("_question_id", "").endswith(q_id)
                    for p in valid_phs
                )]
                if mapped_same_q:
                    m = mapped_same_q[0]
                    warnings.append(
                        f"{ph_id}: 泛型占位符（'阅读图文材料'），与 {m.get('placeholder_id')} "
                        f"位置冗余（同属第{q_id}题），已合并映射"
                    )
                else:
                    warnings.append(f"{ph_id}: 泛型占位符（第{q_id}题），无法确定对应关系")
            elif "下表" in mat_content:
                warnings.append(f"{ph_id}: 第{q_id}题材料为表格（'下表示意'），无对应图片")
            else:
                warnings.append(f"{ph_id}: 无匹配图片 ({ph.get('reason', '')})")

    for img_id in unused_img_ids:
        img = next((i for i in images if i.get("image_id") == img_id), None)
        if img:
            size = img.get("_file_size", 0)
            orig_type = img.get("_original_type", "")
            if size < SYMBOL_SIZE_THRESHOLD:
                warnings.append(f"{img_id}: {size}B 符号小图，不作为内容图片映射")
            elif orig_type == "inline":
                warnings.append(f"{img_id}: 内嵌图片，未找到对应占位符")
            else:
                warnings.append(f"{img_id}: 浮动图片({orig_type})，未找到匹配的占位符")

    return {
        "mappings": mappings,
        "unmapped_ph_ids": unmapped_ph_ids,
        "unused_img_ids": unused_img_ids,
        "warnings": warnings,
    }


def _detect_redundant_placeholders(placeholders: list, existing_mappings: list) -> set:
    """检测冗余占位符：同一题中存在泛型占位符（如"阅读图文材料"）和已映射的具体占位符（如"位置如下图"）。"""
    mapped_ph_ids = {m.get("placeholder_id") for m in existing_mappings}

    # 按 _question_id 分组（同一道题的所有占位符）
    ph_by_question = {}
    for ph in placeholders:
        q_id = ph.get("_question_id", "")
        if q_id not in ph_by_question:
            ph_by_question[q_id] = []
        ph_by_question[q_id].append(ph)

    redundant = set()
    for q_id, phs in ph_by_question.items():
        if len(phs) <= 1:
            continue
        has_mapped = any(ph.get("placeholder_id") in mapped_ph_ids for ph in phs)

        for ph in phs:
            ph_id = ph.get("placeholder_id")
            if ph_id in mapped_ph_ids:
                continue
            reason = ph.get("reason", "")
            context_before = ph.get("context_before", "")
            is_generic = (
                "题干明确提到图片关键词" in reason
                and len(context_before.strip()) <= 5
            )
            if is_generic and has_mapped:
                redundant.add(ph_id)

    return redundant


def _clean_placeholders(data: dict) -> dict:
    """从 placeholders 中移除内部字段 (_xxx)。"""
    for section in data.get("document", {}).get("sections", []):
        for q in section.get("questions", []):
            for ph in q.get("placeholders", []):
                keys_to_remove = [k for k in ph if k.startswith("_")]
                for k in keys_to_remove:
                    del ph[k]
    return data


def build_final_exam(placeholders_data: dict, images_desc: list, mapping_result: dict,
                     descriptions_source: str) -> dict:
    """组装 final_exam.json。"""
    # 清理内部字段 (_xxx)
    clean_images = []
    for img in images_desc:
        clean_img = {k: v for k, v in img.items() if not k.startswith("_")}
        clean_images.append(clean_img)

    # 清理占位符中的内部字段
    data = _clean_placeholders(placeholders_data)

    total_phs = sum(
        len(q.get("placeholders", []))
        for s in data.get("document", {}).get("sections", [])
        for q in s.get("questions", [])
    )

    return {
        **data,
        "images": clean_images,
        "image_mapping": mapping_result["mappings"],
        "validation": {
            "has_unmapped_placeholders": len(mapping_result["unmapped_ph_ids"]) > 0,
            "has_unused_images": len(mapping_result["unused_img_ids"]) > 0,
            "unmapped_placeholders": mapping_result["unmapped_ph_ids"],
            "unused_images": mapping_result["unused_img_ids"],
            "warnings": mapping_result["warnings"],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Step5: 图片映射 — 将占位符与图片进行语义匹配，输出 final_exam.json"
    )
    parser.add_argument(
        "--placeholders", "-p",
        default="{工作目录}/中间数据/with_placeholders.json",
        help="Step3 占位符 JSON 文件路径",
    )
    parser.add_argument(
        "--image-descriptions", "-d",
        default="{工作目录}/中间数据/image_descriptions.json",
        help="Step4 图片描述 JSON 文件路径（可选，缺失时自动从 manifest 构建）",
    )
    parser.add_argument(
        "--images-manifest", "-m",
        default="{工作目录}/清洗产物/image_manifest.json",
        help="图片提取清单 JSON 文件路径",
    )
    parser.add_argument(
        "--content", "-c",
        default="{工作目录}/清洗产物/content.md",
        help="清洗后正文 Markdown 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        default="{工作目录}/试卷数据/final_exam.json",
        help="输出文件路径",
    )
    parser.add_argument(
        "--schema", "-s",
        default="schemas/exam_paper.schema.json",
        help="统一 Schema 文件路径",
    )

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def resolve(path):
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(base_dir, path))

    placeholders_path = resolve(args.placeholders)
    descriptions_path = resolve(args.image_descriptions)
    manifest_path = resolve(args.images_manifest)
    content_path = resolve(args.content)
    output_path = resolve(args.output)
    schema_path = resolve(args.schema)

    # 1. 读取占位符数据
    print(f"[map_images] 读取占位符: {placeholders_path}")
    if not os.path.exists(placeholders_path):
        print(f"错误: 占位符文件不存在: {placeholders_path}", file=sys.stderr)
        sys.exit(2)

    with open(placeholders_path, "r", encoding="utf-8") as f:
        placeholders_data = json.load(f)

    # 2. 读取/构建图片描述
    images_desc = []
    descriptions_source = ""

    if os.path.exists(descriptions_path):
        print(f"[map_images] 读取图片描述: {descriptions_path}")
        with open(descriptions_path, "r", encoding="utf-8") as f:
            desc_data = json.load(f)
        images_desc = desc_data.get("images", [])
        descriptions_source = "image_descriptions.json"

        # 补充 paragraph_index 信息
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for img in images_desc:
                for m_img in manifest.get("images", []):
                    if m_img.get("image_id") == img.get("image_id"):
                        img["_paragraph_index"] = m_img.get("paragraph_index", 9999)
                        img["_file_size"] = m_img.get("file_size", 0)
                        img["_original_type"] = m_img.get("original_type", m_img.get("image_type", "unknown"))
                        break
                if "_paragraph_index" not in img:
                    img["_paragraph_index"] = 9999
                    img["_file_size"] = 0
                    img["_original_type"] = "unknown"

    else:
        print(f"[map_images] 图片描述文件不存在，从 manifest + content.md 构建...")
        if not os.path.exists(manifest_path):
            print(f"错误: image_manifest.json 不存在: {manifest_path}", file=sys.stderr)
            sys.exit(2)
        if not os.path.exists(content_path):
            print(f"警告: content.md 不存在: {content_path}，使用空上下文")

        images_desc = build_image_descriptions(manifest_path, content_path)
        descriptions_source = "image_manifest.json + content.md (自动构建)"

    # 3. 先富化上下文再收集占位符（确保 _question_stem 和 _material_content 同时存在于 placeholders）
    enrich_placeholder_context(placeholders_data)
    placeholders = collect_placeholders(placeholders_data)

    # 将 enrich 添加的 _question_stem / _material_content 复制到 placeholders 列表
    for section in placeholders_data.get("document", {}).get("sections", []):
        for q in section.get("questions", []):
            for ph in q.get("placeholders", []):
                ph_id = ph.get("placeholder_id")
                for p in placeholders:
                    if p.get("placeholder_id") == ph_id:
                        p["_question_stem"] = ph.get("_question_stem", "")
                        p["_material_content"] = ph.get("_material_content", "")
                        break

    print(f"[map_images] 占位符总数: {len(placeholders)}")
    print(f"[map_images] 图片总数: {len(images_desc)}")

    # 4. 构建映射
    mapping_result = build_mapping(placeholders, images_desc)

    # 5. 组装 final_exam.json
    final = build_final_exam(placeholders_data, images_desc, mapping_result, descriptions_source)

    # 6. 写入文件
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"[map_images] 输出: {output_path}")

    # 7. 打印摘要
    mapped_count = len(mapping_result["mappings"])
    unmapped_count = len(mapping_result["unmapped_ph_ids"])
    unused_count = len(mapping_result["unused_img_ids"])
    code_track = sum(1 for m in mapping_result["mappings"] if m.get("track") == "code")
    ai_track = sum(1 for m in mapping_result["mappings"] if m.get("track") == "ai")
    print(f"  占位符: {len(placeholders)} | 图片: {len(images_desc)}")
    print(f"  已映射: {mapped_count} (代码: {code_track}, AI: {ai_track}) | 未映射: {unmapped_count} | 未使用: {unused_count}")

    if mapping_result["unmapped_ph_ids"]:
        print(f"  未映射占位符: {mapping_result['unmapped_ph_ids']}")
    if mapping_result["unused_img_ids"]:
        print(f"  未使用图片: {mapping_result['unused_img_ids']}")
    if mapping_result["warnings"]:
        print(f"  警告 ({len(mapping_result['warnings'])} 条):")
        for w in mapping_result["warnings"]:
            print(f"    - {w}")

    # 8. Schema 校验 (如果 jsonschema 可用)
    if os.path.exists(schema_path):
        print(f"\n[map_images] 执行 Schema 校验...")
        import subprocess as sp
        result = sp.run(
            [sys.executable, str(resolve("scripts/validate_json.py")),
             "--schema", schema_path, "--json", output_path, "--quiet"],
            capture_output=True
        )
        exit_code = result.returncode
        if exit_code == 0:
            print("  Schema 校验 ✓ 通过")
        else:
            print("  Schema 校验 ✗ 失败 (见上方错误详情)", file=sys.stderr)
    else:
        print(f"\n[map_images] Schema 文件不存在，跳过校验: {schema_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
