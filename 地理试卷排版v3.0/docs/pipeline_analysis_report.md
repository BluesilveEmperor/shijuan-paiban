# 流水线架构分析报告：图片分析时机与占位符准确性

> 基于 `templates/选择题案例补充说明.txt` 中 12 个真实选择题场景的对照分析。
> 日期：2026-07-10

---

## 一、补充案例揭示的核心问题

从 12 个补充案例中提取出 **6 类当前流水线可能处理不当的场景**：

### 1. 图片合并判断（案例：图5+图6、左图+右图）

**场景**：材料文字中提到了"图5"和"图6"两张独立的图，但实际文档中它们在一张图片内。

**当前处理**：
- Step3（tag_placeholders）仅根据文字上下文判断 → 创建 2 个占位符
- Step4（tag_images）分析图片 → 发现是 1 张合并图
- Step5（map_images）收到 2 个占位符 vs 1 张图片 → 1 个占位符 unmapped

**问题**：Step3 不知道图片是合并的，做出了错误判断，需要 Step5 补救。

### 2. 题目级图片无文字引用（案例：14题植被景观照片）

**场景**：题目题干没有任何"如图""下图"等关键词，但题干下方确实有一张图片需要考生观察。

**当前处理**：
- Step3 的优先级 1-4 全部依赖文字触发词 → 可能漏掉此图片位置
- 优先级 3（`content.md` 标记）可以补救，但标记定位可能不够精确

**问题**：纯上下文判断可能漏掉无文字引用的图片。

### 3. 图片引用层级区分（案例：15题拱架角度）

**场景**：题目中问"拱架①与地平面的夹角"，需要看材料中的图片，但题目本身没有独立图片。

**当前处理**：
- Step3 可能误判为题目级图片 → 为 15 题也创建占位符
- Step5 发现重复引用 → 标记冗余

**问题**：Step3 无法区分"题目引用材料图片"和"题目有独立图片"。

### 4. 图片数量不匹配（案例：图2+图3，仅1张图）

**场景**：材料文字说"图2...图3..."（2张），但 `content.md` 仅检测到 1 个图片标记。

**当前处理**：
- Step3 根据文字创建 2 个占位符
- Step4 分析后只有 1 张图片
- Step5 有 1 个占位符 unmapped

**问题**：Step3 无法判断是"文档缺失图片"还是"图片合并"，需要人工标注。

### 5. 选项含图片（案例：23题选项为图）

**场景**：选项 A/B/C/D 本身就是图片，而非文字描述。

**当前处理**：
- 已在 Step3 优先级 5 中覆盖 → 处理较好
- 但 `location_type: "option"` 的占位符嵌入位置需要更精确的规定

**问题**：影响较小，当前已覆盖。

### 6. "（如下图）"在 content 内部（案例：东兰墨米）

**场景**：图片位置提示不在 guide_sentence 中，而是 material.content 正文的一部分。

**当前处理**：
- Step2 可能误将"（如下图）"当成引导语提取
- Step3 可能漏掉 content 内部的图片位置提示

**问题**：需要在 Step2 打标案例中明确"（如下图）"属于 content。

---

## 二、当前流水线架构分析

### 2.1 当前架构

```
Step1 (clean_exam)        → content.md + images/
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
Step2 (tag_structure)   Step4 (tag_images)    (并行)
     → structure.json   → image_descriptions.json
          │                   │
          ▼                   │
Step3 (tag_placeholders)      │     ← Step3 不知道图片内容
     → with_placeholders.json │
          │                   │
          └───────────────────┘
                    │
                    ▼
Step5 (map_images)         → final_exam.json
                    │
                    ▼
Step6 (typeset_exam)       → final_exam.docx
```

### 2.2 当前架构的优势

- **并行度高**：Step2+Step3 与 Step4 可同时执行，总时间 ≈ max(T2+T3, T4)
- **职责清晰**：Step3 只管"哪里有图"，Step4 只管"图是什么"，Step5 做匹配
- **降级容错**：当模型不支持图片时（`model_support_images: false`），Step4 跳过，Step5 回退到文档顺序匹配

### 2.3 当前架构的不足（基于补充案例分析）

| 场景 | Step3 错误类型 | Step5 能否修复 | 修复代价 |
|------|---------------|---------------|---------|
| 图片合并（2→1） | 多创建占位符 | 能（标记 unmapped） | 低，但浪费 token |
| 无文字引用图片 | 可能漏掉 | 不能（Step5 只匹配，不新增占位符） | **高，可能永久丢失** |
| 题目引用材料图片 | 多创建占位符 | 能（标记冗余） | 低 |
| 图片数量不匹配 | 占位符数量不对 | 部分能（标记 unmapped） | 中，需人工判断 |

**核心矛盾**：Step3 在最需要图片内容信息的场景（无文字引用、合并判断、数量不匹配）下，恰好没有图片内容信息。

---

## 三、核心决策：图片分析是否应该前置？

### 选项 A：保持当前架构（Step4 与 Step2+3 并行）

```
Step2 + Step3（串行） ∥ Step4（并行）
```

**优势**：
- 总时间最优（并行度高）
- 架构改动最小（零改动）
- 大多数简单场景（占比 > 80%）处理正确
- 降级路径成熟

**劣势**：
- "无文字引用图片"场景可能永久漏掉占位符
- 图片合并/数量不匹配场景需要 Step5 补救
- Step5 只能标记 unmapped，不能新增占位符

### 选项 B：Step4 前置（Step4 与 Step2 并行，Step3 等两者完成）

```
Step2 ∥ Step4（并行） → Step3（等两者） → Step5
```

**优势**：
- Step3 有图片描述信息，可以做更准确的判断：
  - 合并图检测 → 创建正确数量的占位符
  - 无文字引用图片 → 通过图片内容 + 题目主题语义匹配发现
  - 数量不匹配 → 根据图片分析结果 + 上下文综合判断
- 减少 Step5 的补救负担
- 提高占位符整体准确率

**劣势**：
- Step3 需要等待 Step4 → 总时间可能略有增加
- Step4 模型不支持时 → Step3 降级回纯上下文判断（等价于当前）
- 需要修改 Step3 和 master_exam_layout 的逻辑

### 选项 C：两步式 Step3（推荐，折中方案）

保持 Step4 并行，但 Step3 分两轮：

```
Step2 ∥ Step4（并行）
    │
    ▼
Step3-Pass1（纯上下文，快速标注确定的位置）
    │
    ▼
Step3-Pass2（Step4 完成后，仅回查 uncertain 的占位符）
    │
    ▼
Step5（最终映射）
```

**优势**：
- 保留并行度（Step4 与 Step2+Step3-Pass1 并行）
- Pass2 只处理不确定项，增量修正，token 消耗小
- 降级路径：Step4 不可用时跳过 Pass2
- "无文字引用图片"场景 → Pass2 能发现并补充

**劣势**：
- Step3 逻辑变复杂（两轮处理）
- 需要在 Step3 SKILL.md 中增加 Pass2 指令

---

## 四、推荐方案与理由

### 推荐：选项 B（Step4 前置到 Step3 之前）

**理由**：

1. **"无文字引用图片"是硬伤**：当前架构下 Step5 无法补救（Step5 被约束"不新增占位符"），这是唯一的永久性数据丢失场景。选项 B 可以根治。

2. **并行度并未实质降低**：
   - 当前：Step2+Step3 (串行) ∥ Step4 → 瓶颈是 T2+T3
   - 调整后：Step2 ∥ Step4 → Step3 → 瓶颈是 max(T2, T4) + T3
   - Step2 和 Step4 都是 AI 处理步骤，T2 ≈ T4，所以瓶颈时间基本相同

3. **降级路径等价**：当 Step4 `model_support_images: false` 时，Step3 自动退化为纯上下文判断，效果与当前完全一致。

4. **Step5 负担减轻**：图片合并、数量不匹配等场景在 Step3 阶段就解决了，Step5 收到的占位符和图片数量一致，匹配更简单。

5. **改动范围可控**：只需修改 2 个文件：
   - `master_exam_layout/SKILL.md`：调整调度顺序
   - `tag_placeholders/SKILL.md`：增加使用 image_descriptions 的指令

### 推荐的流水线架构

```
Step1 (clean_exam)        → content.md + images/
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   │
Step2 (tag_structure)   Step4 (tag_images)         │ 并行
     → structure.json   → image_descriptions.json  │
          │                   │                    │
          └───────────────────┘                    │
                    │                              │
                    ▼                              │
Step3 (tag_placeholders)                           │ 等 Step2+Step4
     → with_placeholders.json                      │
     （现在有图片描述辅助判断）                       │
                    │                              │
                    ▼                              │
Step5 (map_images)         → final_exam.json       │
                    │                              │
                    ▼                              │
Step6 (typeset_exam)       → final_exam.docx
```

---

## 五、具体改动清单

### 5.1 `master_exam_layout/SKILL.md`

**Step3 指令修改**：增加 `image_descriptions.json` 作为输入。

```diff
- 请严格按照 skills/tag_placeholders.md 执行图片占位标注任务。
- 输入: {工作目录}/中间数据/structure.json
+ 输入: {工作目录}/中间数据/structure.json, {工作目录}/中间数据/image_descriptions.json
```

**调度顺序修改**：
```
- Step2 → Step3（串行），Step4 与 Step2+Step3 并行
+ Step2 ∥ Step4（并行） → Step3（等待两者）
```

### 5.2 `tag_placeholders/SKILL.md`

**Input 部分**：增加 `image_descriptions.json`

**Task 部分**：在"第一步：掌握全局上下文"中增加：

```
**4. 查看 image_descriptions.json（如有）**

若 Step4 已完成且 `model_support_images` 为 `true`，读取图片描述信息以辅助判断：

- **图片合并检测**：若 `image_descriptions.json` 中某张图片的 `summary`/`clues` 包含多个子图描述（如"左图为等高线，右图为天气统计"），则该位置只需创建 1 个占位符，即使材料文字提到多个图号。
- **无文字引用图片发现**：对比 `image_manifest.json` 图片数量与通过文字触发创建的占位符数量，若图片多于已创建占位符，检查未匹配图片在 `content.md` 中的 `paragraph_index`，判断是否需要补充占位符。
- **图片数量不匹配**：若材料提到 N 张图但仅有 M 张（M < N），根据图片分析判断是合并还是缺失。

若 `model_support_images` 为 `false` 或文件不存在，跳过此步骤，使用纯上下文判断。
```

### 5.3 `tag_examples_choice.md`（已完成）

新增案例 3~8，覆盖图片相关边界场景。

### 5.4 `tag_examples_quick_ref.md`（已完成）

新增 6 条图片相关规则。

---

## 六、不改动的场景（确认当前处理正确）

以下场景当前已正确处理，无需调整：

| 场景 | 当前处理方式 | 正确性 |
|------|-------------|--------|
| 选项含图片 | Step3 优先级 5 + `location_type: "option"` | ✓ |
| 多图并排（材料后） | Step3 创建多个占位符 | ✓ |
| 表格在材料中 | Step2 segments 结构 | ✓ |
| 单题无题组 | Step2 单问 label 为空 | ✓ |
| 材料图片 vs 题目图片 | Step3 根据触发词位置判断 `location_type` | ✓（但有改进空间） |

---

## 七、总结

| 维度 | 结论 |
|------|------|
| **是否需要调整流水线？** | **是**。推荐将 Step4 前置到 Step3 之前 |
| **核心收益** | 根治"无文字引用图片"遗漏问题；减少占位符数量错误 |
| **并行度影响** | 几乎无影响（瓶颈不变） |
| **改动范围** | 2 个 SKILL.md 文件 + master_exam_layout 调度逻辑 |
| **降级安全** | 当 Step4 不可用时，Step3 自动回退到纯上下文判断 |
| **是否阻断当前开发** | 否。可在当前基础上增量修改 |
