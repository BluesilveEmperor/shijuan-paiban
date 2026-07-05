---
name: geo-exam-image-analysis
description: "地理试卷图片内容分析skill。AI读取images文件夹中的所有图片，通过多模态能力分析图片内容（地图、图表、示意图等），输出结构化JSON描述。清洗阶段extract_images.py脚本执行完毕后自动触发，或用户提到'分析图片内容'、'图片判断'时触发。AI多模态主导，不依赖代码实现。"
---

# 地理试卷图片内容分析 Skill

## 触发时机（必须明确）

**自动触发条件**：
1. extract_images.py脚本执行完毕
2. images文件夹已生成且包含图片文件
3. image_manifest.json已生成

**手动触发条件**：
- 用户明确要求"分析图片内容"
- 用户提到"图片判断"、"图片用途分析"
- 用户提到"判断图片类型"

**触发检查**：
AI必须先检查以下条件：
- images文件夹是否存在
- image_manifest.json是否存在
- 如果不满足，提示用户："请先运行extract_images.py脚本提取图片"

---

## 输入

**必需输入**：
- `images/`文件夹：包含所有提取的图片文件（img_001.png、img_002.png等）

**可选输入**：
- `image_manifest.json`：图片清单，提供上下文信息（before_text、after_text）

**输入位置**：
- images文件夹位于output目录下（如output/images/）
- 或用户指定的工作目录

---

## 输出

**输出文件**：
- `images_analysis.json`：图片内容分析结果

**输出位置**：
- 与images文件夹同目录（如output/images_analysis.json）

**输出格式**：
```json
{
  "analysis_timestamp": "2026-07-02T10:30:00",
  "total_images": 12,
  "analyses": [
    {
      "filename": "img_001.png",
      "type": "map",
      "description": "世界地图，显示主要洋流分布规律",
      "inferred_usage": "material",
      "confidence": 0.95,
      "reason": "图片是地图类型，结合上下文'洋流对海洋生物的影响'判断为材料图",
      "context_match": {
        "before_text": "阅读图文材料，完成下列要求。",
        "after_text": "洋流对海洋生物的影响...",
        "match_quality": "high"
      }
    }
  ]
}
```

---

## AI任务流程

### 第一步：检查触发条件

AI首先检查触发条件是否满足：

```
检查步骤：
1. 使用LS工具确认images文件夹存在
2. 使用LS工具确认image_manifest.json存在（可选）
3. 如果不满足，提示用户："请先运行extract_images.py脚本提取图片"
4. 如果满足，继续下一步
```

### 第二步：读取所有图片文件

AI浏览images文件夹，读取所有图片文件：

- 使用LS工具查看images文件夹内容
- 使用Read工具逐个读取图片文件（支持PNG/JPG/JPEG格式）
- 每张图片都需要AI通过视觉理解判断内容

**注意**：AI的多模态能力可以直接读取图片内容，无需额外处理。

### 第三步：分析每张图片内容

AI对每张图片进行分析，判断以下信息：

#### 1. 图片类型判断

识别图片属于哪种类型：

- `map`：地图（世界地图、区域地图、地形图、气候图等）
- `chart`：统计图表（柱状图、折线图、饼图、散点图等）
- `diagram`：示意图（流程图、结构图、原理图等）
- `landscape`：景观图（实景照片、地貌照片等）
- `option_diagram`：选项示意图（①②③④等小图）
- `other`：其他类型（无法归类）

#### 2. 图片内容描述

简洁描述图片内容（不超过30字）：

- 地图：描述区域范围和主题内容（如"世界地图，显示洋流分布"）
- 图表：描述图表类型和数据内容（如"柱状图，显示各省份人口"）
- 示意图：描述图示内容（如"水循环示意图"）
- 景观图：描述景观类型（如"山地地貌景观"）

#### 3. 图片用途推断

判断图片在试卷中的用途：

- `material`：材料图片（用于题目背景，配合材料文字）
- `option`：选项图片（选择题选项中的图片，包含①②③④编号）
- `question`：题目图片（题目本身包含的图片，题目要求读图）
- `unknown`：无法判断（缺乏上下文信息或类型模糊）

#### 4. 置信度标记

标记判断的置信度（0.0-1.0）：

- 0.9-1.0：非常确定（类型明确，用途清晰）
- 0.7-0.9：较确定（类型较明确，用途基本清晰）
- 0.5-0.7：一般确定（类型基本明确，用途有一定依据）
- < 0.5：不确定（类型模糊或用途难以判断）

#### 5. 上下文关联（如果有image_manifest.json）

结合上下文信息判断：

- before_text：图片前文内容
- after_text：图片后文内容
- 判断图片用途是否与上下文匹配

### 第四步：输出JSON

AI使用Write工具输出images_analysis.json：

- JSON格式必须正确
- 包含所有图片的分析结果
- 文件保存到与images文件夹同目录
- 文件名：images_analysis.json

---

## 参考文档

详见 `references/image_types.md`，包含：
- 地理试卷常见图片类型分类
- 每种类型的特征描述
- 用途判断依据

AI在分析图片时可以参考该文档，提高判断准确性。

---

## AI能力要求

- **多模态能力**：必须支持图片视觉理解（Claude 3.5 Sonnet）
- **地理知识**：理解地图、地理图表等专业内容
- **JSON输出**：输出格式正确的JSON

---

## 注意事项

### 1. 置信度标记原则

- 不要过度自信，如果图片类型模糊，置信度应降低
- 如果缺乏上下文信息，用途判断置信度应降低
- 只有类型明确且用途清晰时，才标记为0.9-1.0

### 2. 无法判断的处理

- 如果图片类型无法归类，标记为"other"
- 在reason字段说明原因（如"图片模糊"、"类型不常见"）
- 置信度设为0.0

### 3. 图片描述简洁性

- 不超过30字
- 描述关键内容，不描述细节
- 地图重点描述区域和主题，图表重点描述类型和数据

### 4. 多图组合处理

如果一张图片包含多个子图（如①②③④）：
- 类型标记为"option_diagram"
- 在description中说明子图数量（如"四个示意图，分别表示①②③④"）
- 用途标记为"option"

### 5. 地图细节描述

地图图片要详细描述：
- 区域范围：世界/国家/区域/省份
- 主题内容：洋流/地形/气候/人口等

### 6. 脚本使用约束（强制）

**AI不得自行编写任何脚本**：本skill为纯AI操作skill，AI应通过自身多模态能力完成图片分析，**绝不编写Python脚本或其他代码脚本**来辅助处理。

---

## 与后续skill的衔接

本skill输出的images_analysis.json将作为geo-exam-image-insertion skill的输入，用于判断图片插入位置。

**衔接流程**：
1. 本skill生成images_analysis.json
2. geo-exam-image-insertion读取images_analysis.json和初步清理.docx
3. geo-exam-image-insertion根据图片分析结果判断插入位置

---

## 示例

### 示例1：地图图片分析

**图片内容**：世界地图，显示主要洋流分布

**分析结果**：
```json
{
  "filename": "img_001.png",
  "type": "map",
  "description": "世界地图，显示洋流分布",
  "inferred_usage": "material",
  "confidence": 0.95,
  "reason": "图片是世界地图，显示洋流分布，结合上下文'洋流对海洋生物的影响'判断为材料图",
  "context_match": {
    "before_text": "阅读图文材料，完成下列要求。",
    "after_text": "洋流对海洋生物的影响...",
    "match_quality": "high"
  }
}
```

### 示例2：选项示意图分析

**图片内容**：四个小示意图，分别表示①②③④

**分析结果**：
```json
{
  "filename": "img_002.png",
  "type": "option_diagram",
  "description": "四个示意图，表示①②③④",
  "inferred_usage": "option",
  "confidence": 0.90,
  "reason": "图片包含四个编号示意图，符合选择题选项图特征",
  "context_match": {
    "before_text": "A. ①③",
    "after_text": "B. ②④",
    "match_quality": "high"
  }
}
```

### 示例3：景观图分析

**图片内容**：山地地貌实景照片

**分析结果**：
```json
{
  "filename": "img_003.png",
  "type": "landscape",
  "description": "山地地貌景观",
  "inferred_usage": "material",
  "confidence": 0.85,
  "reason": "图片是地貌景观照片，结合上下文判断为材料图",
  "context_match": {
    "before_text": "下图为某山地景观...",
    "after_text": "据此回答...",
    "match_quality": "medium"
  }
}
```

---

## 错误处理

### 如果images文件夹不存在

提示用户："请先运行extract_images.py脚本提取图片，确保images文件夹已生成。"

### 如果图片无法读取

在JSON中记录错误信息：
```json
{
  "filename": "img_001.png",
  "type": "other",
  "description": "无法读取图片",
  "inferred_usage": "unknown",
  "confidence": 0.0,
  "reason": "图片文件损坏或格式不支持"
}
```

### 如果JSON输出失败

提示用户："JSON格式错误，请检查AI输出。重新尝试分析图片。"

---

## 总结

本skill是清洗阶段的关键AI操作，通过多模态能力分析图片内容，为后续图片插入提供依据。

**核心要点**：
- AI主导图片分析，不依赖代码
- 明确触发时机和检查步骤
- 输出结构化JSON供后续使用
- 置信度标记反映判断可靠性