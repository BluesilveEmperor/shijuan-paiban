# 异常处理手册 (error_cases.md)

> 地理试卷排版 v3.0 — 覆盖六步流水线中 12 类预定义异常。
> 每类异常含：现象、可能原因、影响步骤、处理步骤、是否允许 `uncertain`。

---

## 概览

| 编号 | 异常名称 | 触发步骤 | 是否允许 uncertain | 严重程度 |
|------|----------|----------|-------------------|----------|
| E1 | 题号丢失或乱序 | Step2 | 是 | 中 |
| E2 | OCR 选项与题干粘连 | Step2 | 是 | 中 |
| E3 | 多栏文本串行化 | Step1/Step2 | 是 | 中 |
| E4 | 图文分离导致上下文错位 | Step5 | 是 | 高 |
| E5 | 表格被拆成纯文本 | Step2 | 是 | 中 |
| E6 | 一张图对应多个小问 | Step5 | 否（需明确） | 低 |
| E7 | 图片文件名顺序与正文不一致 | Step5 | 否 | 低 |
| E8 | 无图片但正文提到"如图所示" | Step3/Step5 | 是 | 高 |
| E9 | WMF/EMF 矢量图文本提取失败 | Step1 | 是 | 中 |
| E10 | 图片映射置信度过低 | Step5 | 是 | 中 |
| E11 | final_exam.json Schema 校验失败 | Step5/Step6 | 否 | 高 |
| E12 | 排版后图片缺失或错位 | Step6 | 否 | 高 |

---

## E1: 题号丢失或乱序

### 现象
- `structure.json` 中出现题号跳变（如 1, 2, 4, 5 缺少题 3）
- 题号不连续或重复
- 某道题的 `stem` 为空或仅含少量无意义字符

### 可能原因
1. OCR 识别时将题号与前一题内容合并
2. 原始试卷中某道题被删除或遮蔽
3. 清洗脚本 `clean_docx.py` 误删包含题号的段落（如规则 1.17 删除考试名称前图片时误伤题号行）
4. `content.md` 中题号被 `{{image:img_xxx}}` 或 `{{symbol:img_xxx}}` 标记截断

### 影响步骤
- **Step2 tag_structure**：无法准确识别该题及其后所有题目的结构

### 处理步骤
1. 在 `notes` 字段记录跳号位置和可能原因
2. 将该位置前后题目标记 `uncertain: true`
3. 无法匹配的文本块归入 `unclassified_blocks`，`reason` 设为 `"题号丢失或乱序"`
4. 人工检查原始 docx 中对应题号是否确实存在

### 是否允许 uncertain
**是**。题号识别不确定时标记 `uncertain: true`。

---

## E2: OCR 选项与题干粘连

### 现象
- 选择题的 `stem` 字段中包含选项文字（如 `"题干内容A.选项内容B.选项内容C.选项内容"`）
- 选项数组为空或仅部分识别
- 题干末尾没有自然断句，直接与选项标签连在一起

### 可能原因
1. `content.md` 中选项段落与题干段落被合并（换行符丢失）
2. 原始 docx 中题干的段落结束符为软回车（`<w:br/>`）而非段落分隔
3. OCR 将选项前的空格/换行吞掉

### 影响步骤
- **Step2 tag_structure**：无法分离题干和选项，导致 `options` 数组不完整

### 处理步骤
1. 将整题标记 `uncertain: true`
2. 在 `notes` 中记录 `"题干与选项粘连，无法确定分界点"`
3. 若粘连文本可部分拆分（如通过 `A.` `B.` 定位），则拆分并标注不确定
4. 无法拆分的文本放入题目 `stem` 字段，并在 `notes` 中说明含选项文字
5. Step6 排版时尝试按 `A. ` / `B. ` 模式二次拆分

### 是否允许 uncertain
**是**。

---

## E3: 多栏文本串行化

### 现象
- 原始试卷存在左右两栏或三栏布局（如选做题、分栏材料）
- `content.md` 中出现文本顺序混乱：左栏第 1 题 → 右栏第 1 题 → 左栏第 2 题（交叉串行）
- 上下文逻辑断裂，题组关联错误

### 可能原因
1. 原始试卷使用了 Word 分栏（`<w:cols>`）或多列文本框布局
2. `clean_docx.py` 按 XML 物理顺序读取，未考虑分栏逻辑顺序
3. 不同列中的段落交替排列

### 影响步骤
- **Step1 clean_exam**：`content.md` 顺序可能与阅读顺序不一致
- **Step2 tag_structure**：题目识别和题组关联错误

### 处理步骤
1. Step1 清洗时检测 `cleaned_no_images.docx` 中是否含 `<w:cols>` 元素
2. 若有分栏标记，在 `clean_log.txt` 中记录警告
3. Step2 打标时若发现上下文不连贯，标记相关整题 `uncertain: true`
4. 在 `notes` 中记录 `"疑似多栏文本串行化，题目顺序可能不准确"`
5. 尽可能按题号排序恢复部分顺序

### 是否允许 uncertain
**是**。

---

## E4: 图文分离导致上下文错位

### 现象
- 占位符的 `context_before`/`context_after` 与图片描述不匹配
- Step5 映射时出现高置信度错误映射（如"等高线图"映射到"产业价值链"）
- 最终排版中图片出现在无关联的题目中

### 可能原因
1. 原始 docx 中图片与文字使用绝对定位锚定（非嵌入式），提取位置信息丢失
2. `image_manifest.json` 中的 `paragraph_index` 对应的是段落序号而非逻辑位置
3. 多张图片集中在同一位置，上下文窗口重叠

### 影响步骤
- **Step5 map_images**：映射错误
- **Step6 typeset_exam**：图片出现在错误位置

### 处理步骤
1. Step5 映射时将 confidence < 0.5 的匹配降为 unmapped
2. 在 `validation.warnings` 中记录 `"图片 xxx 上下文匹配度低，映射可能不准确"`
3. 若 `image_descriptions.json` 中图片有 `clues` 字段，优先用线索匹配题目
4. 无法确定映射时宁可进入 `unmapped_placeholders`，不强行配对

### 是否允许 uncertain
**是**。Step5 中对低置信度映射降低 confidence 值。

---

## E5: 表格被拆成纯文本

### 现象
- 原始试卷中有表格（如数据表格、选项表格），但 `content.md` 中表格变为逐行文本
- 表格单元格内容按行排列，失去行列结构
- `structure.json` 中无法识别为表格

### 可能原因
1. `clean_docx.py` 的 `docx_to_markdown()` 只处理段落，未解析 `<w:tbl>` 元素
2. 表格被 `clean_docx.py` 中的规则误触发删除

### 影响步骤
- **Step2 tag_structure**：表格内容被当作普通文本，归入 unclassified_blocks 或混入题干
- **Step6 typeset_exam**：无法重建表格

### 处理步骤
1. Step2 检测到连续多行短文本且对齐排列时，标记为疑似表格
2. 将疑似表格的文本块归入 `unclassified_blocks`，`reason` 设为 `"表格被拆成纯文本"`
3. 在 `notes` 中记录行数和列数猜测
4. Step6 排版时，若 unclassified_blocks 中有表格标记，尝试调用 `add_table()` 重建

### 是否允许 uncertain
**是**。

---

## E6: 一张图对应多个小问

### 现象
- 同一张地图/图表被多道选择题或非选择题的多个小问引用
- 占位符指向同一张图片
- 例如：第 1-3 题共用"某区域等高线地形图"

### 可能原因
1. 地理试卷常见模式：一组题共享一幅图
2. Step3 可能在每题都创建了占位符（而非只在第一题创建）

### 影响步骤
- **Step3 tag_placeholders**：可能产生冗余占位符
- **Step5 map_images**：需要处理一张图对多个占位符的映射

### 处理步骤
1. Step5 映射时允许一张图片映射到多个占位符
2. 在 `image_mapping` 的 `reason` 中注明 `"图片复用：第X-Y题共用此图"`
3. **不标记为 uncertain**：这是正常的地理科考试设计模式
4. Step6 排版时，对复用图片仅插入一次（出现在第一引用处），后续引用添加 "(见上图)" 标注

### 是否允许 uncertain
**否**。需要明确识别共用关系。

---

## E7: 图片文件名顺序与正文顺序不一致

### 现象
- `images/` 目录下的 `img_001.png`、`img_002.png` 的文件名序号与正文中出现顺序不匹配
- 按文件名排序的图片列表与按阅读顺序的图片出现顺序不同

### 可能原因
1. `extract_images.py` 按 docx 内部 media 文件的存储顺序编号，而非文档出现顺序
2. Word 插入图片的顺序与存储编号无直接关系

### 影响步骤
- **Step5 map_images**：不应依赖文件名顺序做匹配

### 处理步骤
1. Step5 **不依赖文件名序号**做匹配决策
2. 优先使用 `content.md` 中 `{{image:img_xxx}}` 标记的出现顺序
3. 备选方案：`image_manifest.json` 中的 `paragraph_index`（段落出现顺序）
4. **不标记为 uncertain**：这是设计准则，不是异常

### 是否允许 uncertain
**否**。Step5 的匹配规则已明确排除文件名依赖。

---

## E8: 无图片但正文提到"如图所示"

### 现象
- 题干字符串含"如图"/"图X所示"，但 `image_manifest.json` 中无可匹配的图片
- Step5 无法为该占位符找到映射

### 可能原因
1. 图片在清洗阶段被误删（如 `clean_docx.py` 将小图判定为符号）
2. 原始文件中图片损坏或无法提取
3. 引用的图片在另一份文件中（如试题与图册分离的试卷）

### 影响步骤
- **Step3 tag_placeholders**：创建了占位符
- **Step5 map_images**：无法匹配，该占位符进入 `unmapped_placeholders`
- **Step6 typeset_exam**：该位置出现 `[图片缺失: xxx]` 占位文字

### 处理步骤
1. Step3 检测到"如图"且无可匹配图片时，`reason` 中注明 `"正文提到'如图'但未见对应图片"`
2. Step5 该占位符进入 `unmapped_placeholders`
3. `validation.warnings` 中记录：`"ph_xxx: 正文提到'如图'但未找到对应图片"`
4. Step6 排版时在对应位置显示 `[图片缺失]` 标记

### 是否允许 uncertain
**是**。

---

## E9: WMF/EMF 矢量图文本提取失败

### 现象
- `symbols_report.md` 中列出未解析的 WMF/EMF 小图片
- `content.md` 中对应位置有 `{{symbol:img_xxx}}` 标记
- 正文中有明显缺字（如 `"地"` 后面少了一个字，或 `"29 52'S"` 缺少 `°`）

### 可能原因
1. WMF 文件中不含 EXTTEXTOUT 记录或 MathML（使用了位图方式存储文字）
2. 图片内文字使用了自定义字体编码，无法用 GBK 解码
3. 图片是纯线条/图形，不含文字

### 影响步骤
- **Step1 clean_exam**：`check_pending_symbols()` 报告警告
- **Step2 tag_structure**：需要推断缺失的符号内容

### 处理步骤
1. Step1 不硬猜，仅生成 `symbols_report.md` 供 Step2 参考
2. Step2 根据上下文推断符号内容：
   - 数字 + 数字之间 → 经纬度符号（`°`、`′`、`″`）
   - 元素符号 + 数字 → 化学式下标
   - 选项字母后 → 选项点号（`.`）
3. 推断成功：替换 `{{symbol:img_xxx}}` 为推断符号，`notes` 记录
4. 推断失败：保留原样，标记整题 `uncertain: true`
5. 人工确认 `symbols_report.md` 后修正

### 是否允许 uncertain
**是**。

---

## E10: 图片映射置信度过低

### 现象
- Step5 中多条 `image_mapping` 的 `confidence` 低于 0.5
- 占位符上下文关键词与所有图片的 keywords/summary 均无明显匹配

### 可能原因
1. 图片描述信息不足（`image_descriptions.json` 中 `keywords` 为空或过于泛化）
2. 多张图片主题相似（如都是"等高线图"），无法区分
3. 占位符的 `context_before`/`context_after` 太短

### 影响步骤
- **Step5 map_images**：映射不确定

### 处理步骤
1. `confidence < 0.5` 的配对不进 `image_mapping`，进入 `unmapped_placeholders`
2. `confidence 0.5-0.7` 的配对进 `image_mapping`，但在 `reason` 中注明 `"低置信度匹配"`
3. 回退使用 `paragraph_index` 顺序匹配
4. 在 `validation.warnings` 中列出所有低置信度映射

### 是否允许 uncertain
**是**。

---

## E11: final_exam.json Schema 校验失败

### 现象
- `validate_json.py` 对 `final_exam.json` 报告校验错误
- 错误可能来自：缺少必填字段、ID 格式不匹配、枚举值超出范围

### 可能原因
1. Step5 map_images 在填充 `image_mapping` 时未完全遵循 Schema
2. Step2/Step3 产出的 JSON 未通过校验就被 Step5 使用
3. `images` 数组未从 `image_descriptions.json` 完整复制

### 影响步骤
- **Step5 map_images**：产物不可用
- **Step6 typeset_exam**：无法执行

### 处理步骤
1. 读取所有校验错误详情
2. 定位到具体字段和步骤
3. 若为 Step5 自身错误（如 image_mapping 字段缺失），修正后重新输出
4. 若为上一步骤错误（如 structure 中 id 格式不对），回退到对应步骤修正
5. **绝不允许忽略 Schema 校验进入 Step6**

### 是否允许 uncertain
**否**。Schema 校验是强制性的，校验失败必须修正。

---

## E12: 排版后图片缺失或错位

### 现象
- Step6 排版的 `final_exam.docx` 中出现 `[图片缺失: xxx]` 文字
- `quality_report.html` 中 `missing_images` 数组非空
- 图片存在但出现在错误的题目中

### 可能原因
1. `image_mapping` 中引用的 `file_name` 与实际文件不匹配
2. `ImageResolver` 解析路径拼接错误
3. `images/` 目录中文件被移动或删除

### 影响步骤
- **Step6 typeset_exam**：排版结果不完整
- 最终交付物质量不达标

### 处理步骤
1. 检查 `typeset_log.txt` 中的 WARNING 级别日志
2. 核实 `image_mapping` → `images` → `file_name` 三层引用链完整
3. 用 `quality_report.html` 的 `missing_images` 列表逐张排查
4. 确认 `images/` 目录路径正确且文件存在
5. 修正后重新执行 Step6（无需重跑 Step1-5）

### 是否允许 uncertain
**否**。排版是最终输出，图片缺失不可接受。

---

## 附录 A：异常汇总检查清单

在处理任一份试卷时，应逐项确认：

- [ ] E1 题号丢失或乱序 → 检查 `structure.json` 中 question.number 连续性
- [ ] E2 选项粘连 → 检查选择题 options 数组完整且 stem 不含选项文字
- [ ] E3 多栏串行 → 检查 content.md 上下文连贯性
- [ ] E4 图文错位 → 检查 image_mapping 中高置信度映射的语义匹配
- [ ] E5 表格被拆 → 检查 unclassified_blocks 中是否有表格标记
- [ ] E6 图片复用 → 检查是否有多个占位符映射到同一 image_id
- [ ] E7 文件顺序 → 提醒 Step5 不依赖文件名序号
- [ ] E8 无图但有"如图" → 检查 unmapped_placeholders 和 validation.warnings
- [ ] E9 WMF 提取失败 → 检查 symbols_report.md
- [ ] E10 低置信度 → 检查 image_mapping 中 confidence < 0.5 的条目
- [ ] E11 Schema 校验 → 每步产物必须通过 validate_json.py
- [ ] E12 图片缺失 → 检查 quality_report.html 的 missing_images

## 附录 B：紧急恢复流程图

```
发生异常
  │
  ├─ Step1 失败 → 检查原始 docx 完整性 → 重新清洗
  ├─ Step2 失败 → 检查 content.md → 重新打标
  ├─ Step3 失败 → 检查 structure.json → 重新占位
  ├─ Step4 失败 → 检查 images/ → 重新理解
  ├─ Step5 失败 → 检查 Step3+Step4 产物 → 重新映射
  ├─ Step6 失败 → 检查 final_exam.json + template.dotx → 重新排版
  │
  └─ 任何步骤 → 记录 error_cases.md 对应编号 → 执行处理步骤 → 重跑该步骤
```
