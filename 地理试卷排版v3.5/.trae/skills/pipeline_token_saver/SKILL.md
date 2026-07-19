---
name: "pipeline_token_saver"
description: "Reference document for v3.6 token optimization strategies (incremental editing, script-first, delta output). Not a pipeline step — its content has been integrated into master_exam_layout. Read for background only."
---

# Pipeline Token Saver — 增量 JSON 优化

## 问题诊断

当前 v3.5 流水线在 Step3 和 Step5 中，AI 会**全文重写**大型 JSON 文件，而实际只需要追加少量增量数据：

| 步骤 | 当前输出 | 文件大小 | 实际增量 | 浪费比例 |
|------|---------|---------|---------|:---:|
| Step3 | `with_placeholders.json` | ~1500行 | ~20行占位符 | **~95%** |
| Step5 | `final_exam.json` | ~2000行 | ~150行映射+校验 | **~90%** |

**根因**：AI 把整个 `structure.json`（1000-3000行试卷结构）抄写了两遍——Step3 抄一遍加占位符，Step5 再抄一遍加映射。

## 核心原则

> **AI 只输出"增量"（delta），Python 脚本负责"合并"（merge）。**

这与 v3.5 的设计哲学一致：「代码处理确定性逻辑，AI 仅介入不确定性场景。」

---

## 优化方案

### 优化 1：Step3 使用 Edit 工具增量修改（当前已有但需强制执行）

**现状**：tag_placeholders_anchor SKILL.md 第157行已规定「使用 Edit 工具增量修改 structure.json」，但 AI 执行时常会全文重写。

**强化措施**：
- Step3 不再生成独立的 `with_placeholders.json`
- 直接用 Edit 工具在 `structure.json` 中追加 `placeholders` 数组
- 追加完成后，`structure.json` 即成为 `with_placeholders.json` 的等价物

**执行方式**（在 tag_placeholders_anchor 技能中）：
```
1. 读取 structure.json，定位需要添加占位符的题目节点
2. 使用 Edit 工具，将对应题目的 "placeholders": [] 替换为 "placeholders": [{...}]
3. 每个占位符单独一次 Edit 调用（每次只改一个数组元素）
4. 完成后运行 validate_json.py 校验
```

**预期节省**：Step3 token 消耗降低 ~90%（从输出1500行降到输出20行）

---

### 优化 2：Step5 代码优先 + AI 兜底（核心优化）

**现状**：Step5 由 AI 技能（map_images）执行，AI 读取5个文件、做语义匹配、输出完整的 final_exam.json（~2000行）。

**问题**：`scripts/map_images.py` 已实现双轨映射逻辑（Track1 inline 代码确定 + Track2 anchor 关键词/顺序匹配），但流水线未使用它。AI 重做了一遍脚本已能做的事。

**新流程**：

```
Step5 输入: structure.json + anchor_descriptions.json + image_manifest.json + content.md
    │
    ├─ [5a] 运行 map_images.py（代码，零 token）→ final_exam.json
    │       - Track1: inline 图自动映射（confidence=0.95）
    │       - Track2: anchor 图按关键词+段落顺序匹配
    │
    ├─ [5b] 检查产物
    │       - 如果 validation.warnings 为空 → 完成，跳过 5c
    │       - 如果存在 unmapped_placeholders 或 low_confidence(<0.6) → 进入 5c
    │
    └─ [5c] AI 仅处理问题项（兜底，少量 token）
            - 只读取 unmapped 的占位符和未使用的图片描述
            - 输出 image_mapping_overrides.json（仅覆盖项，~10-30行）
            - Python 脚本应用覆盖 → 更新 final_exam.json
```

**命令**：
```powershell
# 5a: 代码优先映射
python scripts/map_images.py --placeholders {工作目录}/中间数据/structure.json --image-descriptions {工作目录}/中间数据/anchor_descriptions.json --images-manifest {工作目录}/清洗产物/image_manifest.json --content {工作目录}/清洗产物/content.md --output {工作目录}/试卷数据/final_exam.json
```

**预期节省**：Step5 在 happy path 下 **零 AI token**；问题路径下仅 ~200 token（vs 当前 ~5000+ token）。

---

### 优化 3：合并重复文件读取

**现状**：Step5 AI 技能要求同时读取 `structure.json` 和 `with_placeholders.json`，但两者内容 95% 相同。

**优化**：
- Step3 直接修改 `structure.json`（不再生成独立 `with_placeholders.json`）
- Step5 只需读取 `structure.json`（已含占位符）+ `anchor_descriptions.json` + `image_manifest.json`
- 减少一个文件读取，节省输入 token

---

## 具体实施改动

### 1. 修改 Step3 技能行为（tag_placeholders_anchor）

在 `tag_placeholders_anchor/SKILL.md` 中加入强制执行条款：

```markdown
## 强制约束（v3.6 新增）

1. **禁止全量输出**：不得使用 Write 工具输出完整的 with_placeholders.json
2. **必须增量编辑**：仅使用 Edit 工具在 structure.json 中追加 placeholders
3. **逐占位符编辑**：每个占位符单独一次 Edit 调用
4. **编辑后校验**：每次 Edit 后运行 `python scripts/validate_json.py` 确认 JSON 有效
```

### 2. 修改 Step5 调度方式（master_exam_layout）

```markdown
### Step5: map_images（代码优先 + AI 兜底）

| 项目 | 内容 |
|------|------|
| **5a** | 运行 `python scripts/map_images.py`（代码路径，零 AI token） |
| **5b** | 检查产物：若 waring 为空 → 完成 |
| **5c** | 仅当存在未映射项时，调用 AI 做针对性修复 |

**执行指令（5a）**：
```powershell
python scripts/map_images.py \
    --placeholders {工作目录}/中间数据/structure.json \
    --image-descriptions {工作目录}/中间数据/anchor_descriptions.json \
    --images-manifest {工作目录}/清洗产物/image_manifest.json \
    --content {工作目录}/清洗产物/content.md \
    --output {工作目录}/试卷数据/final_exam.json
```

**执行指令（5c，仅问题路径）**：
```
请仅对以下未映射的占位符和未使用图片做语义匹配：
- 读取 {工作目录}/试卷数据/final_exam.json 中的 validation.unmapped_placeholders
- 读取 {工作目录}/中间数据/anchor_descriptions.json 中对应图片
- 输出 image_mapping_overrides.json（仅覆盖项）
```

### 3. 新增合并脚本（可选，用于 5c 覆盖场景）

如果 AI 在 5c 输出了 `image_mapping_overrides.json`，用以下命令合并：

```powershell
python -c "
import json
with open('final_exam.json') as f: data = json.load(f)
with open('image_mapping_overrides.json') as f: overrides = json.load(f)
# 应用覆盖
existing = {m['placeholder_id']: m for m in data['image_mapping']}
for m in overrides.get('mappings', []):
    existing[m['placeholder_id']] = m
data['image_mapping'] = list(existing.values())
data['validation'] = overrides.get('validation', data['validation'])
with open('final_exam.json', 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2)
"
```

---

## 不可复用的 JSON 文件说明

以下文件**必须每个试卷单独生成**，无法跨试卷复用：

| 文件 | 原因 |
|------|------|
| `content.md` | 每份试卷正文唯一 |
| `structure.json` | 每份试卷结构唯一（题号、题干、选项均不同） |
| `image_manifest.json` | 每份试卷图片不同 |
| `anchor_descriptions.json` | 每份试卷图片内容不同 |

**能找到"复用"空间的不是文件级别，而是操作级别**：同一个文件在 pipeline 中不需要被多次全文改写。

---

## 预期效果

| 指标 | 优化前 | 优化后 | 节省 |
|------|--------|--------|:---:|
| Step3 AI token（输出） | ~8000 | ~500 | **~94%** |
| Step5 AI token（输入+输出） | ~15000 | ~0（happy path） | **~100%** |
| Step5 AI token（问题路径） | ~15000 | ~2000 | **~87%** |
| **总流水线 AI token** | ~35000 | ~12000 | **~65%** |

---

## 使用方式

在主编排中追加：

```
请按 pipeline_token_saver 优化模式执行流水线：
输入文件: <原始 docx 绝对路径>

要求：
- Step3 使用 Edit 工具增量修改 structure.json（禁止全量输出）
- Step5 优先运行 map_images.py 脚本，AI 仅处理脚本无法匹配的项
```
