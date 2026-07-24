---
name: "master-exam-layout"
description: "编排6步试卷排版流水线(v3.6)：Step3增量编辑、Step5脚本优先。需对完整流水线排版时触发。"
---

## Role

你是"试卷排版流水线主编排"。你只负责按固定顺序调度 Step1→Step6 六个子 Skill，每步检查产物存在性与 Schema 校验结果，不分析试卷内容、不理解题目语义、不参与图片映射决策。

**v3.5 核心变更**：inline 图片的占位符由代码在 Step1 自动生成（`{{image:img_xxx}}`），你无需为它们创建占位符。AI 仅需介入 anchor 浮动图片。

---

## Input

- **一份原始试卷 `.docx` 文件**（用户提供路径）
- **项目内置资源**：
  - `clean-exam` — Step1 清洗 Skill
  - `tag-structure` — Step2 结构打标 Skill
  - `tag-placeholders-anchor` — Step3 anchor 图占位 Skill（替代原 tag_placeholders）
  - `tag-images-anchor` — Step4 anchor 图理解 Skill（替代原 tag_images）
  - `map-images` — Step5 双轨映射 Skill
  - `typeset-exam` — Step6 排版 Skill
  - `schemas/exam_paper.schema.json` — 统一数据契约
  - `scripts/validate_json.py` — Schema 校验工具
  - `scripts/clean_docx.py` / `scripts/extract_images.py` — 清洗脚本
  - `scripts/typeset_exam.py` — 排版脚本
  - `scripts/map_images.py` — 双轨映射脚本
  - `scripts/utils.py` — 公共工具函数
  - `templates/exam_reference.json` — 结构参考模板
  - `assets/template.dotx` — 样式模板

---

## Task

严格按照 Step1→Step6 顺序调度，每步执行"调度 → 等待 → 检查产物 → Schema 校验 → 记录状态"，**任一步骤失败则停止并报告**。

### 前置：创建工作目录

提取试卷名称 `os.path.splitext(os.path.basename(input_file))[0]`，工作目录为 `~/Desktop/排版结果/{试卷名称}/`（即桌面根目录下的"排版结果"文件夹内）。

**输出目录规则**：
- 首次运行时，自动在桌面创建"排版结果"文件夹，所有输出按原有内部结构保存
- 后续运行复用已有"排版结果"文件夹，新输出追加或更新
- 若文件夹被删除，自动重新创建
- 使用 `scripts/utils.py` 的 `resolve_output_root()` 解析桌面路径并验证权限

确认存在以下目录，不存在则创建：

```
{工作目录}/
  清洗产物/
  中间数据/
  试卷数据/
  排版文档/
```

---

### Step1: clean-exam（清洗）

| 项目 | 内容 |
|------|------|
| **Skill** | `clean-exam` |
| **任务** | 调用清洗脚本，提取正文和图片，记录 original_type |
| **输入** | 原始 `.docx` 文件 |
| **预期产物** | `清洗产物/content.md`、`清洗产物/images/`、`清洗产物/image_manifest.json`（含 `original_type`） |

**执行指令**：

```
请严格按照 clean-exam 技能执行试卷清洗任务。
输入文件: <原始 docx 路径>
输出目录: {工作目录}/清洗产物/

要求:
1. 先执行 python scripts/clean_docx.py（含 record_original_image_types）
2. 再执行 python scripts/extract_images.py（含 original_type 字段）
3. 调用 docx_to_markdown() 生成 content.md
4. 调用 check_pending_symbols() 检查未解析符号
```

**产物检查**：
- [ ] `清洗产物/cleaned_no_images.docx` 存在
- [ ] `清洗产物/content.md` 存在且非空
- [ ] `清洗产物/images/` 目录存在
- [ ] `清洗产物/image_manifest.json` 存在且包含 `original_type` 字段

**重要**：执行完 Step1 后，立即检查 `image_manifest.json`，统计 inline 和 anchor 图片数量。如果 `anchor_count == 0`，**跳过 Step3 和 Step4**，直接从 Step2 → Step5。

**状态输出**：

```json
{
  "step": "clean-exam",
  "status": "success",
  "statistics": {
    "content_paragraphs": 120,
    "images_extracted": 8,
    "inline_images": 6,
    "anchor_images": 2,
    "small_symbol_images": 0
  },
  "next_action": "执行 Step2: tag-structure（可并行启动 Step4: tag-images-anchor）"
}
```

---

### Step2: tag-structure（结构打标）

| 项目 | 内容 |
|------|------|
| **Skill** | `tag-structure` |
| **任务** | 读取 content.md，识别试卷结构，输出 structure.json |
| **输入** | `清洗产物/content.md` + `templates/exam_reference.json` + `schemas/exam_paper.schema.json` |
| **预期产物** | `中间数据/structure.json` |

**执行指令**：

```
请严格按照 tag-structure 技能执行结构打标任务。
输入: {工作目录}/清洗产物/content.md
参考模板: templates/exam_reference.json
Schema: schemas/exam_paper.schema.json
输出: {工作目录}/中间数据/structure.json

注意：inline 图的 {{image:img_xxx}} 标记已在 content.md 中，请保留它们作为结构中的占位符。
```

**产物检查**：
- [ ] `中间数据/structure.json` 存在且非空

**合规检查**：
```powershell
python scripts/check_compliance.py --work-dir {工作目录} --step step2 --json 中间数据/structure.json
```

---

### Step4: tag-images-anchor（anchor 图理解）— 与 Step2 并行

| 项目 | 内容 |
|------|------|
| **Skill** | `tag-images-anchor` |
| **任务** | 仅分析 original_type == "anchor" 的图片内容 |
| **输入** | `清洗产物/images/`（仅 anchor 图）+ `清洗产物/image_manifest.json` |
| **预期产物** | `中间数据/anchor_descriptions.json` |

**前置检查**：如果 Step1 统计 `anchor_count == 0`，**跳过此步骤**。

**执行指令**：

```
请严格按照 tag-images-anchor 技能执行 anchor 图理解任务。
输入: {工作目录}/清洗产物/images/
图片清单: {工作目录}/清洗产物/image_manifest.json（仅 original_type=="anchor" 的图片）
Schema: schemas/exam_paper.schema.json
输出: {工作目录}/中间数据/anchor_descriptions.json
```

**状态输出**：

```json
{
  "step": "tag-images-anchor",
  "status": "success",
  "statistics": {
    "anchor_image_count": 2,
    "analyzed": 2,
    "model_support_images": true
  },
  "next_action": "等待 Step2 完成后执行 Step3"
}
```

---

### Step3: tag-placeholders-anchor（anchor 图占位）— 增量编辑模式

| 项目 | 内容 |
|------|------|
| **Skill** | `tag-placeholders-anchor` |
| **任务** | 结合图片分析结果，仅对 anchor 图判断应插入位置。**使用 Edit 工具增量修改，禁止全量输出** |
| **前置依赖** | Step2 (`structure.json`) + Step4 (`anchor_descriptions.json`) 均已完成 |
| **输入** | `中间数据/structure.json` + `中间数据/anchor_descriptions.json` + `清洗产物/content.md` + `清洗产物/image_manifest.json` |
| **预期产物** | `中间数据/with_placeholders.json`（通过 copy + Edit 生成，仅含 anchor 图占位符） |

**前置检查**：如果 Step1 统计 `anchor_count == 0`，**跳过此步骤**，直接进入 Step5a。

**执行指令（v3.6 增量编辑模式）**：

```
请严格按照 tag-placeholders-anchor 技能执行 anchor 图占位标注任务（增量编辑模式）。
操作流程:
1. 先用 copy 命令复制: copy {工作目录}/中间数据/structure.json {工作目录}/中间数据/with_placeholders.json
2. 使用 Edit 工具逐占位符修改 with_placeholders.json
3. 每次 Edit 后立即运行 validate_json.py 校验
4. 禁止使用 Write 工具全量输出

输入: {工作目录}/中间数据/structure.json, {工作目录}/中间数据/anchor_descriptions.json
上下文: {工作目录}/清洗产物/content.md
图片清单: {工作目录}/清洗产物/image_manifest.json
Schema: schemas/exam_paper.schema.json
输出: {工作目录}/中间数据/with_placeholders.json（增量编辑）

注意：
- 仅为 anchor 浮动图创建占位符，inline 图已由代码处理
- 结合 anchor_descriptions.json 中的 position_hint 辅助判断
- 占位符标记 _source: "anchor"
- 允许一道题有多个占位符
- 每次 Edit 只修改一个占位符
```

**产物检查**：
- [ ] `中间数据/with_placeholders.json` 存在且非空
- [ ] 占位符 `placeholder_id` 无重复
- [ ] 每个占位符有 `_source: "anchor"`、`owner_id`、`reason`
- [ ] 确认 AI 使用了 Edit 工具而非 Write 工具（检查文件修改时间是否合理）

**合规检查**：
```powershell
python scripts/check_compliance.py --work-dir {工作目录} --step step3 --json 中间数据/with_placeholders.json
```

---

### Step5: map-images（脚本优先 + AI 兜底）— v3.6 优化

| 子步骤 | 内容 |
|--------|------|
| **5a** | 运行 `map_images.py` 脚本（代码路径，**零 AI token**） |
| **5b** | 检查产物：若无未映射项 → 完成 |
| **5c** | 仅当存在未映射项时，调用 AI 兜底修正 |

**前置条件**：Step2 和 Step3（如有 anchor 图）均已完成。

---

#### Step5a：脚本优先映射（代码路径）

**执行命令**：

```powershell
python scripts/map_images.py --placeholders {工作目录}/中间数据/with_placeholders.json --image-descriptions {工作目录}/中间数据/anchor_descriptions.json --images-manifest {工作目录}/清洗产物/image_manifest.json --content {工作目录}/清洗产物/content.md --output {工作目录}/试卷数据/final_exam.json
```

**注意**：如果 Step3 被跳过（anchor_count == 0），`--placeholders` 参数改为 `{工作目录}/中间数据/structure.json`，`--image-descriptions` 参数省略。

**产物检查**：
- [ ] 脚本退出码为 0
- [ ] `试卷数据/final_exam.json` 存在且非空

---

#### Step5b：检查脚本产物

读取 `试卷数据/final_exam.json` → `validation` 字段：

```
如果 validation.unmapped_placeholders 为空 && validation.unused_images 为空 && validation.warnings 为空：
    → 映射完全成功，跳过 5c，直接进入 Step6

如果存在未映射项 或 存在低置信度映射（image_mapping 中有 confidence < 0.6 的条目）：
    → 进入 Step5c（AI 兜底）
```

**状态输出**（5a/5b 成功时）：

```json
{
  "step": "map-images",
  "sub_step": "5a",
  "status": "success",
  "method": "script (map_images.py)",
  "statistics": {
    "total_images": 8,
    "inline_mapped": 6,
    "anchor_mapped": 2,
    "unmapped": 0,
    "code_track": 6,
    "ai_track": 2,
    "ai_fallback_used": false
  },
  "next_action": "执行 Step6: typeset-exam"
}
```

---

#### Step5c：AI 兜底修正（仅问题路径）

| 项目 | 内容 |
|------|------|
| **Skill** | `map-images` |
| **任务** | 仅审核脚本未能映射的项，输出覆盖文件 |
| **输入** | `试卷数据/final_exam.json`（仅读取 validation 字段）+ `中间数据/anchor_descriptions.json`（如需参考）+ `清洗产物/content.md`（如需确认上下文） |
| **预期产物** | `中间数据/image_mapping_overrides.json`（**仅覆盖项，~10-30行**） |

**执行指令**：

```
请严格按照 map-images 技能执行 AI 兜底修正任务。
仅处理以下问题项：
- validation.unmapped_placeholders 中的占位符
- validation.unused_images 中的图片
- image_mapping 中 confidence < 0.6 的条目

禁止全文重写 final_exam.json！
仅输出 image_mapping_overrides.json（delta 文件）。
```

**产物检查**：
- [ ] `中间数据/image_mapping_overrides.json` 存在
- [ ] 文件不超过 50 行

**合并覆盖**：

```powershell
python -c "
import json
with open('{工作目录}/试卷数据/final_exam.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
with open('{工作目录}/中间数据/image_mapping_overrides.json', 'r', encoding='utf-8') as f:
    overrides = json.load(f)
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

**合规检查**：
```powershell
python scripts/check_compliance.py --work-dir {工作目录} --step step5 --json 试卷数据/final_exam.json
```

---

### Step6: typeset-exam（排版）

| 项目 | 内容 |
|------|------|
| **Skill** | `typeset-exam` |
| **任务** | 调用排版脚本并行生成版式一和版式二两个 Word 文档 |
| **输入** | `试卷数据/final_exam.json` + `assets/template.dotx` + `清洗产物/images/` |
| **预期产物** | `{试卷名称}-版式一.docx` + `{试卷名称}-版式二.docx` + `排版文档/quality_report.html` + `排版文档/typeset_v1_log.txt` + `排版文档/typeset_v2_log.txt` |

**执行指令**（两个命令可并行执行）：

版式一（标准版式）：
```powershell
python scripts/typeset_exam.py --json {工作目录}/试卷数据/final_exam.json --template assets/template.dotx --images {工作目录}/清洗产物/images/ --output {工作目录}/{试卷名称}-版式一.docx --report-dir {工作目录}/排版文档/ --log {工作目录}/排版文档/typeset_v1_log.txt --format v1
```

版式二（封面版式）：
```powershell
python scripts/typeset_exam.py --json {工作目录}/试卷数据/final_exam.json --template assets/template.dotx --images {工作目录}/清洗产物/images/ --output {工作目录}/{试卷名称}-版式二.docx --report-dir {工作目录}/排版文档/ --log {工作目录}/排版文档/typeset_v2_log.txt --format v2
```

**产物检查**：
- [ ] 两个脚本退出码均为 0
- [ ] `{试卷名称}-版式一.docx` 存在且文件大小 > 0
- [ ] `{试卷名称}-版式二.docx` 存在且文件大小 > 0
- [ ] `排版文档/quality_report.html` 存在

**合规检查**：
```powershell
python scripts/check_compliance.py --work-dir {工作目录} --step step6
```

---

### 汇总：流水线完成报告

```json
{
  "pipeline": "master-exam-layout",
  "version": "3.6",
  "strategy": "dual-track (code + AI) + token-saver (delta-only AI output)",
  "source_file": "<原始docx路径>",
  "steps": {
    "step1_clean_exam": "success",
    "step2_tag_structure": "success",
    "step3_tag_placeholders_anchor": "success (增量编辑)",
    "step4_tag_images_anchor": "success",
    "step5a_map_images_script": "success",
    "step5c_map_images_ai_fallback": "skipped (no unmapped items)",
    "step6_typeset_exam": "success"
  },
  "final_output": {
    "format_v1": "{工作目录}/{试卷名称}-版式一.docx",
    "format_v2": "{工作目录}/{试卷名称}-版式二.docx"
  },
  "quality_report": "{工作目录}/排版文档/quality_report.html",
  "track_statistics": {
    "code_mapped": 6,
    "ai_mapped": 2,
    "ai_bypassed": 6
  },
  "token_saved": {
    "step3_incremental": "~94% output tokens",
    "step5_script_first": "100% (happy path, no AI needed)"
  }
}
```

---

## Constraints

你绝对不能做以下事情：

### 不越界
- **不分析试卷内容**
- **不参与图片映射**：不猜测哪张图对应哪个位置（Step5c 仅做修正）
- **不自行排版**：不直接调用 python-docx
- **不修改 Skill 文件**

### 不跳步
- **严格 Step1→Step6 顺序**
- **Step4 可与 Step2 并行**，Step3 必须等 Step2 和 Step4 都完成
- **anchor_count == 0 时跳过 Step3 和 Step4**，按 Step1 → Step2 → Step5a → Step6 执行

### v3.6 特有约束（token 优化）
- **Step3 必须使用增量编辑**：先 copy structure.json → with_placeholders.json，然后用 Edit 工具逐占位符修改，禁止全量输出
- **Step5 脚本优先**：必须先运行 map_images.py（5a），AI 仅在脚本有未映射项时才介入（5c）
- **Step5c 只输出 delta**：AI 只输出 image_mapping_overrides.json，由主编排用脚本合并
- **禁止全量重写 final_exam.json**：该文件由脚本生成，AI 不重写

### v3.5 特有约束
- **不为 inline 图创建占位符**：`{{image:img_xxx}}` 已由代码在 Step1 生成
- **Step3 仅处理 anchor 图**：不要读取 inline 图片的占位符
- **检查 `original_type` 字段**：在 image_manifest.json 中确认分流依据存在

---

## 快速启动指令

```
请按 master-exam-layout 技能执行流水线：
输入文件: <原始 docx 绝对路径>
```

主编排收到指令后：
1. 确认输入文件存在
2. 调用 `resolve_output_root()` 确认桌面"排版结果"文件夹可访问
3. 创建工作目录（`排版结果/{试卷名称}/`）及四个子目录
4. 逐步骤调度执行
5. 每步完成后报告状态
6. 全部完成后输出汇总报告