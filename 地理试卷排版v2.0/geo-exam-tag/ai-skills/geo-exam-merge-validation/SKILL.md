---
name: geo-exam-merge-validation
description: "地理试卷打标融合验证skill。AI对比tagged_script.json和tagged_ai.json，融合结果，验证输出正确性，标记最终置信度。geo-exam-ai-tagging和tag_docx.py都执行完毕后自动触发。AI主导验证和决策，不依赖代码。"
---

# 地理试卷打标融合验证 Skill

## 触发时机（必须明确）

**自动触发条件**：
1. geo-exam-ai-tagging skill执行完毕
2. tagged_script.py脚本执行完毕（tagged_script.json已生成）
3. tagged_ai.json和tagged_script.json都存在

**手动触发条件**：
- 用户明确要求"验证打标结果"
- 用户提到"融合结果"、"对比JSON"

**触发检查**：
- AI必须先检查tagged_ai.json是否存在
- 检查tagged_script.json是否存在
- 如果不满足，提示用户先运行前序步骤

---

## 输入

**必需输入**：
- `tagged_script.json`：脚本打标结果
- `tagged_ai.json`：AI打标结果

**可选输入**：
- `references/json_schema.json`：JSON Schema定义
- `references/validation_rules.md`：验证规则

**输入位置**：
- 文件位于output目录下

---

## 输出

**输出文件**：
- `tagged_final.json`：融合后的最终结果
- `validation_report.json`：验证报告

**输出位置**：
- 与前序JSON同目录

---

## AI任务流程

### 第一步：检查触发条件

AI首先检查触发条件是否满足：
```
检查步骤：
1. 确认tagged_ai.json存在
2. 确认tagged_script.json存在
3. 如果不满足，提示用户先运行前序步骤
```

### 第二步：格式验证

AI验证两个JSON的格式正确性：

**必需字段检查**：
- exam_info字段是否存在
- sections字段是否存在
- section_id、section_type、question_groups是否完整

**结构完整性检查**：
- sections是否是数组
- question_groups是否是数组
- questions是否是数组

**字段类型检查**：
- 题号是否是数字
- 选项是否是对象（包含ABCD）

### 第三步：逻辑验证

AI验证JSON的逻辑合理性：

**题号连续性检查**：
- 检查题号是否重复
- 检查题号是否跳跃过大

**选项完整性检查**：
- 选择题是否包含ABCD四个选项
- 选项内容是否为空

**题组归属检查**：
- 检查group_id是否合理
- 检查题组范围是否合理

**图片引用检查**：
- 图片引用是否与images文件夹对应

### 第四步：结果对比

AI对比两个JSON的差异：
- 考试信息是否一致
- 分区数量是否一致
- 题组数量是否一致
- 题目数量是否一致
- 图片位置是否一致

### 第五步：结果融合

AI根据验证结果融合两个JSON：

**融合策略**：
- **格式都正确且一致**：优先采用AI结果
- **格式都正确但不一致**：标记差异
- **脚本失败、AI成功**：使用AI结果
- **AI失败、脚本成功**：使用脚本结果
- **都失败**：输出空JSON

### 第六步：标记置信度

AI根据验证结果标记最终置信度：
- **high**：双轨都通过验证且一致
- **medium**：单轨通过验证
- **low**：仅逻辑验证通过
- **failed**：验证失败

### 第七步：输出最终JSON和验证报告

AI输出tagged_final.json和validation_report.json。

---

## 参考文档

详见：
- `references/validation_rules.md`：验证规则详细说明
- `references/json_schema.json`：JSON Schema定义

---

## AI能力要求

- **JSON理解**：理解JSON结构和内容
- **对比分析**：对比两个JSON的差异
- **验证判断**：判断JSON正确性
- **决策能力**：选择融合策略

---

## 注意事项

1. **优先AI结果**：
   - AI理解更准确，优先采用AI结果
   - 脚本结果作为参考和验证

2. **差异标记**：
   - 如果两个JSON不一致，在最终JSON中记录差异
   - 不隐藏不一致信息

3. **置信度合理**：
   - 不盲目标记high置信度
   - 根据实际验证结果判定

4. **脚本使用约束（强制）**：**AI不得自行编写任何脚本**。本skill为纯AI操作skill，AI应通过自身能力完成JSON对比验证和融合，**绝不编写Python脚本或其他代码脚本**来辅助处理。

---

## 与后续skill的衔接

本skill输出的tagged_final.json将作为排版阶段（geo-exam-format）的输入。
validation_report.json将作为质检报告的参考信息。