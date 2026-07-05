---
name: geo-exam-clean
description: "地理试卷清洗skill（AI主导架构）。AI执行清洗脚本（clean_docx.py）和图片提取脚本（extract_images.py），然后AI skills（geo-exam-image-analysis和geo-exam-image-insertion）自动触发完成图片分析和占位符插入。当用户提到清洗试卷、清理格式、清理水印等场景时使用本skill。"
---

# 地理试卷清洗 Skill（AI主导架构）

## 概述

本skill是地理试卷排版的**清洗阶段**，采用AI主导架构。AI执行清洗脚本，然后内部AI skills自动触发完成图片处理。

**AI主导流程**：
```
AI触发geo-exam-clean
  ↓
AI执行clean_docx.py脚本（删除无关内容）
  ↓
AI执行extract_images.py脚本（提取所有图片）
  ↓
geo-exam-image-analysis自动触发（AI分析图片内容）
  ↓
geo-exam-image-insertion自动触发（AI插入图片占位符）
  ↓
输出：插入图片后.docx + images_analysis.json + image_insertion_log.json
```

---

## 触发时机

**自动触发条件**：
- geo-exam-formatting主skill执行阶段1时触发
- 用户明确要求"清洗试卷"、"清理格式"
- 用户提到"删除水印"、"清理品牌信息"

**触发检查**：
AI应先检查：
- 输入文件是否为.docx格式
- 文件路径是否正确
- 如不满足，提示用户提供正确的输入文件

---

## AI执行流程

### 步骤1：执行清洗脚本

AI使用RunCommand工具执行clean_docx.py：

```powershell
python scripts/clean_docx.py --input "原始试卷.docx" --output "cleaned.docx"
```

**脚本功能**：
- 删除品牌水印（学科网、组卷网等）
- 删除域代码、超链接、书签
- 统一标点符号（全角→半角）
- 删除空段落、多余空行
- 清理表格样式
- **保留所有图片**（嵌入式+浮动式）

**AI职责**：
- 执行脚本
- 检查cleaned.docx是否生成
- 检查clean_log.txt日志内容

### 步骤2：执行图片提取脚本

AI使用RunCommand工具执行extract_images.py：

```powershell
python scripts/extract_images.py --input "cleaned.docx" --output "初步清理.docx"
```

**脚本功能**：
- 提取所有图片（嵌入式wp:inline + 浮动式wp:anchor）
- 保存图片到images文件夹（img_001.png、img_002.png等）
- 删除文档中所有图片元素
- 输出image_manifest.json（记录图片原始位置信息）

**输出文件**：
- `初步清理.docx`：不含图片，只有文字
- `images/`：所有提取的图片文件
- `image_manifest.json`：图片位置信息清单

**AI职责**：
- 执行脚本
- 检查images文件夹是否生成
- 检查image_manifest.json是否存在
- 统计提取图片数量

### 步骤3：等待AI skills自动触发

AI skills会在extract_images.py完成后**自动触发**：

#### geo-exam-image-analysis自动触发

**触发条件**：extract_images.py执行完毕，images文件夹已生成

**AI职责**：等待该skill自动执行，无需手动触发

**该skill会**：
- 读取images文件夹中的所有图片
- AI多模态分析图片内容（地图、图表、示意图等）
- 输出images_analysis.json

#### geo-exam-image-insertion自动触发

**触发条件**：geo-exam-image-analysis执行完毕，images_analysis.json已生成

**AI职责**：等待该skill自动执行，无需手动触发

**该skill会**：
- 读取初步清理.docx和images_analysis.json
- AI判断哪些位置需要图片但未放置
- 插入图片占位符【图片：<filename> - <description>】
- 输出插入图片后.docx和image_insertion_log.json

### 步骤4：检查最终输出

AI应检查清洗阶段最终输出：

| 文件 | 说明 | 必须生成 |
|------|------|----------|
| `插入图片后.docx` | 包含图片占位符的文档 | ✅ 必须有 |
| `images/` | 提取的图片文件夹 | ✅ 必须有 |
| `images_analysis.json` | 图片内容分析结果 | ✅ 必须有 |
| `image_insertion_log.json` | 图片插入日志 | ✅ 必须有 |
| `cleaned.docx` | 清洗后文档（中间产物） | 可选 |
| `image_manifest.json` | 图片位置清单（中间产物） | 可选 |

**如果文件缺失**：
- 检查脚本执行日志
- 检查AI skills触发日志
- 向用户汇报缺失文件和原因

---

## 输出目录结构

清洗阶段输出应保存到用户指定目录：

```
<输出目录>/
├── cleaned.docx                 ← 清洗后文档（中间产物）
├── 初步清理.docx                ← 不含图片的文档（中间产物）
├── 插入图片后.docx              ← 最终清洗结果（含占位符）
├── images/                      ← 提取的图片文件夹
│   ├── img_001.png
│   ├── img_002.png
│   └── ...
├── image_manifest.json          ← 图片位置清单
├── images_analysis.json         ← 图片内容分析结果
├── image_insertion_log.json     ← 图片插入日志
└── clean_log.txt                ← 清洗过程日志
```

---

## 内部AI skills说明

本skill包含2个内部AI skills：

| AI skill | 触发时机 | 功能 |
|----------|----------|------|
| geo-exam-image-analysis | extract_images.py完成后 | AI多模态分析图片内容 |
| geo-exam-image-insertion | geo-exam-image-analysis完成后 | AI判断并插入图片占位符 |

**关键机制**：
- 这些AI skills通过description字段定义的触发条件**自动触发**
- AI无需手动触发，只需等待它们执行
- AI skills执行完成后，会生成对应的JSON文件

---

## 脚本调用参数说明

### clean_docx.py参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input` | 输入文件路径 | 必填 |
| `--output` | 输出文件路径 | 必填 |
| `--log` | 日志文件路径 | `<输出目录>/clean_log.txt` |

### extract_images.py参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input` | 输入文件路径（cleaned.docx） | 必填 |
| `--output` | 输出文件路径（初步清理.docx） | 必填 |
| `--images-dir` | 图片输出目录 | `<输出目录>/images` |
| `--manifest` | 图片清单路径 | `<输出目录>/image_manifest.json` |

---

## 脚本使用约束（强制）

**AI必须严格遵守以下约束**：

1. **禁止自行编写脚本**：AI不得自己书写任何Python脚本或其他代码脚本，也不得用Write工具创建新的脚本文件。
2. **只能使用项目已有脚本**：AI只能通过RunCommand工具调用本skill目录下已有的脚本：
   - `scripts/clean_docx.py`（清洗脚本）
   - `scripts/extract_images.py`（图片提取脚本）
3. **功能不足时的处理**：如遇脚本功能不足，应向用户说明情况，**绝不自行编写替代脚本**。

---

## 注意事项

### 1. 不要替代AI skills

AI在执行本skill时，**不要尝试替代内部AI skills**：
- 不要自己分析图片内容（应由geo-exam-image-analysis完成）
- 不要自己判断图片位置（应由geo-exam-image-insertion完成）

AI只需**执行脚本并等待**内部AI skills自动触发。

### 2. 检查脚本输出

AI应在每个脚本执行后检查输出：
- clean_docx.py执行后检查cleaned.docx
- extract_images.py执行后检查images文件夹和image_manifest.json
- 确认图片数量与提取脚本日志一致

### 3. 图片占位符格式

图片占位符由geo-exam-image-insertion自动生成，格式为：
```
【图片：<filename> - <description>】
```

AI不应手动修改占位符格式。

### 4. 数据契约（图片流转关键约束）

**图片在流水线中的流转路径**：

```
原始试卷.docx
  → clean_docx.py → cleaned.docx（保留图片）
  → extract_images.py → 初步清理.docx（删除图片）+ images/文件夹
  → 插入图片占位符 → 插入图片后.docx（含【图片：xxx】文本占位符）
  → tag_docx.py → tagged_script.json
  → format_docx.py → 排版结果.docx（重新插入真实图片）
```

**关键约束**：
- `extract_images.py` 会删除文档中的所有图片元素，因此 `tag_docx.py` 无法通过XML检测到图片
- `tag_docx.py` 必须能识别 `【图片：xxx】` 文本占位符，并将其转换为 `{"type": "image", "name": "xxx"}` segment
- `format_docx.py` 必须同时支持：
  - `{"type": "image", "name": "xxx"}` segment → 直接插入图片
  - `{"type": "text", "content": "【图片：xxx - 描述】"}` segment → 识别占位符并插入图片（向后兼容）
  - `{"images": ["xxx"]}` 旧格式字段 → 直接插入图片
- 这三层防御确保无论打标轨道输出哪种格式，图片都能正确插入最终文档

---

## 总结

本skill是清洗阶段的AI主导执行器。AI执行脚本后，内部AI skills自动触发完成图片分析和占位符插入。

**核心要点**：
- AI执行项目已有脚本，通过RunCommand工具调用
- 内部AI skills自动触发，无需手动调用
- AI检查输出文件完整性
- 输出"插入图片后.docx"供打标阶段使用