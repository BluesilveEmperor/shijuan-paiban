---
name: geo-exam-formatting
description: "地理试卷排版主skill，编排清洗→打标→排版三步AI主导流水线。AI直接读取并执行各个子skills（geo-exam-clean、geo-exam-tag、geo-exam-format），各子skill内部的AI skills自动触发。当用户提到排版试卷、试卷排版、地理试卷、批量排版、处理试卷等场景时务必使用本skill。"
---

# 地理试卷排版主 Skill（AI主导架构）

## 概述

本skill是"地理试卷排版"系统的**AI主导编排入口**。AI通过读取并执行各个子skills完成完整流水线，而非调用脚本。

**核心架构**：AI执行skills（AI读取skills → AI触发子skills → AI在子skills内部调用脚本）

**AI主导流程**：
```
用户触发geo-exam-formatting
  ↓
AI读取本SKILL.md（获取流程指引）
  ↓
AI按流程执行各阶段：
  
  【阶段1：清洗】AI触发geo-exam-clean skill
    → AI执行清洗脚本（clean_docx.py）
    → AI执行图片提取脚本（extract_images.py）
    → AI自动触发geo-exam-image-analysis（分析图片内容）
    → AI自动触发geo-exam-image-insertion（插入图片占位符）
  
  【阶段2：打标】AI触发geo-exam-tag skill
    → AI执行打标脚本（tag_docx.py）
    → AI自动触发geo-exam-ai-tagging（AI语义理解打标）
    → AI自动触发geo-exam-merge-validation（融合验证）
  
  【阶段3：排版】AI触发geo-exam-format skill
    → AI执行排版脚本（format_docx.py）
```

---

## 脚本使用约束（强制）

**AI必须严格遵守以下约束**：

1. **禁止自行编写脚本**：AI不得自己书写任何Python脚本、Shell脚本或其他代码脚本，也不得用Write工具创建新的脚本文件。
2. **只能使用项目已有脚本**：AI只能调用本项目中已存在的脚本文件，通过RunCommand工具执行。
3. **可用脚本清单**：
   - 清洗阶段：`geo-exam-clean/scripts/clean_docx.py`、`geo-exam-clean/scripts/extract_images.py`
   - 打标阶段：`geo-exam-tag/scripts/tag_docx.py`
   - 排版阶段：`geo-exam-format/scripts/format_docx.py`
4. **功能不足时的处理**：如遇已有脚本功能不足，应向用户说明情况并请求处理，**绝不自行编写替代脚本**。

---

## 触发时机

**本skill触发后，AI应按以下流程执行**：

### 自动触发条件
- 用户提到"排版试卷"、"试卷排版"、"地理试卷"
- 用户提到"批量排版"、"处理试卷"
- 用户上传.docx试卷文件并要求排版

### 触发检查
AI应先检查：
- 输入文件是否为.docx格式
- 文件路径是否正确
- 如不满足，提示用户提供正确的输入文件

---

## AI执行流程（完整指引）

### 步骤1：准备输入文件

AI首先确认输入文件：
- 单个文件：用户提供具体.docx文件路径
- 多个文件：用户提供文件列表或目录路径
- AI使用Glob或LS工具收集所有.docx文件

**输入文件要求**：
- 格式：.docx（Word文档）
- 来源：从学科网等平台下载的高考真题
- 状态：未清洗的原始试卷

### 步骤2：执行清洗阶段

AI触发**geo-exam-clean** skill：

**执行方式**：
```
AI读取geo-exam-clean/SKILL.md
AI按照geo-exam-clean的流程执行：
  1. 调用clean_docx.py脚本（删除无关内容）
  2. 调用extract_images.py脚本（提取所有图片）
  3. 等待geo-exam-image-analysis自动触发
  4. 等待geo-exam-image-insertion自动触发
```

**AI职责**：
- 使用RunCommand工具执行Python脚本
- 检查脚本输出是否成功
- 确认中间文件已生成（cleaned.docx、初步清理.docx、images/、images_analysis.json等）

**关键点**：
- geo-exam-image-analysis和geo-exam-image-insertion会在extract_images.py完成后**自动触发**
- AI只需执行脚本，等待子skills自动触发即可

### 步骤3：执行打标阶段

AI触发**geo-exam-tag** skill：

**执行方式**：
```
AI读取geo-exam-tag/SKILL.md
AI按照geo-exam-tag的流程执行：
  1. 调用tag_docx.py脚本（正则匹配打标）
  2. 等待geo-exam-ai-tagging自动触发（AI语义理解）
  3. 等待geo-exam-merge-validation自动触发（融合验证）
```

**AI职责**：
- 使用RunCommand工具执行tag_docx.py脚本
- 检查脚本输出（tagged_script.json）
- 等待AI skills自动触发并生成tagged_final.json

**关键点**：
- geo-exam-ai-tagging会在"插入图片后.docx"生成后**自动触发**
- geo-exam-merge-validation会在tagged_script.json和tagged_ai.json都生成后**自动触发**
- 双轨并行：脚本轨道+AI轨道，自动融合

### 步骤4：执行排版阶段

AI触发**geo-exam-format** skill：

**执行方式**：
```
AI读取geo-exam-format/SKILL.md
AI按照geo-exam-format的流程执行：
  1. 调用format_docx.py脚本（应用模板排版）
```

**AI职责**：
- 使用RunCommand工具执行format_docx.py脚本
- 检查脚本输出（排版结果.docx）
- 确认质检报告生成（quality_report.html）

**关键点**：
- 排版阶段是纯脚本执行，无AI skills
- 输入文件：tagged_final.json
- 输出文件：排版结果.docx

### 步骤5：输出结果并汇报

AI汇总结果并向用户汇报：

**汇报内容**：
- 排版完成状态
- 输出文件路径（使用computer://链接）
- 处理耗时统计
- 图片数量统计
- 质检报告摘要

**输出格式示例**：
```
排版完成！
- 排版结果：[排版结果.docx](computer://路径)
- 清洗后文档：[清洗.docx](computer://路径)
- 打标数据：[打标.json](computer://路径)
- 质检报告：[质检.html](computer://路径)
- 处理耗时：XX秒
- 提取图片：XX张
```

---

## 批量处理指引

当用户提供多个文件或目录时，AI应执行批量处理：

### 执行方式

**逐个处理**（推荐）：
```
AI对每个文件按顺序执行：
  文件1 → 清洗 → 打标 → 排版 → 完成
  文件2 → 清洗 → 打标 → 排版 → 完成
  ...
```

**并行处理**（可选，如果用户明确要求）：
```
AI同时启动多个处理流程：
  文件1、文件2、文件3同时开始
  每个文件独立执行清洗→打标→排版
```

### 批量输出

AI应生成批量汇总报告：
- 成功处理数量
- 失败处理数量（如有）
- 各文件处理耗时
- 总耗时统计

---

## 子skills关系

本skill编排三个阶段子skill：

| 子skill | 触发时机 | 内部AI skills |
|---------|----------|---------------|
| geo-exam-clean | 阶段1开始时 | geo-exam-image-analysis、geo-exam-image-insertion |
| geo-exam-tag | 阶段2开始时（清洗完成后） | geo-exam-ai-tagging、geo-exam-merge-validation |
| geo-exam-format | 阶段3开始时（打标完成后） | 无（纯脚本） |

**关键机制**：
- 子skills内部的AI skills通过description字段定义的触发条件**自动触发**
- AI无需手动触发子skills内部的AI skills，只需等待它们自动执行

---

## 输出目录结构

AI应将输出保存到用户桌面或用户指定目录：

```
~/Desktop/试卷排版结果/
├── <试卷名称>/
│   ├── <试卷名称>_排版.docx          ← 最终结果
│   ├── <试卷名称>_清洗.docx          ← 中间产物
│   ├── <试卷名称>_打标.json          ← 中间产物（tagged_final.json）
│   ├── images/                       ← 提取的图片
│   ├── clean_log.txt                 ← 清洗日志
│   ├── tag_log.txt                   ← 打标日志
│   ├── format_log.txt                ← 排版日志
│   ├── images_analysis.json          ← 图片分析结果
│   ├── image_insertion_log.json      ← 图片插入日志
│   ├── tagged_script.json            ← 脚本打标结果
│   ├── tagged_ai.json                ← AI打标结果
│   ├── validation_report.json        ← 验证报告
│   └── quality_report.html           ← 质检报告
└── 排版汇总报告.txt                   ← 批量汇总
```

---

## 脚本调用方式

AI在执行各阶段时，使用RunCommand工具调用Python脚本：

### 清洗阶段脚本调用

```powershell
# 清洗脚本
python geo-exam-clean/scripts/clean_docx.py --input "原始试卷.docx" --output "cleaned.docx"

# 图片提取脚本
python geo-exam-clean/scripts/extract_images.py --input "cleaned.docx" --output "初步清理.docx"
```

### 打标阶段脚本调用

```powershell
# 打标脚本
python geo-exam-tag/scripts/tag_docx.py --input "插入图片后.docx" --output "tagged_script.json"
```

### 排版阶段脚本调用

```powershell
# 排版脚本
python geo-exam-format/scripts/format_docx.py --json "tagged_final.json" --template "geo-exam-format/assets/template.dotx" --output "排版结果.docx"
```

---

## AI决策点

在各阶段执行过程中，AI需要做出关键决策：

### 决策1：是否跳过清洗

**判断条件**：
- 如果用户明确说明"文件已清洗"
- 或用户输入文件名包含"cleaned"、"清洗后"等关键词

**决策**：跳过clean_docx.py，直接执行extract_images.py

### 决策2：处理失败时的应对

**判断条件**：
- 脚本执行返回非零退出码
- 输出文件未生成
- AI skill输出验证失败

**决策**：
- 记录失败原因
- 尝试重试一次（如果失败原因可修复）
- 向用户汇报失败并提供错误详情

### 册策3：置信度处理

**判断条件**：
- geo-exam-merge-validation输出的final_confidence为"low"或"failed"

**决策**：
- 向用户提示"打标置信度较低，建议人工检查"
- 在质检报告中标记警告

---

## 注意事项

### 1. 不要替代AI skills

AI在执行本skill时，**不要尝试替代子skills内部的AI skills**：
- 不要自己分析图片内容（应由geo-exam-image-analysis完成）
- 不要自己判断图片位置（应由geo-exam-image-insertion完成）
- 不要自己语义理解试卷结构（应由geo-exam-ai-tagging完成）
- 不要自己融合验证（应由geo-exam-merge-validation完成）

AI只需**触发并等待**这些子skills自动执行。

### 2. 检查中间文件

AI应在每个阶段完成后检查中间文件：
- 清洗阶段：确认cleaned.docx、初步清理.docx、images/、images_analysis.json已生成
- 打标阶段：确认tagged_script.json、tagged_ai.json、tagged_final.json已生成
- 排版阶段：确认排版结果.docx已生成

如果中间文件缺失，AI应停止并汇报错误。

### 3. 保持流程顺序

AI应严格按清洗→打标→排版顺序执行，**不可跳过或颠倒顺序**：
- 清洗必须先执行（生成cleaned.docx和图片信息）
- 打标依赖清洗结果（需要"插入图片后.docx"）
- 排版依赖打标结果（需要tagged_final.json）

---

## 使用示例

### 示例1：处理单个文件

**用户输入**：
"请排版这份试卷：2025年海南高考地理真题.docx"

**AI执行流程**：
1. 读取本SKILL.md，获取流程指引
2. 触发geo-exam-clean，执行清洗脚本和AI skills
3. 等待清洗完成，检查中间文件
4. 触发geo-exam-tag，执行打标脚本和AI skills
5. 等待打标完成，检查tagged_final.json
6. 触发geo-exam-format，执行排版脚本
7. 汇报结果，提供输出文件链接

### 示例2：批量处理

**用户输入**：
"请批量排版参考目录下的所有试卷"

**AI执行流程**：
1. 使用Glob工具收集参考/*.docx文件
2. 对每个文件按顺序执行完整流程
3. 生成批量汇总报告
4. 汇报批量结果

---

## 总结

本skill是地理试卷排版的**AI主导编排器**。AI通过读取并执行各个子skills完成完整流水线，各子skill内部的AI skills通过description定义的触发条件自动执行。

**核心要点**：
- AI主导编排，通过读取并执行子skills完成流水线
- 子skills自动触发，无需手动调用
- AI在各阶段间协调和检查
- AI向用户汇报结果并提供文件链接