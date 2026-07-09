# -*- coding: utf-8 -*-
import json

with open('中间数据/with_placeholders.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('中间数据/image_descriptions.json', 'r', encoding='utf-8') as f:
    image_desc = json.load(f)

data['images'] = image_desc['images']

data['image_mapping'] = [
    {
        "placeholder_id": "ph_001",
        "image_id": "img_002",
        "confidence": 0.95,
        "reason": "占位符上下文为'冷链物流产业链示意图'，与img_002的关键词['冷链','物流','产业链']高度匹配"
    },
    {
        "placeholder_id": "ph_002",
        "image_id": "img_003",
        "confidence": 0.95,
        "reason": "占位符上下文为'甘青宁区域城市货运发展水平'，与img_003的关键词['货运','差异','甘青宁']高度匹配"
    },
    {
        "placeholder_id": "ph_003",
        "image_id": "img_004",
        "confidence": 0.95,
        "reason": "占位符上下文为'锢囚锋形成演化过程示意图'，与img_004的关键词['锢囚锋','形成过程']高度匹配"
    },
    {
        "placeholder_id": "ph_004",
        "image_id": "img_005",
        "confidence": 0.95,
        "reason": "占位符上下文为'岱海水量收支示意图'，与img_005的关键词['岱海','水量平衡','收支']高度匹配"
    },
    {
        "placeholder_id": "ph_005",
        "image_id": "img_006",
        "confidence": 0.90,
        "reason": "占位符上下文为'滑坡体周边等高线地形图'，与img_006的关键词['等高线','滑坡']匹配，图中左图为等高线地形图"
    },
    {
        "placeholder_id": "ph_006",
        "image_id": "img_007",
        "confidence": 0.85,
        "reason": "占位符上下文为'滑坡发生前后天气状况'和'滑坡发生过程'，img_007展示滑坡四个阶段过程，与第14题选项对应"
    },
    {
        "placeholder_id": "ph_007",
        "image_id": "img_008",
        "confidence": 0.90,
        "reason": "占位符上下文为'枣庄（位置如下图）'，与img_008的描述'枣庄市位置及区域示意图'匹配"
    },
    {
        "placeholder_id": "ph_008",
        "image_id": "img_009",
        "confidence": 0.75,
        "reason": "占位符上下文为'实验数据表'，img_009为苏里南光伏项目图，文档顺序匹配"
    },
    {
        "placeholder_id": "ph_009",
        "image_id": "img_009",
        "confidence": 0.90,
        "reason": "占位符上下文为'罗斯贝尔金矿光伏储能项目'，与img_009的关键词['苏里南','光伏','储能']匹配"
    },
    {
        "placeholder_id": "ph_010",
        "image_id": "img_010",
        "confidence": 0.95,
        "reason": "占位符上下文为'西西里岛地理位置及附近地区地形示意图'，与img_010的关键词['西西里岛','地形','埃特纳火山']高度匹配"
    }
]

all_placeholder_ids = set()
for section in data['document']['sections']:
    for question in section['questions']:
        for ph in question.get('placeholders', []):
            all_placeholder_ids.add(ph['placeholder_id'])

mapped_placeholder_ids = {m['placeholder_id'] for m in data['image_mapping']}
unmapped_placeholders = sorted(list(all_placeholder_ids - mapped_placeholder_ids))

all_image_ids = {img['image_id'] for img in data['images']}
mapped_image_ids = {m['image_id'] for m in data['image_mapping']}
unused_images = sorted(list(all_image_ids - mapped_image_ids))

data['validation'] = {
    "has_unmapped_placeholders": len(unmapped_placeholders) > 0,
    "has_unused_images": len(unused_images) > 0,
    "unmapped_placeholders": unmapped_placeholders,
    "unused_images": unused_images,
    "warnings": [
        "img_001: 标题处小图片(200B)，可能是学科标识符号，不作为内容图片映射",
        "ph_008: 文档描述为'实验数据表'，实际图片为光伏项目图，映射置信度较低"
    ]
}

with open('试卷数据/final_exam.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("final_exam.json 已生成")