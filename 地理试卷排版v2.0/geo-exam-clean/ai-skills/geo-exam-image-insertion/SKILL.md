---
name: geo-exam-image-insertion
description: "地理试卷图片占位符插入skill。AI读取初步清理.docx和images_analysis.json，判断哪些位置需要图片但未放置，插入图片占位符【图片：<filename> - <description>】，输出插入图片后.docx。geo-exam-image-analysis执行完毕后自动触发。AI主导判断和插入，不依赖代码。"
---

# 地理试卷图片占位符插入 Skill

## 触发时机（必须明确）

**自动触发条件**：
1. geo-exam-image-analysis skill执行完毕
2. images_analysis.json已生成
3. 初步清理.docx已生成（不含图片，只有文字）

**手动触发条件**：
- 用户明确要求"插入图片占位符"
- 用户提到"图片位置"、"插入图片标记"

**触发检查**：
- AI必须先检查images_analysis.json是否存在
- 检查初步清理.docx是否存在
- 如果不存在，提示用户先运行前序步骤

---

## 输入

**必需输入**：
- `初步清理.docx`：清洗后的文档（不含图片，只有文字）
- `images_analysis.json`：图片内容分析结果

**可选输入**：
- `images/`文件夹：图片文件，用于确认图片存在

**输入位置**：
- 文件位于output目录下（如output/初步清理.docx）

---

## 输出

**输出文件**：
- `插入图片后.docx`：包含图片占位符的文档
- `image_insertion_log.json`：图片插入日志

**输出位置**：
- 与初步清理.docx同目录（如output/插入图片后.docx）

**图片占位符格式**：
```
【图片：<filename> - <description>】
```

示例：
```
【图片：img_001.png - 世界地图，显示洋流分布】
```

---

## AI任务流程

### 第一步：检查触发条件

AI首先检查触发条件是否满足：
```
检查步骤：
1. 确认images_analysis.json存在
2. 确认初步清理.docx存在
3. 如果不满足，提示用户先运行前序步骤
```

### 第二步：读取文档全文

AI读取"初步清理.docx"，理解文档结构：
- 考试信息（标题、注意事项等）
- 题型分区（选择题、非选择题）
- 题组结构（材料、题干、选项）
- 段落顺序和内容

### 第三步：匹配图片与文档位置

AI结合images_analysis.json，判断每张图片应该插入的位置：

**材料图匹配规则**：
- 图片用途标记为"material"
- 查找文档中"阅读图文材料"、"读图回答"等引导语
- 在引导语所在段落或前一个段落插入占位符

**选项图匹配规则**：
- 图片用途标记为"option"
- 查找文档中选项段落（A. B. C. D.）
- 在选项文字中插入图片占位符

**题目图匹配规则**：
- 图片用途标记为"question"
- 查找文档中题干段落
- 在题干文字中插入图片占位符

**无法确定位置的图片**：
- 标记为"unknown"
- 在文档末尾插入占位符
- 在日志中标记"待人工确认"

### 第四步：插入图片占位符

AI在文档中插入图片占位符：
- 使用Edit工具编辑文档
- 插入格式：【图片：<filename> - <description>】
- 不破坏文档原有结构

### 第五步：保存文档

AI保存修改后的文档：
- 使用Write工具保存为"插入图片后.docx"
- 文件位于output目录

### 第六步：输出插入日志

AI输出image_insertion_log.json，记录每张图片的插入位置：
```json
{
  "insertion_timestamp": "2026-07-02T11:00:00",
  "total_images": 12,
  "inserted_images": 10,
  "pending_images": 2,
  "insertions": [
    {
      "filename": "img_001.png",
      "insert_position": {
        "paragraph_index": 15,
        "insert_type": "new_paragraph",
        "context": "阅读图文材料，完成下列要求。"
      },
      "placeholder": "【图片：img_001.png - 世界地图，显示洋流分布】",
      "status": "success"
    }
  ]
}
```

---

## 参考文档

详见 `references/placeholder_rules.md`，包含：
- 不同用途图片的插入位置规则
- 占位符格式规范
- 特殊情况处理

---

## AI能力要求

- **文档理解**：理解试卷结构、段落内容
- **图片匹配**：根据图片描述匹配文档位置
- **位置判断**：判断图片应该插入的具体位置
- **文档编辑**：在文档中插入占位符文字

---

## 注意事项

1. **保持段落顺序**：
   - 不改变文档原有段落顺序
   - 图片占位符插入到合适位置

2. **占位符格式统一**：
   - 使用中文方括号【】
   - 使用中文冒号：
   - 使用短横线 - 分隔

3. **待确认图片**：
   - 无法确定位置的图片，插入到文档末尾
   - 占位符格式：【图片待确认：<filename> - <description>】

4. **脚本使用约束（强制）**：**AI不得自行编写任何脚本**。本skill为纯AI操作skill，AI应通过自身能力完成图片占位符插入，**绝不编写Python脚本或其他代码脚本**来辅助处理。

---

## 与后续skill的衔接

本skill输出的"插入图片后.docx"将作为打标阶段（geo-exam-tag）的输入。
image_insertion_log.json将作为打标阶段的参考信息。