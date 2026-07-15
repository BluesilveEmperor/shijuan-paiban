# 地理试卷排版 v3.5 重构方案

## 版本定位

| 版本 | 策略 | 定位 |
|------|------|------|
| **v3.0** | 纯 AI 驱动 | 留给未来 AI 足够强大时使用——模型自行理解图片内容、判断图片位置、完成全部映射 |
| **v3.5** | 代码 + AI 双轨 | 当前版本——代码处理确定性逻辑，AI 仅介入不确定性场景，最大化降低对模型智能度的依赖 |

---

## 一、核心问题与解决思路

### 1.1 问题根源

试卷源文档中的图片有两种存在形式：

```
【内嵌图片 (inline)】
段落: "读图回答3-4题。四大地理区域分布如图1所示。 [图] 下列关于..."
       ↑ 人有意把图放在这段文字后面，paragraph_index 可靠

【浮动图片 (anchor)】  
视觉上图片飘在页面右侧，文字绕在左边。
锚点挂在了某个段落上，但这个段落不一定就是图片该出现的位置。
       ↑ paragraph_index 不可靠，必须 AI 介入判断
```

### 1.2 核心判断

> **内嵌图的 paragraph_index 是可靠的，因为这是原始排版者有意为之。浮动图的 paragraph_index 不可靠，需要 AI 验证。**

### 1.3 解决思路：双轨分流

```
所有图片
  ├─ original_type == "inline"  → 代码确定路径（零 AI 调用）
  │    paragraph_index → 顺序映射到占位符 → 锁定
  │
  └─ original_type == "anchor"  → AI 不确定路径
       AI 分析图片内容 + 文档上下文 → 在剩余空位中匹配 → 插入占位符
```

### 1.4 关键设计决策

- **不给 AI 加硬约束**：一段材料可以有多张图（如地形图 + 降水量图）。不做"一段一图"的限制。
- **占位符一步到位**：anchor 图的占位符由 AI 直接创建并确定位置，不经过"先创建占位符再映射"的两阶段流程。
- **inline 图零 AI 依赖**：`content.md` 中的 `{{image:img_xxx}}` 标记本身就是占位符，代码直接使用。

---

## 二、流水线变更总览

### 2.1 v3.0 流水线（现状）

```
原始试卷.docx
  [Step1] clean_exam          → content.md + images/ + image_manifest.json
  [Step2] tag_structure       → structure.json                          (AI)
  [Step3] tag_placeholders    → with_placeholders.json                  (AI, 全部图片)
  [Step4] tag_images          → image_descriptions.json                 (AI, 全部图片)
  [Step5] map_images          → final_exam.json                         (AI或脚本)
  [Step6] typeset_exam        → final_exam.docx                         (脚本)
```

### 2.2 v3.5 流水线（双轨）

```
原始试卷.docx
  [Step1] clean_exam          → content.md + images/ + image_manifest.json
  │                              ↑ 新增 original_type 字段
  ▼
  [Step2] tag_structure       → structure.json                          (AI)
  │
  ├─ 内嵌图 (inline) ───────────────────────────────┐
  │   content.md 中的 {{image:img_xxx}} 即占位符      │
  │   零 AI 调用                                      │
  │                                                  ▼
  ├─ 浮动图 (anchor) ── [Step4] tag_images_anchor → anchor_descriptions.json (AI)
  │                          ↓
  │                     [Step3] tag_placeholders_anchor → with_placeholders.json (AI)
  │                          ↓
  │                     [Step5] map_images          → final_exam.json
  │                          ↑ 代码处理 inline + AI 处理 anchor
  ▼
  [Step6] typeset_exam        → final_exam.docx                         (脚本)
```

### 2.3 步骤职责变更对比

| 步骤 | v3.0 | v3.5 |
|------|------|------|
| Step1 | 清洗+提取图片 | 清洗+提取图片 + **记录 original_type** |
| Step2 | AI 打结构（不变） | **同 v3.0** |
| Step3 | AI 为全部图片创建占位符 | **AI 仅对 anchor 图创建占位符** |
| Step4 | AI 分析全部图片 | **AI 仅分析 anchor 图（可选）** |
| Step5 | AI/脚本做全部映射 | **代码锁定 inline + AI 匹配 anchor** |
| Step6 | 脚本排版（不变） | **同 v3.0** |

---

## 三、脚本改动清单

### 3.1 clean_docx.py

**改动位置**：`rule_1_19_convert_floating_images()` 执行之前

**改动内容**：在阶段二"图片处理"中，rule_1_19 执行前，增加一个预扫描步骤，记录每张图片的原始类型。

```python
def record_original_image_types(doc, logger):
    """预扫描：在浮动图片转换前，记录每张图片的原始类型（inline/anchor）。

    将类型信息写入一个临时 JSON 文件，供 extract_images.py 读取后
    合并到 image_manifest.json 的 original_type 字段。
    
    Returns:
        dict: {image_rid: "inline" | "anchor"}
    """
    original_types = {}
    for drawing in doc.element.body.findall(f'.//{qn("w:drawing")}'):
        # 获取 rId
        for desc in drawing.findall(f'.//{qn("wp:docPr")}'):
            rid = None
            for blip in drawing.findall(f'.//{qn("a:blip")}'):
                rid = blip.get(qn('r:embed'))
                break
            if not rid:
                for imagedata in drawing.findall(f'.//{qn("v:imagedata")}'):
                    rid = imagedata.get(qn('r:id'))
                    break
            if rid:
                # 判断类型
                if drawing.find(qn('wp:anchor')) is not None:
                    original_types[rid] = "anchor"
                elif drawing.find(qn('wp:inline')) is not None:
                    original_types[rid] = "inline"
                else:
                    original_types[rid] = "unknown"
    return original_types
```

**产物**：`{工作目录}/清洗产物/_original_image_types.json`（临时文件，供 extract_images.py 消费）

### 3.2 extract_images.py

**改动内容**：读取 `_original_image_types.json`，在 `image_manifest.json` 每条图片记录中增加 `original_type` 字段。

```json
{
  "image_id": "img_005",
  "image_type": "inline",
  "original_type": "anchor",
  "paragraph_index": 12,
  ...
}
```

**字段说明**：
- `image_type`：提取时的类型（经过 rule_1_19 后，始终为 `inline`）
- `original_type`：原始类型，`"inline"` | `"anchor"` | `"vml"` | `"unknown"`

### 3.3 map_images.py（重点改动）

**改动内容**：拆分 `build_mapping()` 为双轨逻辑。

```python
def build_mapping_dual_track(placeholders, images, anchor_descriptions=None):
    """双轨映射：代码处理 inline 图 + AI 结果处理 anchor 图。

    Track 1 (代码，确定路径)：
      - 筛选 original_type == "inline" 的图片
      - 按 paragraph_index 排序
      - 按题目顺序分配到有效占位符
      - 锁定映射 + 标记 consumed 占位符

    Track 2 (AI，不确定路径)：
      - 筛选 original_type == "anchor" 的图片
      - AI 已预先在 Step3/4 完成占位符创建和图片分析
      - 读取 with_placeholders.json 中 anchor 图对应的占位符
      - 直接采纳 AI 的映射结果（AI 已结合图片分析做了判断）
    
    Returns:
        mapping_result dict
    """
    
    # ── Track 1: inline 图片 → 代码确定路径 ──
    inline_images = [img for img in images 
                     if img.get("_original_type") == "inline"
                     and img.get("_file_size", 0) >= SYMBOL_SIZE_THRESHOLD]
    inline_images.sort(key=lambda x: x.get("_paragraph_index", 9999))
    
    # 收集所有占位符（inline + anchor）
    # inline 图的占位符来自 content.md 的 {{image:img_xxx}} 位置
    # anchor 图的占位符来自 AI Step3 产物
    inline_placeholders = collect_inline_placeholders(placeholders)  # 新增
    anchor_placeholders = collect_anchor_placeholders(placeholders)  # 标记来源
    
    # 按题目顺序映射 inline 图
    sorted_inline_phs = sorted(inline_placeholders, key=ph_sort_key)
    for i, ph in enumerate(sorted_inline_phs):
        if i < len(inline_images):
            img = inline_images[i]
            mappings.append({
                "placeholder_id": ph["placeholder_id"],
                "image_id": img["image_id"],
                "confidence": 0.95,  # 高置信度，因为 inline 位置可靠
                "reason": f"内嵌图片，位置确定（段落{img.get('_paragraph_index', '?')}）",
                "track": "code"  # 标记来源
            })
    
    # ── Track 2: anchor 图片 → AI 匹配路径 ──
    anchor_images = [img for img in images
                     if img.get("_original_type") == "anchor"
                     and img.get("_file_size", 0) >= SYMBOL_SIZE_THRESHOLD]
    
    # anchor 图占位符已由 AI Step3 创建并确定了位置
    # 按题目顺序排序，与剩余未使用的 anchor 图匹配
    anchor_images.sort(key=lambda x: x.get("_paragraph_index", 9999))
    
    for i, ph in enumerate(sorted(anchor_placeholders, key=ph_sort_key)):
        if i < len(anchor_images):
            img = anchor_images[i]
            # 可选：使用 anchor_descriptions 做关键词验证
            confidence = 0.75  # 基础置信度
            reason = f"浮动图片，AI 判断归位（锚点段落{img.get('_paragraph_index', '?')}）"
            
            # 如果 AI 分析结果中有高置信度匹配，提升置信度
            if anchor_descriptions:
                matched_desc = find_matching_description(ph, img, anchor_descriptions)
                if matched_desc and matched_desc.get("_ai_confidence"):
                    confidence = matched_desc["_ai_confidence"]
                    reason = matched_desc.get("_ai_reason", reason)
            
            mappings.append({
                "placeholder_id": ph["placeholder_id"],
                "image_id": img["image_id"],
                "confidence": confidence,
                "reason": reason,
                "track": "ai"
            })
    
    # 符号小图单独处理（同 v3.0 逻辑）
    # ...
    
    return mapping_result
```

**新增辅助函数**：

```python
def classify_images_by_original_type(images):
    """按 original_type 分类图片。
    
    Returns:
        (inline_images, anchor_images, vml_images, symbol_images)
    """
    inline = []
    anchor = []
    vml = []
    symbols = []
    
    for img in images:
        orig_type = img.get("_original_type", img.get("image_type", "unknown"))
        file_size = img.get("_file_size", 0)
        
        if file_size < SYMBOL_SIZE_THRESHOLD:
            symbols.append(img)
        elif orig_type == "inline":
            inline.append(img)
        elif orig_type == "anchor":
            anchor.append(img)
        elif orig_type == "vml":
            vml.append(img)
        else:
            # unknown: 保守处理，归入 anchor（需要 AI 验证）
            anchor.append(img)
    
    return inline, anchor, vml, symbols


def collect_inline_placeholders(placeholders):
    """从所有占位符中筛选 inline 类型（来自 content.md 标记）。"""
    return [ph for ph in placeholders 
            if ph.get("_source") == "inline"]


def collect_anchor_placeholders(placeholders):
    """从所有占位符中筛选 anchor 类型（来自 AI Step3）。"""
    return [ph for ph in placeholders 
            if ph.get("_source") != "inline"]
```

---

## 四、AI Skill 改动清单

### 4.1 Step3: tag_placeholders_anchor（替代原 tag_placeholders）

**职责**：仅对浮动图（`original_type == "anchor"`）创建占位符。

**输入**：
- `structure.json`（Step2 产物）
- `image_manifest.json`（筛选 `original_type == "anchor"` 的条目）
- `content.md`（文档全文）
- `anchor_descriptions.json`（Step4 产物，anchor 图的 AI 内容分析）

**任务**：
1. 阅读文档全文，理解每道题的语义
2. 对每张 anchor 图，分析其内容描述（来自 Step4）
3. 判断该图应该插入到哪道题、哪个位置（材料/题干/子问题）
4. 在对应位置创建占位符 `{{image:ph_xxx}}`
5. 占位符标记 `_source: "anchor"` 和 `_ai_reason`（AI 判断依据）

**输出**：`with_placeholders.json`（同 v3.0 格式，但仅含 anchor 图占位符 + _source/_ai_reason 内部字段）

**约束**：
- 不创建 inline 图的占位符（inline 图由代码处理）
- 允许一张题有多张图
- 无法确定时标记 `uncertain: true`

### 4.2 Step4: tag_images_anchor（替代原 tag_images）

**职责**：仅分析浮动图（`original_type == "anchor"`）的内容。

**输入**：
- `image_manifest.json`（筛选 `original_type == "anchor"` 的条目）
- `images/` 目录下对应的图片文件

**任务**：
1. 检测模型是否支持图片处理
2. 对每张 anchor 图进行内容理解（类型、主题、关键词、OCR）
3. 产出图片描述

**输出**：`anchor_descriptions.json`

**新增字段**（相比 v3.0 image_descriptions.json）：
```json
{
  "images": [
    {
      "image_id": "img_005",
      "file_name": "img_005.png",
      "original_type": "anchor",
      "anchor_paragraph_index": 12,
      "anchor_context": "北方地区冬季寒冷干燥...",
      "type": "地图",
      "summary": "中国四大地理区域分布图",
      "keywords": ["北方地区", "南方地区", "西北地区", "青藏地区"],
      "ocr_text": ["北方地区", "南方地区"],
      "discipline_features": ["区域划分", "分界线"],
      "clues": ["四大地理区域", "分界线"],
      "position_hint": "材料中提到'四大地理区域分布如图'，应插入该材料位置",
      "uncertain": false
    }
  ]
}
```

**与 v3.0 差异**：
- 只处理 `original_type == "anchor"` 的图片
- 新增 `anchor_paragraph_index`、`anchor_context`、`position_hint` 字段
- `position_hint` 是 AI 对图片应放位置的初步判断，作为 Step3 的输入参考

### 4.3 Step5: map_images（更新）

**职责变更**：从"AI 占位符 ↔ 图片语义匹配"变为"代码处理 inline + 采纳 AI 的 anchor 结果"。

**输入**：
- `structure.json`（含 inline 图占位符 `{{image:img_xxx}}`）
- `with_placeholders.json`（AI Step3 为 anchor 图创建的占位符）
- `image_manifest.json`（含 `original_type` 字段）
- `anchor_descriptions.json`（AI Step4 对 anchor 图的分析）
- `content.md`

**任务**：
1. 读取 `image_manifest.json`，按 `original_type` 分流图片
2. **Track 1（代码）**：inline 图按 paragraph_index 顺序映射到 inline 占位符
3. **Track 2（AI 结果）**：读取 anchor 图的占位符，与 anchor 图一一映射
4. 组装 `final_exam.json`（统一格式，与 v3.0 兼容）

**输出**：`final_exam.json`（格式同 v3.0，新增 `track` 字段标记映射来源）

### 4.4 不再需要的步骤

| 步骤 | v3.0 | v3.5 | 说明 |
|------|------|------|------|
| tag_placeholders (原) | AI 为全部图片创建占位符 | **删除** | 拆分为 inline（代码） + anchor（新 Step3） |
| tag_images (原) | AI 分析全部图片 | **删除** | 替换为 tag_images_anchor（仅 anchor 图） |

---

## 五、数据流图

```
                      原始试卷.docx
                           │
                    [Step1] clean_exam
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        content.md   image_manifest   images/
        (含 img_xxx    (含 original    (全部图片)
         标记)          _type字段)
              │            │
              ▼            ├──────────────────┐
        [Step2] tag_       │                  │
        structure (AI)     │                  │
              │            │                  │
              ▼            │                  │
        structure.json     │                  │
              │            │                  │
    ┌─────────┴────────────┤                  │
    │                      │                  │
    │  inline 图            │  anchor 图        │
    │  (代码处理)           │  (AI 处理)        │
    │                      │                  │
    │  content.md 中的      │        [Step4] tag_images_
    │  {{image:img_xxx}}    │        anchor (AI)
    │  即占位符             │                  │
    │                      │                  ▼
    │                      │        anchor_descriptions.json
    │                      │                  │
    │                      │                  ▼
    │                      │        [Step3] tag_placeholders_
    │                      │        anchor (AI)
    │                      │                  │
    │                      │                  ▼
    │                      │        with_placeholders.json
    │                      │        (仅 anchor 图占位符)
    │                      │                  │
    └──────────────────────┴──────────────────┘
                           │
                    [Step5] map_images
                    (代码 + AI 双轨)
                           │
                           ▼
                    final_exam.json
                           │
                    [Step6] typeset_exam
                           │
                           ▼
                    final_exam.docx
```

---

## 六、image_manifest.json 格式变更

### v3.0

```json
{
  "images": [
    {
      "image_id": "img_001",
      "image_type": "inline",
      "paragraph_index": 5,
      ...
    }
  ]
}
```

### v3.5

```json
{
  "images": [
    {
      "image_id": "img_001",
      "image_type": "inline",
      "original_type": "inline",
      "paragraph_index": 5,
      ...
    },
    {
      "image_id": "img_002",
      "image_type": "inline",
      "original_type": "anchor",
      "paragraph_index": 8,
      ...
    }
  ]
}
```

---

## 七、final_exam.json image_mapping 格式变更

### v3.0

```json
{
  "image_mapping": [
    {
      "placeholder_id": "ph_001",
      "image_id": "img_001",
      "confidence": 0.85,
      "reason": "关键词匹配: 等高线"
    }
  ]
}
```

### v3.5

```json
{
  "image_mapping": [
    {
      "placeholder_id": "img_001",
      "image_id": "img_001",
      "confidence": 0.95,
      "reason": "内嵌图片，位置确定（段落6）",
      "track": "code"
    },
    {
      "placeholder_id": "ph_anchor_001",
      "image_id": "img_004",
      "confidence": 0.82,
      "reason": "浮动图片，AI匹配：材料'四大地理区域分布图'语义吻合",
      "track": "ai"
    }
  ]
}
```

**新增字段**：
- `track`: `"code"` | `"ai"` —— 标识映射来源，便于排查问题

---

## 八、兼容性保证

### 8.1 向下兼容 v3.0

`final_exam.json` 格式保持兼容。v3.6 的 `typeset_exam.py` 可以同时处理 v3.0 和 v3.5 产出的 `final_exam.json`。

新增的 `track` 和 `original_type` 字段为**可选字段**，不影响现有排版逻辑。

### 8.2 占位符格式统一

无论来源（inline 代码 还是 anchor AI），所有占位符统一使用 `{{image:xxx}}` 格式：
- inline 图：`{{image:img_001}}` （与 content.md 标记一致）
- anchor 图：`{{image:ph_anchor_001}}` （AI Step3 创建）

### 8.3 检测 original_type 缺失

如果旧版 `image_manifest.json` 没有 `original_type` 字段，`map_images.py` 回退到 v3.0 逻辑（全部走 AI 路径），保证不崩溃。

---

## 九、实施顺序

| 阶段 | 内容 | 依赖 | 验证方式 |
|------|------|------|---------|
| **第1阶段** | `clean_docx.py` 增加 `record_original_image_types()` | 无 | 检查 `_original_image_types.json` 产出 |
| **第2阶段** | `extract_images.py` 读取并写入 `original_type` | 第1阶段 | 检查 `image_manifest.json` 含 `original_type` |
| **第3阶段** | `map_images.py` 双轨逻辑 | 第2阶段 | 用有 inline + anchor 的试卷跑，检查映射结果 |
| **第4阶段** | AI Step4 `tag_images_anchor` | 第2阶段 | 检查 `anchor_descriptions.json` 质量 |
| **第5阶段** | AI Step3 `tag_placeholders_anchor` | 第3+4阶段 | 检查 `with_placeholders.json` 合理性 |
| **第6阶段** | `master_exam_layout` 调度更新 | 全部 | 端到端跑通完整流水线 |
| **第7阶段** | 老试卷回归测试 | 全部 | v3.0 能通过的试卷，v3.5 也通过 |

---

## 十、预期效果

| 指标 | v3.0 | v3.5 | 提升 |
|------|------|------|------|
| inline 图定位准确率 | 依赖 AI 匹配质量 | ~100%（代码确定） | 消除 AI 出错可能 |
| AI 调用次数（图片处理） | N 张图全部 | 仅 anchor 图 | 减少 60-80% |
| 一段多图支持 | 可能冲突 | 天然支持 | 消除误判 |
| 低能模型容错 | inline 图也会出错 | inline 图不受影响 | 核心路径不依赖 AI |
| 锚点段落误判 | 可能发生 | anchor 图由 AI 语义判断 | 精准介入 |

---

## 十一、风险与边界

### 11.1 已知边界

1. **VML 图片**：`original_type == "vml"` 的图片（通常为旧版 Word 格式），暂归入 anchor 路径，由 AI 处理
2. **未知类型**：`original_type == "unknown"` 保守处理，归入 anchor 路径
3. **符号小图**（< 2KB）：与 v3.0 逻辑一致，不作为内容图片映射
4. **Inline 图片的 paragraph_index 也可能偏差**：如果源文档本身就是用 Word 拼凑的（复制粘贴导致图片错位），inline 的 paragraph_index 也不可靠。此类试卷属于极端情况，v3.0 同样处理不好，不在本次优化范围内。

### 11.2 回退策略

- 如果 `original_type` 字段缺失或全部为 `unknown`，map_images.py 回退到 v3.0 的纯 AI 路径
- 如果 AI Step3/Step4 失败（anchor 图），anchor 图降级为 paragraph_index 顺序匹配
- 排版脚本无需改动，兼容两种产出的 `final_exam.json`

---

## 十二、文件变更清单

### 修改的文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/clean_docx.py` | 修改 | 新增 `record_original_image_types()`，在 rule_1_19 前调用 |
| `scripts/extract_images.py` | 修改 | 读取 `_original_image_types.json`，写入 `original_type` |
| `scripts/map_images.py` | **重点修改** | 双轨映射逻辑 `build_mapping_dual_track()` |
| `scripts/batch_process.py` | 修改 | 适配新的产物路径和步骤 |

### 新增的 AI Skill 文件

| 文件 | 说明 |
|------|------|
| `.trae/skills/tag_placeholders_anchor/SKILL.md` | AI 为 anchor 图创建占位符 |
| `.trae/skills/tag_images_anchor/SKILL.md` | AI 仅分析 anchor 图内容 |

### 不再需要的文件

| 文件 | 说明 |
|------|------|
| `.trae/skills/tag_placeholders/SKILL.md` | 被 `tag_placeholders_anchor` 替代 |
| `.trae/skills/tag_images/SKILL.md` | 被 `tag_images_anchor` 替代 |

### 删除的 AI Skill 文件（v3.5）

| 文件 | 对应 v3.0 |
|------|----------|
| `.trae/skills/tag_placeholders/SKILL.md` | 删除：改为仅 AI 处理 anchor 图的 `tag_placeholders_anchor` |
| `.trae/skills/tag_images/SKILL.md` | 删除：改为仅 AI 分析 anchor 图的 `tag_images_anchor` |
