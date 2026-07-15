## 🤖 Assistant

下面这段可以直接发给 Trae / Codex / Cursor 等 AI 编程工具，让它根据说明修改项目代码与 `图片处理.md`。

---

# 任务：修改 Word 图片提取与 Markdown 占位符生成逻辑

## 背景

当前项目在处理 docx 试卷时，存在图片占位符和文字粘连的问题。

典型错误输出：

```markdown
{{image:img_002}}11.大蒜交易市场...
```

期望输出：

```markdown
{{image:img_002}}

11.大蒜交易市场...
```

根因是：

docx 中很多图片虽然在 Word 视觉上独占一行，但 XML 结构上只是同一个段落 `<w:p>` 内的一个 run `<w:r>`。当前流程在 `extract_images.py` 中删除图片 run 后，再由 `docx_to_markdown()` 按段落补图片占位符，导致丢失 run 级别顺序和图片/文本的真实相对位置。

另外，试卷中还有大量几百 B 的小图片，本质是标点、汉字或符号，例如：

```text
.
。
的
是
```

这些小图不能按题图处理，不能独占一行，也不能参与 AI 图片映射。

---

# 修改目标

请修改图片处理流程，使其满足以下目标：

1. 图片占位符插入必须基于段落内部 run 顺序，而不是只基于 paragraph_index。
2. 根据图片文件大小区分“符号小图”和“内容图片”。
3. `file_size < 2KB` 的图片视为 `symbol`，行内输出，不换行。
4. `file_size >= 2KB` 且原始类型为 `inline` 的图片视为普通内容图片，输出 `{{image:img_xxx}}`，默认块级显示，前后加换行。
5. `file_size >= 2KB` 且原始类型为 `anchor` 的图片视为浮动内容图片，不在 Markdown 原位置插入，后续交给 AI/映射逻辑处理。
6. `<w:br/>` 必须转换为 Markdown 换行。
7. 禁止对 `file_size < 2KB` 的图片应用“后面是题号就断行”的规则。
8. `symbol` 图片不参与 `map_images.py` 的题图映射。
9. 更新 `图片处理.md`，说明新的处理规则。

---

# 核心分类规则

新增或统一使用字段：

```json
"image_class": "symbol" | "image" | "anchor_image"
```

分类逻辑如下：

```text
if file_size < 2KB:
    image_class = "symbol"

else if original_type == "anchor":
    image_class = "anchor_image"

else:
    image_class = "image"
```

更具体：

```text
file_size < 2048:
    symbol，小符号/文字图片，行内处理

file_size >= 2048 且 original_type = inline:
    image，普通内容图片，块级处理

file_size >= 2048 且 original_type = anchor:
    anchor_image，浮动内容图片，不在 Markdown 原位置插入，交由 AI 处理

file_size >= 2048 且 original_type = vml/unknown:
    image 或 unknown，可先按 image 处理，必要时保留 warning
```

---

# 一、修改 clean_docx.py

## 1. 保留原始图片类型记录

确保在任何 anchor 转 inline 操作之前，先记录图片原始类型。

已有逻辑如果存在：

```python
record_original_image_types()
```

请确认它在：

```python
rule_1_19_convert_floating_images()
```

之前执行。

输出 `_original_image_types.json`，格式类似：

```json
{
  "rId7": "inline",
  "rId8": "anchor",
  "rId9": "vml"
}
```

## 2. anchor 转 inline 后必须保留 original_type

即使后续为了统一处理，把 `<wp:anchor>` 转成 `<wp:inline>`，也不能丢失图片原始类型。

后续 `image_manifest.json` 中必须有：

```json
"original_type": "anchor"
```

而不是只记录清洗后的 inline。

## 3. 小于 2KB 的 WMF/EMF/VML 图片优先作为符号/文字图片

对于：

```text
file_size < 2048
```

的图片，优先按符号/文字图处理：

1. 尝试 WMF/EMF 文本提取；
2. 尝试上下文推断；
3. 成功则替换为真实文本；
4. 失败则后续标记为 `symbol`，不要作为题图处理。

---

# 二、修改 extract_images.py

## 1. image_manifest.json 必须增加 image_class 字段

提取每张图片时，记录：

```json
{
  "image_id": "img_001",
  "image_file": "img_001.png",
  "relationship_id": "rId7",
  "file_size": 823,
  "file_ext": ".wmf",
  "original_type": "inline",
  "image_type": "inline",
  "image_class": "symbol",
  "paragraph_index": 12,
  "run_index": 3,
  "context_before": "这是",
  "context_after": "正确的。"
}
```

## 2. 分类函数

请增加统一分类函数，例如：

```python
def classify_image(file_size, original_type):
    if file_size < 2048:
        return "symbol"

    if original_type == "anchor":
        return "anchor_image"

    return "image"
```

如果已有分类逻辑，请替换或统一到这个规则。

## 3. 必须记录 run_index

当前只记录 `paragraph_index` 不够。

请确保每张图片记录：

```json
"paragraph_index": 12,
"run_index": 3
```

后续 Markdown 插入必须依赖 run 顺序。

## 4. 删除图片前，先完整记录位置信息

如果 `extract_images.py` 会删除图片 run，请确保删除前已经写入：

```text
image_id
relationship_id
paragraph_index
run_index
file_size
original_type
image_class
context_before
context_after
```

## 5. 建议保留 run 级别定位映射

可以在内部构建：

```python
images_by_position = {
    (paragraph_index, run_index): image_manifest_item
}
```

供 `docx_to_markdown()` 使用。

如果 `docx_to_markdown()` 无法访问已删除图片 run，请考虑以下两种方案之一：

### 方案 A，推荐

在删除图片前，生成一个 run 级别的占位符信息，并写入 manifest。`docx_to_markdown()` 读取 manifest 后，根据 `paragraph_index + run_index` 恢复占位符。

### 方案 B，更推荐但改动稍大

不要让 `docx_to_markdown()` 基于 `cleaned_no_images.docx` 恢复图片位置，而是让它读取含图片的 `cleaned.docx`，按 run 顺序直接生成 token，同时提取/引用 manifest 中的图片信息。

如无法大改，先采用方案 A。

---

# 三、修改 utils.py::docx_to_markdown()

这是最重要的修改点。

## 1. 不要再只按 paragraph_index 插入图片

当前逻辑如果类似：

```text
处理一个段落文本
再检查该段落是否有图片
然后把图片占位符插到段落前或段落后
```

请改掉。

必须改成：

```text
按段落内部 run 顺序处理。
```

也就是：

```text
遍历 paragraph
    遍历 run
        如果当前位置有图片
            输出图片占位符
        如果 run 有文字
            输出文字
        如果 run 有 <w:br/>
            输出换行
```

## 2. 按 image_class 输出不同占位符

规则如下：

### image_class = symbol

输出：

```markdown
{{symbol:img_xxx}}
```

特点：

```text
行内输出；
不加换行；
不独占一行；
不因后面是题号而断行。
```

示例：

```markdown
这是{{symbol:img_003}}正确的。
```

### image_class = image

输出：

```markdown
{{image:img_xxx}}
```

并作为块级图片处理。

块级输出规则：

```text
如果当前行已有文字，先补一个换行；
输出 {{image:img_xxx}}；
图片后补两个换行；
后续文字另起一行。
```

期望：

```markdown
{{image:img_002}}

11.大蒜交易市场...
```

不要输出成：

```markdown
{{image:img_002}}11.大蒜交易市场...
```

### image_class = anchor_image

不在 Markdown 原位置插入。

处理方式：

```text
跳过；
保留给后续 AI 生成 anchor 占位符。
```

## 3. 必须处理 `<w:br/>`

如果 run 中存在：

```xml
<w:br/>
```

Markdown 中必须输出换行。

例如：

```xml
图片 + <w:br/> + 文字
```

应输出：

```markdown
{{image:img_001}}

文字
```

至少不能粘连成：

```markdown
{{image:img_001}}文字
```

## 4. 示例伪代码

请按项目实际 XML 解析方式调整：

```python
def render_image_placeholder(item, current_text_buffer):
    image_id = item["image_id"]
    image_class = item.get("image_class")

    if image_class == "symbol":
        return f"{{{{symbol:{image_id}}}}}"

    if image_class == "image":
        return f"\n{{{{image:{image_id}}}}}\n\n"

    if image_class == "anchor_image":
        return ""

    return f"\n{{{{image:{image_id}}}}}\n\n"
```

处理段落时：

```python
for paragraph_index, paragraph in enumerate(paragraphs):
    paragraph_md = []

    for run_index, run in enumerate(paragraph.runs):
        image_item = images_by_position.get((paragraph_index, run_index))

        if image_item:
            if image_item["image_class"] == "symbol":
                paragraph_md.append(f"{{{{symbol:{image_item['image_id']}}}}}")
            elif image_item["image_class"] == "image":
                # 块级图片，保证前后换行
                if paragraph_md and not "".join(paragraph_md).endswith("\n"):
                    paragraph_md.append("\n")
                paragraph_md.append(f"{{{{image:{image_item['image_id']}}}}}\n\n")
            elif image_item["image_class"] == "anchor_image":
                pass

        # 处理 run 内文字
        text = extract_text_from_run(run)
        if text:
            paragraph_md.append(text)

        # 处理 w:br
        if run_has_break(run):
            paragraph_md.append("\n")

    md_parts.append("".join(paragraph_md).strip())
```

注意：如果当前代码使用 `python-docx` 取 run，可能需要通过 run 的底层 XML `_element` 检测 `<w:br/>` 和图片。

---

# 四、修改 map_images.py

## 1. symbol 图片不参与题图映射

在图片映射阶段，过滤掉：

```json
"image_class": "symbol"
```

这类图片不应该参与：

```text
inline Track 1 映射
anchor Track 2 AI 映射
```

它们只是行内符号或文字残留。

## 2. inline 内容图片走 Track 1

条件：

```text
image_class = image
original_type = inline
```

处理：

```text
placeholder_id = image_id
image_id = image_id
track = code
confidence = 0.95
```

## 3. anchor 内容图片走 Track 2

条件：

```text
image_class = anchor_image
original_type = anchor
```

处理：

```text
由 AI/规则生成的 ph_anchor_xxx 占位符进行匹配。
```

## 4. 不要用 file_size < 2KB 的图片进行 AI 匹配

如果当前逻辑中有：

```text
anchor 图片全部进入 AI 匹配
```

请修改为：

```text
只有 image_class = anchor_image 的图片进入 AI 匹配。
```

---

# 五、修改 typeset_exam.py

如果当前排版只识别：

```markdown
{{image:img_xxx}}
```

请确认是否需要处理：

```markdown
{{symbol:img_xxx}}
```

处理建议：

1. `{{image:img_xxx}}`：按现有图片插入逻辑，居中或按题图规则插入；
2. `{{symbol:img_xxx}}`：不要作为块级图片插入；
3. 如果支持行内小图片，可以行内插入；
4. 如果当前不支持行内小图片，可先保留占位符文本，或在前置阶段尽量 OCR/替换为文字；
5. 不要把 `{{symbol:img_xxx}}` 居中成独立图片段落。

---

# 六、Markdown 后处理规则调整

如果项目中存在类似正则：

```python
re.sub(r"(\{\{image:[^}]+\}\})(?=\s*\d+[\.．、])", r"\1\n\n", md)
```

请删除或改造。

新规则：

```text
不能无条件根据“图片后面是题号”断行。
```

原因：

`file_size < 2KB` 的小图可能是“.”、“的”、“是”等，如果后面刚好是数字，错误断行会破坏正文。

如果确实需要保留题号断行规则，必须基于 manifest 判断：

```text
只有 image_class = image 的图片才允许题号断行；
image_class = symbol 禁止题号断行。
```

---

# 七、更新 图片处理.md

请将文档中的图片分类说明更新为以下核心规则。

## 新规则

```text
file_size < 2KB：
    符号/文字小图；
    image_class = symbol；
    Markdown 输出 {{symbol:img_xxx}}；
    行内保留；
    不独占一行；
    不参与 AI 题图映射。

file_size >= 2KB 且 original_type = inline：
    内容图片；
    image_class = image；
    Markdown 输出 {{image:img_xxx}}；
    默认块级显示；
    前后加换行；
    由代码确定位置。

file_size >= 2KB 且 original_type = anchor：
    浮动内容图片；
    image_class = anchor_image；
    不在 Markdown 原位置插入；
    交给 AI/映射逻辑定位。

<w:br/>：
    必须转成 Markdown 换行。
```

## 需要特别说明

```text
inline 图片不等于一定行内显示。
inline 只代表图片在 XML 文字流中有确定顺序。

真正决定 Markdown 中是否独占一行的是 image_class：
symbol 行内；
image 块级；
anchor_image 交给 AI。
```

---

# 八、验收标准

请确保以下输入能够得到正确输出。

## Case 1：大图和题号同段落

manifest：

```json
{
  "image_id": "img_002",
  "file_size": 45678,
  "original_type": "inline",
  "image_class": "image",
  "paragraph_index": 10,
  "run_index": 0
}
```

Word run 顺序：

```text
run0: 图片 img_002
run1: 文本 "11.大蒜交易市场..."
```

期望 Markdown：

```markdown
{{image:img_002}}

11.大蒜交易市场...
```

禁止输出：

```markdown
{{image:img_002}}11.大蒜交易市场...
```

---

## Case 2：小符号图片在文字中

manifest：

```json
{
  "image_id": "img_003",
  "file_size": 512,
  "original_type": "inline",
  "image_class": "symbol",
  "paragraph_index": 12,
  "run_index": 2
}
```

Word run 顺序：

```text
run0: 文本 "这是"
run1: 图片 img_003
run2: 文本 "正确的。"
```

期望 Markdown：

```markdown
这是{{symbol:img_003}}正确的。
```

禁止输出：

```markdown
这是

{{image:img_003}}

正确的。
```

---

## Case 3：anchor 大图

manifest：

```json
{
  "image_id": "img_005",
  "file_size": 38912,
  "original_type": "anchor",
  "image_class": "anchor_image",
  "paragraph_index": 20,
  "run_index": 1
}
```

期望：

```text
docx_to_markdown 阶段不在该段落直接插入 {{image:img_005}}。
该图片后续由 AI/MapImages 通过 ph_anchor_xxx 映射。
```

---

## Case 4：小 anchor 图

manifest：

```json
{
  "image_id": "img_006",
  "file_size": 700,
  "original_type": "anchor",
  "image_class": "symbol",
  "paragraph_index": 30,
  "run_index": 1
}
```

期望：

```text
不进入 anchor AI 匹配；
不作为题图；
可作为 symbol 或 pending 处理。
```

---

# 九、最终目标

修改后，不应再出现大图占位符与题号粘连的问题：

```markdown
{{image:img_002}}11.题目
```

而应输出：

```markdown
{{image:img_002}}

11.题目
```

同时，小于 2KB 的符号/文字图片不会被错误处理成独立题图。
