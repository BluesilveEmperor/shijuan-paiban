# 地理试卷打标JSON结构模板

## 一、完整JSON结构

```json
{
  "exam_info": {
    "exam_name": "2025年海南省普通高中学业水平选择性考试",
    "subject": "地理",
    "notes": "注意事项内容..."
  },
  "sections": [
    {
      "section_id": 1,
      "section_title": "一、选择题：本题共15小题...",
      "section_type": "选择题",
      "question_groups": [
        {
          "group_id": "1-2",
          "materials": [
            {
              "text": "阅读图文材料，完成下列要求。",
              "images": ["img_001.png"],
              "tables": [],
              "notes": []
            }
          ],
          "instruction": "据此完成下面小题。",
          "questions": [
            {
              "question_number": 1,
              "question_type": "选择题",
              "stem": "洋流对海洋生物的影响...",
              "sub_options": ["①...", "②...", "③...", "④..."],
              "options": {
                "A": "①③",
                "B": "②④",
                "C": "①④",
                "D": "②③"
              }
            },
            {
              "question_number": 2,
              "question_type": "选择题",
              "stem": "题干内容...",
              "sub_options": null,
              "options": {
                "A": "选项内容A",
                "B": "选项内容B",
                "C": "选项内容C",
                "D": "选项内容D"
              }
            }
          ]
        }
      ]
    },
    {
      "section_id": 2,
      "section_title": "二、非选择题：本题共4小题...",
      "section_type": "非选择题",
      "question_groups": [
        {
          "group_id": "17",
          "materials": [
            {
              "text": "阅读图文材料...",
              "images": ["img_002.png"],
              "tables": []
            }
          ],
          "instruction": null,
          "questions": [
            {
              "question_number": 17,
              "question_type": "非选择题",
              "stem": "17. 阅读图文材料，完成下列要求。",
              "sub_options": null,
              "options": null,
              "sub_questions": [
                {
                  "sub_number": 1,
                  "text": "（1）图中①表示..."
                },
                {
                  "sub_number": 2,
                  "text": "（2）分析原因..."
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "source": "ai",
  "confidence": "medium"
}
```

---

## 二、字段说明

### exam_info字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| exam_name | string | 必需 | 考试完整名称 |
| subject | string | 必需 | 科目名称（固定为"地理"） |
| notes | string | 可选 | 注意事项内容 |

### sections字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| section_id | integer | 必需 | 分区编号（1, 2, 3...） |
| section_title | string | 必需 | 分区标题完整文字 |
| section_type | string | 必需 | 分区类型（选择题/非选择题/填空题） |
| question_groups | array | 必需 | 题组数组 |

### question_groups字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| group_id | string | 必需 | 题组ID（如"1-2"或"17"） |
| materials | array | 必需 | 材料数组 |
| instruction | string | 可选 | 引导语（如"据此完成下面小题。"） |
| questions | array | 必需 | 题目数组 |

### materials字段

**格式A（旧格式，推荐AI轨道使用）**：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| text | string | 必需 | 材料文字内容 |
| images | array | 可选 | 图片文件名数组（如["img_001.png"]） |
| tables | array | 可选 | 表格引用数组 |
| notes | array | 可选 | 注释数组 |

**格式B（segments格式，脚本轨道使用）**：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| segments | array | 必需 | 段落数组 |
| tables | array | 可选 | 表格数据数组 |

**segments数组元素类型**：

| type | 必需字段 | 说明 |
|------|----------|------|
| `text` | `content` | 普通文本段落 |
| `image` | `name`, `width_cm`, `height_cm` | 图片段落（`width_cm`/`height_cm`可为null） |
| `table` | `table_id` | 表格段落（引用tables数组中的数据） |

**关键约束**：图片必须使用 `type: "image"` 的独立segment，**不可**将图片信息嵌入文本segment中。

### questions字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| question_number | integer | 必需 | 题号（如1, 2, 17...） |
| question_type | string | 必需 | 题目类型（选择题/非选择题） |
| stem | string | 必需 | 题干内容 |
| sub_options | array/null | 可选 | 子选项（①②③④） |
| options | object/null | 可选 | ABCD选项（选择题必需） |
| sub_questions | array/null | 可选 | 子问题（非选择题） |

### options字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| A | string | 必需 | 选项A内容 |
| B | string | 必需 | 选项B内容 |
| C | string | 必需 | 选项C内容 |
| D | string | 必需 | 选项D内容 |

---

## 三、图片引用规则

**图片占位符识别**：
- 格式：【图片：<filename> - <description>】
- AI识别占位符后，提取filename
- 嵌入到对应字段的images数组

**示例**：
```
材料段落："阅读图文材料。【图片：img_001.png - 世界地图】"
JSON中："images": ["img_001.png"]
```

---

## 四、特殊情况处理

### 无材料题组

如果题目没有材料，materials数组为空：
```json
{
  "materials": [],
  "instruction": null,
  "questions": [...]
}
```

### 图片选项

如果选项包含图片占位符：
```json
{
  "options": {
    "A": "①③【图片：img_002.png】",
    "B": "②④",
    "C": "①④",
    "D": "②③"
  }
}
```

### 子问题编号

非选择题的子问题：
```json
{
  "sub_questions": [
    {
      "sub_number": 1,
      "text": "（1）图中①表示..."
    },
    {
      "sub_number": 2,
      "text": "（2）分析原因..."
    }
  ]
}
```