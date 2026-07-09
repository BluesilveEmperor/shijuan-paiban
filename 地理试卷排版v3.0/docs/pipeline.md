# 地理试卷排版 v3.0 - 六步解耦流水线说明

> **设计原则**：每一步只做一件事，有固定输入输出，结果落盘可校验。

---

## 输出目录结构

```
output/
├── README.md                         # 输出文件说明文档
├── {试卷名称}/                        # 每份试卷的独立工作目录
│   ├── 清洗产物/                      # Step1 输出：清洗后的文本和图片
│   │   ├── content.md                # 清洗后纯文字正文（含上下标标记）
│   │   ├── cleaned_no_images.docx    # 去图片后的纯文本 docx
│   │   ├── images/                   # 提取的图片文件
│   │   │   ├── img_001.png
│   │   │   └── img_002.jpeg
│   │   ├── image_manifest.json       # 图片提取清单（位置、来源）
│   │   ├── clean_log.txt            # 清洗过程日志
│   │   └── symbols_report.md        # 未解析符号图片报告（如有）
│   ├── 中间数据/                      # Step2-4 输出：中间处理数据
│   │   ├── structure.json           # Step2：试卷结构 JSON
│   │   ├── with_placeholders.json   # Step3：含图片占位符的试卷 JSON
│   │   └── image_descriptions.json  # Step4：图片内容理解描述
│   ├── 试卷数据/                      # Step5 输出：完整试卷数据
│   │   └── final_exam.json          # 最终试卷 JSON（含图片映射+校验信息）
│   └── 排版文档/                      # Step6 输出：最终排版文档
│       ├── final_exam.docx          # 排版完成的 Word 文档
│       ├── quality_report.html      # 排版质检报告 (HTML)
│       └── typeset_log.txt          # 排版运行日志
```

---

## 流水线总览

```
原始试卷.docx
    │
    ▼
[Step1] clean_exam ──────────► {工作目录}/清洗产物/content.md + images/
    │
    ▼
[Step2] tag_structure ───────► {工作目录}/中间数据/structure.json
    │
    ▼
[Step3] tag_placeholders ────► {工作目录}/中间数据/with_placeholders.json
    │
    ▼
[Step4] tag_images ──────────► {工作目录}/中间数据/image_descriptions.json
    │                              (并行于 Step2/3，仅依赖 清洗产物/images/)
    ▼
[Step5] map_images ──────────► {工作目录}/试卷数据/final_exam.json
    │
    ▼
[Step6] typeset_exam ────────► {工作目录}/排版文档/final_exam.docx
```

`{工作目录}` = `output/{试卷名称}/`

---

## 各步骤详述

### Step 1: clean_exam（清洗）

| 维度 | 说明 |
|------|------|
| **输入** | 原始试卷 `.docx` 文件 |
| **输出** | `{工作目录}/清洗产物/content.md` + `{工作目录}/清洗产物/images/` |
| **职责** | 调用清洗脚本，提取正文和图片资源，不分析题目结构 |
| **脚本** | `scripts/clean_docx.py` + `scripts/extract_images.py` |
| **校验** | `content.md` 存在且非空；`images/` 目录存在 |

### Step 2: tag_structure（结构打标）

| 维度 | 说明 |
|------|------|
| **输入** | `{工作目录}/清洗产物/content.md` + `templates/exam_reference.json` + `schemas/exam_paper.schema.json` |
| **输出** | `{工作目录}/中间数据/structure.json` |
| **职责** | 识别试卷标题、大题/题组、题号、题干、选项、材料、小问，不处理图片 |
| **校验** | `python scripts/validate_json.py -s schemas/exam_paper.schema.json -j {工作目录}/中间数据/structure.json` |

### Step 3: tag_placeholders（图片占位）

| 维度 | 说明 |
|------|------|
| **输入** | `{工作目录}/中间数据/structure.json` |
| **输出** | `{工作目录}/中间数据/with_placeholders.json` |
| **职责** | 在结构中标出需要图片的位置（`{{image:ph_xxx}}`），不读取图片文件 |
| **校验** | Schema 校验 + 占位符 ID 唯一性 + 每个占位符有 `owner_id` 和 `reason` |

### Step 4: tag_images（图片理解）

| 维度 | 说明 |
|------|------|
| **输入** | `{工作目录}/清洗产物/images/` |
| **输出** | `{工作目录}/中间数据/image_descriptions.json` |
| **职责** | 逐张理解图片（类型、主题、关键词、OCR文字），不决定图片位置 |
| **校验** | Schema 校验 + 每图有 `summary` 和 `keywords` |
| **并行** | 与 Step2/3 无依赖，可并行执行 |

### Step 5: map_images（图片映射）

| 维度 | 说明 |
|------|------|
| **输入** | `{工作目录}/中间数据/with_placeholders.json` + `{工作目录}/中间数据/image_descriptions.json` |
| **输出** | `{工作目录}/试卷数据/final_exam.json` |
| **职责** | 完成占位符与图片的匹配，填写 `image_mapping` 和 `validation` 字段 |
| **校验** | Schema 校验 + 映射 ID 引用有效性 + 映射置信度检查 |

### Step 6: typeset_exam（排版）

| 维度 | 说明 |
|------|------|
| **输入** | `{工作目录}/试卷数据/final_exam.json` + `assets/template.dotx` + `{工作目录}/清洗产物/images/` |
| **输出** | `{工作目录}/排版文档/final_exam.docx` |
| **职责** | 调用排版脚本生成最终文档，不修改 JSON 语义 |
| **脚本** | `scripts/typeset_exam.py` |

---

## 数据契约

所有步骤间的数据传递均使用 `schemas/exam_paper.schema.json` 定义的统一数据格式。

### 核心结构

```
{
  meta:                   试卷元信息
  document: {
    sections: [{         分区列表（选择题区/非选择题区）
      questions: [{       题目列表
        materials: [],    材料
        subquestions: [], 子问题
        options: [],      选项
        placeholders: []  占位符
      }]
    }],
    unclassified_blocks: []  兜底：无法归类的文本
  },
  images: [],              图片理解结果
  image_mapping: [],       占位符→图片映射
  validation: {}           校验信息（warnings/unmapped/unused）
}
```

### 占位符规范

- **统一格式**：`{{image:ph_xxx}}`（如 `{{image:ph_001}}`）
- **属性**：`placeholder_id` / `token` / `location_type` / `owner_id` / `context_before` / `context_after` / `reason`
- **location_type 枚举**：`title` / `material` / `question_stem` / `subquestion` / `option`

### 兜底字段

| 字段 | 用途 |
|------|------|
| `question.uncertain` | 题目结构识别不确定 |
| `placeholder.uncertain` | 占位插入不确定 |
| `image.uncertain` | 图片理解不确定 |
| `unclassified_blocks` | 无法归类的文本块 |
| `validation.unmapped_placeholders` | 未匹配的占位符 |
| `validation.unused_images` | 未使用的图片 |
| `validation.warnings` | 警告信息 |

---

## 校验工具

所有产物均可通过 `validate_json.py` 进行格式校验：

```bash
# 对任意步骤产物进行校验
python scripts/validate_json.py \
    --schema schemas/exam_paper.schema.json \
    --json output/{试卷名称}/中间数据/structure.json \
    [--log output/{试卷名称}/排版文档/validate.log]
```

退出码：
- `0` - 校验通过
- `1` - 校验失败（含错误明细）
- `2` - 运行异常

---

## v2.0 → v3.0 关键差异

| v2.0 | v3.0 |
|------|------|
| 3阶段聚合 | 6步骤解耦 |
| description 隐式触发 | 主 Skill 显式编排 |
| 双轨（脚本+AI）融合 | 单轨 AI + Schema 校验 |
| `【图片：xxx】` / `{{IMAGE:xxx}}` 混用 | 统一 `{{image:ph_xxx}}` |
| 图片耦合在清洗阶段 | 图片独立 Step4 + Step5 |
| 缺系统兜底字段 | uncertain / unclassified_blocks / warnings |
| 上下文 + 文件传递 | 纯文件落盘传递 |
| `runtime/` 单目录 | `output/{试卷名称}/` 隔离多试卷 |
