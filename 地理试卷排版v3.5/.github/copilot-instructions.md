# 地理试卷排版系统 Copilot 指令

> 完整规则见 AGENTS.md，本文件为精简版。

## 项目概述

地理试卷排版系统 v3.6，六步解耦流水线，将 .docx 试卷转为排版精美 Word 文档。
核心策略：代码 + AI 双轨。代码处理确定性逻辑（inline 图），AI 仅介入不确定性场景（anchor 图）。

## 技术栈

- Python 3.10+，python-docx，lxml
- JSON Schema：`schemas/exam_paper.schema.json`
- 样式模板：`assets/template.dotx`

## 严格禁止

1. 禁止在工作目录创建 .py 文件 — 所有脚本在 `scripts/` 中
2. 禁止绕过合规检查 — Step2/3/5 后必须运行 `check_compliance.py`
3. 禁止自行编写排版脚本 — Step6 必须调用 `scripts/typeset_exam.py`
4. 禁止修改 `scripts/` 下的任何现有脚本
5. 禁止为 inline 图创建占位符 — `{{image:img_xxx}}` 已由代码生成
6. 禁止全量重写大型 JSON — Step3 用 Edit 增量修改，Step5 AI 只输出 delta

## 流水线

1. `clean_exam` → 清洗产物/（脚本）
2. `tag_structure` → structure.json（AI）
3. `tag_placeholders_anchor` → with_placeholders.json（AI，增量编辑）
4. `tag_images_anchor` → anchor_descriptions.json（AI，可与 Step2 并行）
5. `map_images` → final_exam.json（脚本优先 + AI 兜底）
6. `typeset_exam` → 排版后 .docx（脚本）

Step3/4 跳过条件：`image_manifest.json` 中 `anchor_count == 0` 时跳过。

## 关键命令

```bash
python scripts/clean_docx.py --input <in.docx> --output <out.docx>
python scripts/extract_images.py --input <in.docx> --output <out.docx>
python scripts/validate_json.py --schema schemas/exam_paper.schema.json --json <t.json>
python scripts/check_compliance.py --work-dir <dir> --step <n> --json <t.json>
python scripts/map_images.py --placeholders <s.json> --images-manifest <m.json> --output <f.json>
python scripts/typeset_exam.py --json <f.json> --template assets/template.dotx --images <dir> --output <out.docx>
```

## Token 优化

- Step3：增量编辑（先 copy 再 Edit），禁止 Write 全量输出，节省 ~94% token
- Step5：脚本优先（map_images.py 零 token），AI 仅处理未映射项
- Step5c：Delta 输出，AI 只输出 image_mapping_overrides.json（~10-30 行）

## 图片处理

- inline 图：`paragraph_index` 可靠，代码直接映射
- anchor 图：`paragraph_index` 不可靠，需 AI 判断位置
- 符号小图（< 2KB）：标记 `{{symbol:img_xxx}}`，不做映射
- 图片尺寸：基准 = 原卷 extent 真值；原宽 < 6cm 才放大到 12cm
- 一行多图：用 `paragraph_index` 判断同段落，横排嵌入
