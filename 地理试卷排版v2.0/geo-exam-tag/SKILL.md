---
name: geo-exam-tag
description: "地理试卷打标skill（AI主导架构）。AI执行打标脚本（tag_docx.py），然后AI skills（geo-exam-ai-tagging和geo-exam-merge-validation）自动触发完成双轨并行打标和融合验证。当用户提到打标、结构化、解析试卷结构、提取题目等场景时使用本skill。"
---

# 地理试卷打标 Skill（AI主导架构）

## 概述

本skill是地理试卷排版的**打标阶段**，采用AI主导架构。AI执行打标脚本，然后内部AI skills自动触发完成双轨并行和融合验证。

**AI主导流程**：
```
AI触发geo-exam-tag
  ↓
AI执行tag_docx.py脚本（正则匹配打标）
  ↓
geo-exam-ai-tagging自动触发（AI语义理解打标）
  ↓
geo-exam-merge-validation自动触发（融合验证）
  ↓
输出：tagged_final.json + validation_report.json
```

**双轨并行架构**：
```
插入图片后.docx
  ↓
  ├─ [脚本轨道] tag_docx.py → tagged_script.json
  │
  └─ [AI轨道] geo-exam-ai-tagging → tagged_ai.json
  ↓
geo-exam-merge-validation → tagged_final.json
```

---

## 触发时机

**自动触发条件**：
- geo-exam-formatting主skill执行阶段2时触发（清洗完成后）
- 用户明确要求"打标"、"结构化试卷"
- 用户提到"解析试卷结构"、"提取题目"

**触发检查**：
AI应先检查：
- 输入文件是否为"插入图片后.docx"（清洗阶段输出）
- images_analysis.json是否存在（提供图片信息）
- 如不满足，提示用户先运行geo-exam-clean

---

## AI执行流程

### 步骤1：执行打标脚本

AI使用RunCommand工具执行tag_docx.py：

```powershell
python scripts/tag_docx.py --input "插入图片后.docx" --output "tagged_script.json"
```

**脚本功能**：
- 识别试卷结构（分区、题组、题目）
- 正则模式匹配（标准格式试卷）
- 提取题干、选项、材料
- 记录不确定段落（uncertain_paragraphs）
- 识别图片占位符【图片：<filename> - <description>】

**输出文件**：
- `tagged_script.json`：脚本打标结果
- `tag_log.txt`：打标过程日志

**AI职责**：
- 执行脚本
- 检查tagged_script.json是否生成
- 检查tag_log.txt日志内容
- 统计不确定段落数量

### 步骤2：等待AI skills自动触发

AI skills会在tag_docx.py完成后**自动触发**：

#### geo-exam-ai-tagging自动触发

**触发条件**：清洗阶段生成"插入图片后.docx"后自动触发

**AI职责**：等待该skill自动执行，无需手动触发

**该skill会**：
- 读取插入图片后.docx
- AI语义理解试卷结构（不依赖正则）
- 输出tagged_ai.json

**关键点**：
- 该skill与tag_docx.py**并行执行**（双轨并行）
- AI通过语义理解，兼容非标准格式试卷
- 输出完整JSON，包含图片引用

#### geo-exam-merge-validation自动触发

**触发条件**：geo-exam-ai-tagging和tag_docx.py都执行完毕后自动触发

**AI职责**：等待该skill自动执行，无需手动触发

**该skill会**：
- 对比tagged_script.json和tagged_ai.json
- 执行格式验证和逻辑验证
- 融合双轨结果
- 输出tagged_final.json和validation_report.json
- 标记置信度（high/medium/low/failed）

**关键点**：
- 双轨结果融合，提高准确性
- 验证机制保障输出质量
- 置信度标记供用户参考

### 步骤3：检查最终输出

AI应检查打标阶段最终输出：

| 文件 | 说明 | 必须生成 |
|------|------|----------|
| `tagged_final.json` | 融合后的最终打标结果 | ✅ 必须有 |
| `validation_report.json` | 验证报告 | ✅ 必须有 |
| `tagged_script.json` | 脚本打标结果（中间产物） | 可选 |
| `tagged_ai.json` | AI打标结果（中间产物） | 可选 |
| `tag_log.txt` | 打标过程日志 | 可选 |

**检查要点**：
- tagged_final.json的final_confidence字段
- validation_report.json的验证结果
- 如果置信度为"low"或"failed"，向用户提示

---

## 输出目录结构

打标阶段输出应保存到用户指定目录：

```
<输出目录>/
├── tagged_script.json           ← 脚本打标结果（中间产物）
├── tagged_ai.json               ← AI打标结果（中间产物）
├── tagged_final.json            ← 最终打标结果
├── validation_report.json       ← 验证报告
└── tag_log.txt                  ← 打标过程日志
```

---

## 内部AI skills说明

本skill包含2个内部AI skills：

| AI skill | 触发时机 | 功能 |
|----------|----------|------|
| geo-exam-ai-tagging | "插入图片后.docx"生成后 | AI语义理解打标 |
| geo-exam-merge-validation | tagged_script.json和tagged_ai.json都生成后 | 融合验证 |

**关键机制**：
- 这些AI skills通过description字段定义的触发条件**自动触发**
- geo-exam-ai-tagging与tag_docx.py**并行执行**
- AI无需手动触发，只需等待它们执行
- AI skills执行完成后，会生成对应的JSON文件

---

## 双轨并行架构详解

### 脚本轨道（确定性）

**执行者**：tag_docx.py脚本

**特点**：
- 正则模式匹配，确定性高
- 处理标准格式试卷准确率高
- 对非标准格式试卷兼容性差
- 输出uncertain_paragraphs标记不确定段落

**适用场景**：
- 标准格式试卷（如"一、选择题：本题共15小题..."）
- 需要确定性保障的场景

### AI轨道（适应性）

**执行者**：geo-exam-ai-tagging skill

**特点**：
- AI语义理解，适应性强
- 兼容各种非标准格式
- 图片占位符识别准确
- Token消耗较高

**适用场景**：
- 非标准格式试卷（如"第I卷"、"第一部分"）
- 包含大量图片的试卷

### 融合验证

**执行者**：geo-exam-merge-validation skill

**融合策略**：
- 格式都正确且一致 → 优先采用AI结果
- 格式都正确但不一致 → 标记差异，记录两个版本
- 单轨通过 → 使用通过的轨道
- 双轨都失败 → 输出空JSON，标记failed

**验证内容**：
- 格式验证：必需字段、结构完整性
- 逻辑验证：题号连续性、选项完整性、题组归属
- 置信度标记：high/medium/low/failed

---

## 脚本调用参数说明

### tag_docx.py参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input` | 输入文件路径（插入图片后.docx） | 必填 |
| `--output` | 输出JSON路径 | 必填 |
| `--images-analysis` | 图片分析JSON路径 | 可选 |
| `--log` | 日志文件路径 | `<输出目录>/tag_log.txt` |

---

## 脚本使用约束（强制）

**AI必须严格遵守以下约束**：

1. **禁止自行编写脚本**：AI不得自己书写任何Python脚本或其他代码脚本，也不得用Write工具创建新的脚本文件。
2. **只能使用项目已有脚本**：AI只能通过RunCommand工具调用本skill目录下已有的脚本：
   - `scripts/tag_docx.py`（打标脚本）
3. **功能不足时的处理**：如遇脚本功能不足，应向用户说明情况，**绝不自行编写替代脚本**。

---

## 注意事项

### 1. 不要替代AI skills

AI在执行本skill时，**不要尝试替代内部AI skills**：
- 不要自己语义理解试卷结构（应由geo-exam-ai-tagging完成）
- 不要自己融合验证（应由geo-exam-merge-validation完成）

AI只需**执行脚本并等待**内部AI skills自动触发。

### 2. 检查双轨输出

AI应在双轨完成后检查输出：
- tagged_script.json（脚本轨道）
- tagged_ai.json（AI轨道）
- tagged_final.json（融合结果）
- validation_report.json（验证报告）

### 3. 处理置信度低的场景

如果validation_report.json显示final_confidence为"low"或"failed"：
- 向用户提示"打标置信度较低，建议人工检查"
- 在质检报告中标记警告
- 提供validation_report.json供用户查看

---

## 总结

本skill是打标阶段的AI主导执行器。AI执行脚本后，内部AI skills自动触发完成双轨并行和融合验证。

**核心要点**：
- AI执行项目已有脚本，通过RunCommand工具调用
- 双轨并行：脚本轨道+AI轨道
- 内部AI skills自动触发，无需手动调用
- AI检查输出文件完整性和置信度
- 输出tagged_final.json供排版阶段使用