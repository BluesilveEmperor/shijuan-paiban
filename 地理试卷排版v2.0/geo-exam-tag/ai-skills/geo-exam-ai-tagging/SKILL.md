---
name: geo-exam-ai-tagging
description: "地理试卷AI主导打标skill。AI读取插入图片后.docx，通过语义理解识别试卷结构（题型分区、题组、题目、选项、图片位置），输出完整结构化JSON。清洗阶段生成插入图片后.docx后自动触发。AI语义理解主导，不依赖正则匹配。"
---

# 地理试卷AI主导打标 Skill

## 触发时机（必须明确）

**自动触发条件**：
1. geo-exam-image-insertion skill执行完毕
2. 插入图片后.docx已生成（包含图片占位符）

**手动触发条件**：
- 用户明确要求"AI打标"
- 用户提到"理解试卷结构"、"结构化输出"

**触发检查**：
- AI必须先检查插入图片后.docx是否存在
- 如果不存在，提示用户先运行清洗阶段

---

## 输入

**必需输入**：
- `插入图片后.docx`：包含图片占位符的文档

**可选输入**：
- `images_analysis.json`：图片内容分析，提供图片信息
- `参考/exam-json-examples/`：参考试卷JSON示例，提高一致性

**输入位置**：
- 文件位于output目录下

---

## 输出

**输出文件**：
- `tagged_ai.json`：AI打标结果（完整JSON）

**输出位置**：
- 与插入图片后.docx同目录

**JSON格式**：
详见 `references/json_template.md`

---

## AI任务流程

### 第一步：检查触发条件

AI首先检查触发条件是否满足：
```
检查步骤：
1. 确认插入图片后.docx存在
2. 如果不满足，提示用户先运行清洗阶段
```

### 第二步：读取文档全文

AI读取"插入图片后.docx"，理解文档结构：
- 考试信息（标题、注意事项、卷次）
- 题型分区（选择题、非选择题）
- 题组结构（材料、引导语、题目）
- 图片占位符位置（【图片：...】）

### 第三步：识别试卷结构

AI通过语义理解识别结构（不依赖正则匹配）：

**考试信息识别**：
- 考试名称：包含"考试"关键词的标题段落
- 科目名称：包含"地理"关键词
- 注意事项：包含"注意事项"关键词的段落

**题型分区识别**：
- 选择题区：包含"选择题"关键词
- 非选择题区：包含"非选择题"、"综合题"关键词

**题组识别**：
- 材料+引导语+题目组合判断
- 题号连续性判断题组范围

**题目识别**：
- 题干：题号开头的段落
- 选项：选项字母开头的段落
- 子问题：括号编号开头

**图片占位符识别**：
- 识别【图片：<filename> - <description>】占位符
- 在JSON中记录图片引用

### 第四步：输出完整JSON

AI输出tagged_ai.json，格式参考 `references/json_template.md`：
- JSON结构必须完整
- 包含所有必要字段
- 图片引用使用filename（不带路径）

---

## 参考文档

详见：
- `references/json_template.md`：完整JSON结构模板
- `references/json_schema.json`：JSON Schema定义
- `references/exam_examples.md`：参考试卷JSON示例

---

## JSON格式要求

**必需字段**：
```json
{
  "exam_info": {
    "exam_name": "考试名称",
    "subject": "地理"
  },
  "sections": [
    {
      "section_id": 1,
      "section_type": "选择题",
      "question_groups": [
        {
          "group_id": "1-2",
          "materials": [...],
          "questions": [...]
        }
      ]
    }
  ],
  "source": "ai",
  "confidence": "medium"
}
```

详见 `references/json_schema.json`

---

## AI能力要求

- **语义理解**：理解试卷结构，不依赖固定格式
- **上下文理解**：理解材料、题目、选项的关联
- **JSON输出**：输出格式正确的JSON

---

## 注意事项

1. **不依赖正则匹配**：
   - AI通过语义理解识别结构
   - 兼容非标准格式试卷

2. **图片处理（强约束）**：
   - **格式A**：图片必须放在 `materials[].images` 数组中，不可嵌入文本
   - **格式B（segments）**：图片必须使用 `{"type": "image", "name": "filename"}` 独立segment
   - **禁止**将图片占位符作为普通文本放入 `{"type": "text"}` segment
   - 图片引用使用filename（不带路径）
   - 正确示例和错误示例见下：

   **正确（格式A）**：
   ```json
   {"text": "...", "images": ["img_001.png"]}
   ```

   **正确（格式B）**：
   ```json
   {"type": "image", "name": "img_001.png", "width_cm": null, "height_cm": null}
   ```

   **错误**：
   ```json
   {"type": "text", "content": "【图片：img_001.png - 描述】"}
   ```

3. **置信度标记**：
   - AI输出标记为"medium"置信度
   - 不确定的部分标记"unknown"

4. **脚本使用约束（强制）**：**AI不得自行编写任何脚本**。本skill为纯AI操作skill，AI应通过自身语义理解能力完成试卷结构识别，**绝不编写Python脚本或其他代码脚本**来辅助处理。

---

## 与后续skill的衔接

本skill输出的tagged_ai.json将与tagged_script.json一起输入geo-exam-merge-validation进行融合验证。