# Question IR（paper.json）结构说明

> 渲染器 `scripts/render_tex.py` 的输入格式。
> 打印可运行的示例：`python scripts/render_tex.py --schema`

## 设计意图

把「理解」和「排版」分开：

| 环节 | 谁做 | 为什么 |
|------|------|--------|
| 题目切分、公式、表格、图片归属 | LLM | 需要语义理解，无法枚举 |
| 编号、环境嵌套、`tasks` 列数 | 渲染器 | 纯规则，LLM 判断不稳定 |
| 图片场景选择（8 选 1） | 渲染器 | 规则确定（`IMG-SCENE-001`） |
| `examenum` start 值 | 渲染器 | 纯算术，手算最易错 |
| 答题空间插入位置 | 渲染器 | 位置确定（`ANS-002`） |
| `itemsep` 分配 | 渲染器 | 经验值表（`PAGE-003`） |
| 表格 / TikZ / 罕见结构 | LLM（`raw_tex`） | 无法枚举 |

结果：同一份 IR 渲染两次**逐字节一致**，因此可以单测、可以 diff、可以进评估。

## 完整示例

```json
{
  "meta": {
    "title": "2026 年普通高等学校招生全国统一考试（模拟）",
    "template": "gaokao",
    "total_pages": 4,
    "images_dir": "media",
    "answer_space": "normal"
  },
  "sections": [
    {
      "heading": "一、选择题：本题共2小题，每小题5分，共10分。",
      "type": "choice_single",
      "questions": [
        {
          "stem": "已知集合 $A=\\{x \\mid x^2-3x+2=0\\}$，则 $A \\cup B =$",
          "options": [
            {"label": "A", "text": "$\\{0\\}$"},
            {"label": "B", "text": "$\\{0,1,2\\}$"},
            {"label": "C", "text": "$\\{1,2\\}$"},
            {"label": "D", "text": "$\\{0,1\\}$"}
          ]
        }
      ]
    },
    {
      "heading": "四、解答题：本题共1小题，共12分。",
      "type": "long_answer",
      "questions": [
        {
          "stem": "已知数列 $\\{a_n\\}$ 中，$a_1=3$，$a_{n+1}=2a_n+1$.",
          "points": 12,
          "subquestions": [
            "证明：数列 $\\{a_n+1\\}$ 是等比数列；",
            "求 $\\{a_n\\}$ 的前 $n$ 项和 $S_n$."
          ]
        }
      ]
    }
  ]
}
```

## 字段说明

### meta

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | 是 | 试卷标题 |
| `template` | 否 | `gaokao`（学生版，默认）/ `answer`（答案版） |
| `total_pages` | 否 | 试卷标注页数，用于推导 `itemsep`（`PAGE-003`） |
| `images_dir` | 否 | 图片目录名（`EXTRACT-001`）：试题 `media`，答案 `Images-<文件名>` |
| `answer_space` | 否 | `compact` / `normal`（默认）/ `exam`（`ANS-001`） |
| `front_matter` | 否 | 自定义标题区原始 LaTeX，省略则用模板标准标题+注意事项 |

### section

| 字段 | 必填 | 说明 |
|------|------|------|
| `heading` | 是 | 大题标题（含题量与分值） |
| `type` | 是 | `choice_single` / `choice_multi` / `fill_blank` / `long_answer` |
| `start` | 否 | 显式起始编号；省略则按累计题量自动推导（`ENUM-START-001`） |
| `itemsep` | 否 | 显式指定；省略则按 type 或 `PAGE-003` 推导 |
| `questions` | 是 | 题目数组 |

### question

| 字段 | 必填 | 说明 |
|------|------|------|
| `stem` | 是 | 题干（LaTeX） |
| `points` | 否 | 分值，渲染成 `（N分）` |
| `options` | 否 | `[{label, text, image}]`，`image` 用于图片选项 |
| `subquestions` | 否 | 子问数组，自动包 `examenum` |
| `images` | 否 | `[{file, caption}]`，布局由 `IMG-SCENE-001` 自动决定 |
| `image_layout` | 否 | `auto`（默认）/ `wrap` / `side` / `multi` / `inline` |
| `raw_tex` | 否 | **逃生舱**：非空时直接输出该 LaTeX，跳过所有渲染 |
| `no` | 否 | 题号，省略则自动编号 |

### 答案版额外字段（`template: answer`）

| 字段 | 渲染结果 |
|------|---------|
| `answer` | `\daan{...}` |
| `analysis` | `\jieti ...` |
| `detail` | `\xijie ...` |
| `sub_details` | `\xiaoI` / `\xiaoII` / `\xiaoIII` |

## 使用

```bash
# 渲染
python scripts/render_tex.py paper.json -o 学生版.tex

# 渲染后立即结构验证
python scripts/render_tex.py paper.json -o 学生版.tex --validate

# 生成教师版（三种模式）
python scripts/gen_teacher.py 学生版.tex --mode normal
```

## 逃生舱

`raw_tex` 用于无法用 IR 表达的结构（复杂 TikZ、特殊表格、跨题排版）：

```json
{
  "raw_tex": "\\item （12分）如图所示：\n\\begin{tikzpicture}...\\end{tikzpicture}"
}
```

**`raw_tex` 里的 `\item` 需要自己写**——渲染器会原样输出，不再补 `\item`。
使用 `raw_tex` 的题目不参与自动编号校验，请自行确认编号正确。
