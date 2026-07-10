# 打标规则速查表

> 供 `tag_structure` (Step2) 快速查阅。包含所有题型的通用高频判断规则。
> **始终加载**，帮助 AI 快速定位每条规则的归属字段。

---

## 位置标记约定

在案例原文中，使用以下标记指示图片/表格位置：

| 标记 | 含义 | Step3/排版中的处理 |
|------|------|-------------------|
| `【图片位置】` | 此处应插入一张图片 | 创建 1 个占位符（`{{image:ph_xxx}}`），排版时替换为实际图片 |
| `【图片位置】【图片位置】` | 此处应插入多张图片（并排） | 创建 N 个占位符，排版时并排放置 |
| `【表格位置】` | 此处应插入一张表格 | 使用 `material.segments` 结构（Step2 负责） |

> **重要**：`【图片位置】` 标记在 `content.md` 中不会出现（那是原始文档中的图片位置，由 `{{image:img_xxx}}` 表示），在案例原文中标注是为了帮助 AI 理解图片应该出现在什么位置。

---

## 高频判断规则速查

| 场景 | 判断规则 | 归属 |
|------|----------|------|
| "据此完成X~Y题" | 引导语，非材料正文 | `guide_sentence` |
| "阅读图文材料" | 非选择题标准引导语 | `stem` |
| "下图示意..." | 材料正文的一部分 | `content` |
| ①②③④在选择题下方 | 子选项 | `sub_options` |
| ①②③在非选择题子问题中 | 拆分为独立子问题 | `subquestions`，`label` = "(N)-①" |
| 只有一个子问题 | `label` 为空字符串 | `""` |
| "材料一：""材料二：" | 保留在 `content` 中 | `material.content` |
| 注意事项条目 | `content` 不含序号，序号在 `number` 字段 | `notes_items` |
| 引导语与标题同段 | 合并到 `title` | `instructions` 为空 |
| 引导语单独成段 | 写入 `instructions` | `instructions` = ["引导语"] |
| 表格在材料中 | 使用 `segments` 数组，`type: "table"` | `material.segments` |
| 材料含"材料一/二"标记 | 按标记拆分为多个 `material` 对象 | `materials[]` |
| 选择题组共享材料 | 材料放在第一题的 `materials` 中 | 第一题的 `materials` |
| 选择题子选项（①②③④） | 从 `stem` 中移除，提取到 `sub_options` | `sub_options` |
| 非选择题子问题含①②③ | 按序号拆分为独立子问题，`label` = "(N)-①" | `subquestions` |
| "（如下图）"在材料正文中 | 保留在 `content` 中，提示图片插入位置 | `material.content` |
| 材料引用"图X""图Y"多张图 | 创建多个占位符，需图片分析确认是否合并 | Step3 占位符 |
| 题干无"如图"但有图片 | 依赖 `content.md` 中 `{{image}}` 标记判断归属 | Step3 占位符 |
| 题目引用材料级图片 | 不重复创建占位符，只在材料节点创建 | Step3 占位符 |
| 选项含图片（A/B/C/D为图） | `location_type: "option"`，每个选项独立占位符 | Step3 占位符 |
| 材料提及图片数与实际不符 | `uncertain: true`，记录到 warnings，依赖图片分析 | Step3/5 |
| 材料与子问题交错排列 | 为 material + subquestion 赋值共享 `order` 字段，按原文顺序编号 | Step2 |
| 子问题含专属表格/材料 | 放入 `subquestions[].materials[]`，非父问题 materials | Step2 |
| 非标准材料标题（【xxx】） | 识别为材料段落开头，保留在 `content` 中 | Step2 |
| 无标记材料段落边界 | 按"子问题位置"+"话题突变"判断材料拆分点 | Step2 |
| 子问题含填空空位（____） | 设置 `sub_question_type`：`fill_in_blank` / `mixed` / `essay` | Step2 |
| 材料中【图片位置】标记 | 图片插入到材料段落后、题目之前 | Step3 占位符位置 |
| 题干中【图片位置】标记 | 图片插入到题干后、选项之前 | Step3 占位符位置 |
| 子问题中【图片位置】标记 | 图片插入到该子问题题干后 | Step3 占位符位置 |
| 选项含【图片位置】标记 | 图片替代选项文字（如A/B/C/D为图） | Step3 占位符位置 |
| 材料中【表格位置】标记 | 表格插入到提示文字后，使用 segments 结构 | Step2 表格 segments |
