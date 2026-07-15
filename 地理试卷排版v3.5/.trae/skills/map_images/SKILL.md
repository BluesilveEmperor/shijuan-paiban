---
name: "map_images"
description: "Fallback skill for image mapping correction. Primary path is map_images.py script. AI only intervenes when the script produces unmapped items or low-confidence results. Invoke as Step5c only if Step5a (script) has unresolved issues."
---

# Step5c: map_images — AI 兜底修正（v3.6 脚本优先模式）

## Role

你是"图片映射兜底修正专家"。**主要映射工作已由 `map_images.py` 脚本完成**（Track1 inline 代码确定 + Track2 anchor 关键词/顺序匹配）。你仅在脚本无法处理的场景下介入：审核未映射项、修正低置信度映射、处理边缘情况。

**你绝对不做**：全文重写 `final_exam.json`、重新匹配所有图片、修改试卷结构。

---

## Input

| 文件 | 说明 |
|------|------|
| `{工作目录}/试卷数据/final_exam.json` | 脚本已生成的最终 JSON（**已含完整结构和脚本映射结果**） |
| `{工作目录}/中间数据/anchor_descriptions.json` | 仅 anchor 图的 AI 内容分析（如需参考） |
| `{工作目录}/清洗产物/content.md` | 清洗后的试卷全文（如需确认上下文） |

---

## Task

### 第一步：检查是否需要介入

读取 `final_exam.json` → `validation` 字段，判断是否需要 AI 介入：

```
如果 validation.unmapped_placeholders 为空 && validation.unused_images 为空 && validation.warnings 为空：
    → 脚本已完成所有映射，无需 AI 介入，直接报告"完成"。

如果存在未映射项 或 低置信度映射（confidence < 0.6）：
    → 进入第二步，仅处理问题项。
```

### 第二步：仅处理问题项

**只读取和修改以下内容**：

1. `validation.unmapped_placeholders` 列表中的占位符
2. `validation.unused_images` 列表中的图片
3. `image_mapping` 中 `confidence < 0.6` 的条目

**不读取、不修改**：`meta`、`document.sections`（已由 Step2/3 完成，你不碰）。

### 第三步：逐项审核

对每个未映射的占位符，在 `anchor_descriptions.json` 中找到对应的图片描述，结合 `content.md` 中的上下文：
- 如果占位符确实无法匹配任何图片 → 保持 unmapped
- 如果找到了匹配 → 记录修正

### 第四步：输出覆盖文件

输出 `{工作目录}/中间数据/image_mapping_overrides.json`（**仅包含修正项，~10-30行**）：

```json
{
  "mappings": [
    {
      "placeholder_id": "ph_anchor_002",
      "image_id": "img_005",
      "confidence": 0.75,
      "reason": "手动修正：图片为'巴西汽车产业链分布图'，与第17题材料'巴西新能源汽车产业'语义匹配",
      "track": "ai"
    }
  ],
  "validation": {
    "has_unmapped_placeholders": true,
    "has_unused_images": false,
    "unmapped_placeholders": ["ph_anchor_001"],
    "unused_images": [],
    "warnings": [
      "ph_anchor_001: 无对应图片，材料为纯表格"
    ]
  }
}
```

---

## Constraints

### 强制约束（v3.6 新增，违反即失败）

1. ❌ **禁止全文输出 final_exam.json**：只输出 `image_mapping_overrides.json`（delta），主编排会用脚本合并
2. ❌ **禁止重新匹配已映射的图片**：`image_mapping` 中 `confidence >= 0.6` 的项保持不变
3. ❌ **禁止修改试卷结构**：不读、不改 `document.sections` 中的任何字段
4. ✅ **只处理问题项**：仅关注 unmapped / unused / low_confidence 条目
5. ✅ **输出文件不超过 50 行**

### 业务约束

6. **不新增或删除占位符**：占位符列表来自 Step3，你只做修正
7. **不重分析图片内容**：图片描述来自 Step4，你只读取
8. **不强行匹配**：无法匹配的保留 unmapped
9. **置信度低于 0.5 不进映射**：无明显匹配依据标记 unmapped

---

## Output Format

输出文件：`{工作目录}/中间数据/image_mapping_overrides.json`

**仅包含修正项**，格式如上第四步所示。

输出后向主编排报告：
- 审核了哪些未映射项
- 成功修正了几项
- 仍无法匹配的项及原因

---

## 合并方式（由主编排执行）

AI 输出 `image_mapping_overrides.json` 后，主编排运行以下命令合并到 `final_exam.json`：

```powershell
python -c "
import json
with open('{工作目录}/试卷数据/final_exam.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
with open('{工作目录}/中间数据/image_mapping_overrides.json', 'r', encoding='utf-8') as f:
    overrides = json.load(f)
# 应用覆盖
existing = {m['placeholder_id']: m for m in data['image_mapping']}
for m in overrides.get('mappings', []):
    existing[m['placeholder_id']] = m
data['image_mapping'] = list(existing.values())
data['validation'] = overrides.get('validation', data['validation'])
with open('{工作目录}/试卷数据/final_exam.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('覆盖已应用')
"
```

---

## Self-check

- [ ] 是否只输出了 `image_mapping_overrides.json`（没有重写 final_exam.json）？
- [ ] 是否只处理了 unmapped / unused / low_confidence 项？
- [ ] 是否没有修改 `document.sections` 中的内容？
- [ ] 输出文件是否不超过 50 行？
- [ ] 如果没有任何问题项，是否直接报告"完成"而不输出任何文件？
