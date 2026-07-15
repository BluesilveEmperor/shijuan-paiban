# 地理试卷排版 v3.5 — 双轨流水线说明

> **设计原则**：代码处理确定性逻辑，AI 仅介入不确定性场景。

---

## 输出目录结构

```
output/
├── {试卷名称}/
│   ├── 清洗产物/                      # Step1 输出：清洗后的文本和图片
│   │   ├── content.md                # 清洗后纯文字正文（含 {{image:img_xxx}} 标记）
│   │   ├── cleaned_no_images.docx    # 去图片后的纯文本 docx
│   │   ├── images/                   # 提取的图片文件
│   │   │   ├── img_001.png
│   │   │   └── img_002.jpeg
│   │   ├── image_manifest.json       # 图片提取清单（含 original_type 字段）
│   │   ├── _original_image_types.json # 临时：原始图片类型记录
│   │   ├── clean_log.txt            # 清洗过程日志
│   │   └── symbols_report.md        # 未解析符号图片报告（如有）
│   ├── 中间数据/                      # Step2-4 输出：中间处理数据
│   │   ├── structure.json           # Step2：试卷结构 JSON
│   │   ├── with_placeholders.json   # Step3：仅 anchor 图的占位符
│   │   └── anchor_descriptions.json # Step4：仅 anchor 图的内容理解
│   ├── 试卷数据/                      # Step5 输出：完整试卷数据
│   │   └── final_exam.json          # 最终试卷 JSON（含双轨映射+track 字段）
│   ├── 排版文档/                      # Step6 辅助输出：质检报告和日志
│   │   ├── quality_report.html      # 排版质检报告 (HTML)
│   │   └── typeset_log.txt          # 排版运行日志
│   └── {试卷名称}-排版后.docx         # Step6 输出：最终排版完成的 Word 文档
```

---

## 流水线总览

```
原始试卷.docx
    │
    ▼
[Step1] clean_exam ──────────► 清洗产物/content.md + images/ + image_manifest.json
    │                              （新增 original_type 字段）
    ▼
[Step2] tag_structure ───────► 中间数据/structure.json
    │
    │   ┌── inline 图片 → 代码路径 → 零 AI 调用
    │   │   content.md 中的 {{image:img_xxx}} 即占位符
    │   │
    │   └── anchor 图片 → AI 路径
    │       [Step4] tag_images_anchor ──► 中间数据/anchor_descriptions.json
    │       [Step3] tag_placeholders_anchor ──► 中间数据/with_placeholders.json
    │
    ▼
[Step5] map_images ──────────► 试卷数据/final_exam.json
    │                              （Track: code + Track: ai）
    ▼
[Step6] typeset_exam ────────► {试卷名称}-排版后.docx（排版文档/ 含质检报告和日志）
```

---

## 双轨分流逻辑

### 图片分类

```python
所有图片
  ├─ original_type == "inline"  → 代码确定路径
  │    paragraph_index 可靠（排版者有意为之）
  │    按段落顺序映射到占位符
  │    置信度 ≥ 0.95
  │
  ├─ original_type == "anchor"  → AI 不确定路径
  │    paragraph_index 可能不可靠
  │    AI 分析图片内容 + 文档上下文 → 判断位置
  │    置信度取决于 AI 匹配质量
  │
  ├─ original_type == "vml"     → 归入 anchor 路径
  └─ file_size < 2KB            → 符号小图，不做内容映射
```

### 一段多图

一段材料可以有多个 inline 图或多个 anchor 图，不做硬限制。AI 根据语义判断每张图的位置。

---

## 各步骤详述

### Step 1: clean_exam（清洗）

| 维度 | 说明 |
|------|------|
| **输入** | 原始试卷 `.docx` 文件 |
| **输出** | `清洗产物/content.md` + `清洗产物/images/` + `清洗产物/image_manifest.json`（含 `original_type`） |
| **脚本** | `scripts/clean_docx.py` + `scripts/extract_images.py` |
| **新增** | `record_original_image_types()` 在 rule_1_19 前记录原始图片类型 |

**关键变更**：
- clean_docx.py 在网页二"图片处理"中，rule_1_19 执行前，先调用 `record_original_image_types()` 扫描文档，记录每张图片的 `original_type`
- 输出 `_original_image_types.json` 临时文件
- extract_images.py 读取该临时文件，将 `original_type` 写入 `image_manifest.json`

### Step 2: tag_structure（结构打标）

| 维度 | 说明 |
|------|------|
| **输入** | `清洗产物/content.md` + `templates/exam_reference.json` + `schemas/exam_paper.schema.json` |
| **输出** | `中间数据/structure.json` |
| **职责** | 识别试卷标题、大题/题组、题号、题干、选项、材料、小问 |

**与 v3.0 对比**：完全一致，无变更。

### Step 3: tag_placeholders_anchor（anchor 图占位）

| 维度 | 说明 |
|------|------|
| **输入** | `中间数据/structure.json` + `中间数据/anchor_descriptions.json`（Step4 产物） + `清洗产物/content.md` + `清洗产物/image_manifest.json` |
| **输出** | `中间数据/with_placeholders.json`（仅含 anchor 图占位符） |
| **职责** | 结合图片分析结果，仅对 anchor 浮动图判断应插入位置 |

**与 v3.0 对比**：
- v3.0：AI 为**全部**图片创建占位符
- v3.5：AI 仅为 **anchor 浮动图**创建占位符（inline 图由代码处理）
- 新增 `_source: "anchor"` 字段标记占位符来源
- 允许一道题有多个占位符（多张图）

**依赖**：必须等待 Step4 `tag_images_anchor` 完成（需要图片分析结果）

### Step 4: tag_images_anchor（anchor 图理解）

| 维度 | 说明 |
|------|------|
| **输入** | `清洗产物/images/`（仅处理 image_manifest.json 中 `original_type == "anchor"` 的图片） |
| **输出** | `中间数据/anchor_descriptions.json` |
| **职责** | 仅分析 anchor 浮动图的内容（类型、关键词、OCR、位置提示） |

**与 v3.0 对比**：
- v3.0：分析**全部**图片
- v3.5：仅分析 `original_type == "anchor"` 的图片
- 新增 `anchor_paragraph_index`、`anchor_context`、`position_hint` 字段
- `position_hint` 是 AI 对图片应放位置的初步判断，供 Step3 参考

### Step 5: map_images（双轨映射）

| 维度 | 说明 |
|------|------|
| **输入** | `中间数据/structure.json` + `中间数据/with_placeholders.json` + `清洗产物/image_manifest.json` + `中间数据/anchor_descriptions.json` + `清洗产物/content.md` |
| **输出** | `试卷数据/final_exam.json` |
| **职责** | **双轨映射**：代码锁定 inline 图 + 采纳 AI 的 anchor 图结果 |

**Track 1（代码，inline 图）**：
1. 筛选 `original_type == "inline"` 且 `file_size >= 2KB` 的图片
2. 按 `paragraph_index` 排序
3. 与 inline 占位符按题目顺序一一映射
4. 置信度固定 0.95，`track: "code"`

**Track 2（AI，anchor 图）**：
1. 筛选 `original_type == "anchor"` 且 `file_size >= 2KB` 的图片
2. 读取 AI Step3 创建的 anchor 占位符
3. 按题目顺序排序，与 anchor 图一一映射
4. 使用 `anchor_descriptions.json` 中的信息做关键词验证
5. 置信度基于 AI 分析结果，`track: "ai"`

### Step 6: typeset_exam（排版）

| 维度 | 说明 |
|------|------|
| **输入** | `试卷数据/final_exam.json` + `assets/template.dotx` + `清洗产物/images/` |
| **输出** | `{试卷名称}-排版后.docx` + `排版文档/quality_report.html` + `排版文档/typeset_log.txt` |
| **脚本** | `scripts/typeset_exam.py` |

**与 v3.0 对比**：完全一致，无变更。排版脚本同时兼容 v3.0 和 v3.5 的 `final_exam.json`。

---

## 数据契约

所有步骤间的数据传递均使用 `schemas/exam_paper.schema.json` 定义的统一数据格式。

### v3.5 新增/变更字段

| 字段 | 所属 | 类型 | 说明 |
|------|------|------|------|
| `original_type` | `image_manifest.json` → `images[].original_type` | `"inline"` \| `"anchor"` \| `"vml"` \| `"unknown"` | 图片在源文档中的原始类型 |
| `track` | `final_exam.json` → `image_mapping[].track` | `"code"` \| `"ai"` | 映射来源标识 |
| `_source` | `with_placeholders.json` → `placeholders[]._source` | `"anchor"` | 占位符来源（内部字段，不影响排版） |
| `anchor_paragraph_index` | `anchor_descriptions.json` → `images[].anchor_paragraph_index` | `int` | anchor 图的原始锚点段落索引 |
| `anchor_context` | `anchor_descriptions.json` → `images[].anchor_context` | `string` | anchor 图的锚点段落上下文 |
| `position_hint` | `anchor_descriptions.json` → `images[].position_hint` | `string` | AI 对图片应放置位置的分析 |

---

## 校验工具

所有产物均可通过 `validate_json.py` 进行格式校验：

```bash
python scripts/validate_json.py \
    --schema schemas/exam_paper.schema.json \
    --json output/{试卷名称}/中间数据/structure.json
```

---

## v3.0 → v3.5 关键差异

| 维度 | v3.0 | v3.5 |
|------|------|------|
| 架构策略 | 纯 AI 驱动 | 代码 + AI 双轨 |
| inline 图处理 | AI 占位 + AI 映射 | **代码直接定位**（零 AI） |
| anchor 图处理 | AI 占位 + AI 映射 | AI 占位（含图片分析辅助） |
| AI 调用量 | 全部图片 | 仅 anchor 图（减少 60-80%） |
| 图片占位符来源 | 全部 AI 创建 | inline=代码，anchor=AI |
| Step4 产物 | `image_descriptions.json`（全部图片） | `anchor_descriptions.json`（仅 anchor 图） |
| 映射置信度 | AI 评估，波动大 | inline 固定 0.95，anchor 基于 AI 分析 |
| 低能模型容错 | 全部环节受影响 | inline 图不受影响 |
| `original_type` 字段 | 无 | 有，用于双轨分流 |
| `track` 字段 | 无 | 有，标记映射来源 |
