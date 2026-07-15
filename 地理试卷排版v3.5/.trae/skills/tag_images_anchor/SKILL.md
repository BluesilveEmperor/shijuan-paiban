---
name: "tag_images_anchor"
description: "Analyze only anchor/floating images (original_type=='anchor') in a geography exam to produce content descriptions for position determination. Does NOT process inline images."
---

# Step4: tag_images_anchor — anchor 浮动图内容理解

## Role

你负责仅对源文档中的 **浮动图片**（`original_type == "anchor"`）进行内容理解，为后续的图片定位提供语义依据。**inline 内嵌图片不需要你处理**，它们由代码在 Step1 中自动定位。

---

## Input

| 文件 | 说明 |
|------|------|
| `{工作目录}/清洗产物/images/` | 包含所有提取的图片文件 |
| `{工作目录}/清洗产物/image_manifest.json` | 图片提取清单，**仅处理 `original_type == "anchor"` 的条目** |

---

## Task

### 1. 筛选 anchor 图片

从 `image_manifest.json` 中筛选 `original_type == "anchor"` 的图片条目。如果没有任何 anchor 图片，直接输出空结果并标记 `anchor_count: 0`。

### 2. 检测模型图片能力

尝试读取第一张 anchor 图片。如果模型不支持图片读取，设置 `model_support_images: false` 并跳过所有分析。

### 3. 逐张分析 anchor 图片

对每张 anchor 图进行内容理解，提取以下信息：

| 字段 | 说明 |
|------|------|
| `type` | 图片类型（地图/统计图表/示意图/景观图/卫星图/表格图/等高线图/剖面图/流程图/其他） |
| `summary` | 20-50 字的图片内容摘要 |
| `keywords` | 3-8 个地理学科关键词 |
| `ocr_text` | 图片中的文字内容（如有） |
| `discipline_features` | 学科特征（如"区域划分"、"地形分析"、"气候统计"） |
| `clues` | 与试题可能相关的线索（如"中国四大地理区域"、"降水量柱状图"） |
| `position_hint` | **关键字段**：基于图片内容和锚点上下文，给出这张图最可能出现在试卷的哪个位置。格式如"材料中提到'四大地理区域分布如图'，该图应位于第X题的材料部分" |

### 4. 锚点上下文分析

对于每张 anchor 图，从 `image_manifest.json` 中读取：
- `paragraph_index`：锚点所在段落编号
- `paragraph_text`：锚点段落的文本内容（前100字）
- `context_before`：图片前的文字
- `context_after`：图片后的文字

分析锚点上下文是否与图片内容**语义匹配**：
- 如果上下文出现"如图"、"下图"、"读图" + 与图片关键词匹配的地理术语 → 锚点可能正确
- 如果上下文与图片内容完全无关 → 锚点可能偏移，需在 `position_hint` 中标注

---

## Output

输出文件：`{工作目录}/中间数据/anchor_descriptions.json`

```json
{
  "model_support_images": true,
  "anchor_count": 2,
  "images": [
    {
      "image_id": "img_005",
      "file_name": "img_005.png",
      "original_type": "anchor",
      "anchor_paragraph_index": 12,
      "anchor_context": "北方地区冬季寒冷干燥，夏季高温多雨...",
      "type": "地图",
      "summary": "中国四大地理区域分布图，标注了北方地区、南方地区、西北地区和青藏地区",
      "keywords": ["北方地区", "南方地区", "西北地区", "青藏地区", "分界线"],
      "ocr_text": ["北方地区", "南方地区"],
      "discipline_features": ["区域划分", "地理分界线"],
      "clues": ["四大地理区域", "秦岭-淮河线"],
      "position_hint": "锚点段落内容与图片无关。试卷第3题材料提到'四大地理区域分布如下图所示'，该图应位于第3题材料末尾。建议将图片从当前位置（段落12）移至第3题材料区域。",
      "uncertain": false
    }
  ]
}
```

### 模型不支持图片时的输出

```json
{
  "model_support_images": false,
  "anchor_count": 2,
  "images": [],
  "note": "当前模型无法读取图片文件。将在 Step5 中通过锚点段落顺序进行图片匹配。"
}
```

---

## Constraints

1. ❌ **不处理 inline 图片**：`image_manifest.json` 中 `original_type == "inline"` 的条目直接忽略
2. ❌ **不处理符号小图**（< 2KB）：这些已在 Step1 标记，不是内容图片
3. ❌ **不决定最终位置**：`position_hint` 只是参考建议，最终位置由 Step3 决定
4. ❌ **不修改试卷结构**：只分析图片，不改动任何 JSON 文件
5. ✅ **必须读取 image_manifest.json 筛选 anchor 图**：不要遍历 images/ 目录中所有图片

---

## Self-check

- [ ] 是否只处理了 `original_type == "anchor"` 的图片？
- [ ] `anchor_count` 是否与 manifest 中 anchor 图数量一致？
- [ ] 每张 anchor 图是否有 `position_hint` 字段？
- [ ] 模型不支持图片时，是否设置了 `model_support_images: false`？
