# 地理试卷 → LaTeX 排版流水线参考

> 本文档是 geo-paper-format 技能的流水线步骤详细规则索引。顶层入口见 `SKILL.md`。

## 流水线步骤

```
Step1: 读取文件 → 看结构
    ├── 1-A. DOCX 输入：pandoc 提取 Markdown
    └── 1-B. PDF 输入：MinerU SDK 提取 Markdown + 图片

Step2: 提取图片
    ├── 2-A. DOCX 输入：解包取图片 / WMF→PNG
    └── 2-B. PDF 输入：确认图片位置 + 设置图片目录

Step3: 读模板 → 知能力
    ├── 自动模板选择（试题/答案）
    └── 答案文档的三段式试题匹配

Step4: 写 LaTeX → 逐题转换
    ├── 保留模板导言区，只替换正文
    ├── 题型编号约定
    ├── 图片插入规则（wrapfigure/minipage）
    └── 答案文档特例

Step5: 生成教师版（仅试题文档）
    └── 解答题每题分页

Step6: 编译 → 验证
    ├── XeLaTeX 编译两次
    ├── Overfull/Error 检查
    └── 页数验证

Step7: 清理
    └── 删除辅助文件，保留 .tex + .pdf + 图片
```

## Step 1: 读取文件 → 看结构

### 1-A. DOCX 输入（pandoc 方案）

```bash
pandoc "<docx路径>" -t markdown --wrap=none --track-changes=all
```

快速浏览输出，识别：
- 标题（考试名称）
- 题型（选择题/非选择题/综合题）
- 题目编号
- 选项（A/B/C/D）
- 图片标记（`![...](media/imageN.png)` 或 `.wmf`）
- 材料段落（"材料一""材料二"等）

### 1-B. PDF 输入（MinerU SDK 方案）

先检查 `~/.mineru/config.yaml` 是否有有效 `token`。

```bash
python "$MATH_EXTRACT" "<pdf路径>" --output-dir ./geo-output --language ch
```

读取输出目录的 `.md` 确认提取质量。

## Step 2: 提取图片

### 2-A. DOCX 输入（解包取图片）

**试题文档（无"答案"字样）：**
```bash
python "$DOCX_SKILL_DIR/scripts/office/unpack.py" "<docx路径>" "<临时目录>/"
cp "<临时目录>/word/media/"*.png "<docx所在目录>/"
```

**答案文档（文件名含"答案"）：**
```bash
python "$DOCX_SKILL_DIR/scripts/office/unpack.py" "<docx路径>" "<临时目录>/"
# 推导图片目录名
img_dir = "Images-" + os.path.basename(docx).replace(".docx", "")
mkdir -p "<docx所在目录>/$img_dir"
cp "<临时目录>/word/media/"*.png "<docx所在目录>/$img_dir/"
# WMF→PNG 批量转换（600 DPI）
```

### 2-B. PDF 输入（MinerU SDK 自动提取图片）

MinerU SDK 已在第 1-B 步完成 Markdown + 图片的提取。只需确认图片位置并设置 `{图片目录}`。

**图片目录命名规则：**
| 文档类型 | 图片目录 |
|---------|---------|
| 答案文档（文件名含"答案"） | `Images-<文件名>` |
| 试题文档 | 固定 `media` |
| PDF 输入 | `Images-<PDF文件名>` |

## Step 3: 读模板 → 知能力

### 自动模板选择

| 条件 | 使用模板 |
|------|---------|
| 文件名含"答案" | `gaokao-geo-answer-template.tex`（答案模板） |
| 明显是地理试卷 | `gaokao-geo-template.tex`（试题模板） |
| 用户明确指定 | 按指定模板 |

### 答案文档的三段式试题匹配

1. **精确剥离**：依次去掉 `-答案`/`_答案`/`答案` 等后缀拼 `.tex`
2. **公共前缀匹配**：扫描同目录 `.tex`，取最长公共前缀 ≥ 3 字符
3. **回退**：都没找到 → 直接从输入文件提取题目文本

### 读模板时重点确认

- 用了什么选择题环境（`tasks`? `choice`?）
- 大题用什么编号（`examenum`? 普通 `enumerate`?）
- 是否已加载 `graphicx`、`wrapfig`（没有则补 `\usepackage{wrapfig}`）
- 自定义命令（`\blank`? `\mycircled`? `\Parallel`?）
- 当前是否有 `\linespread` 设置

## Step 4: 写 LaTeX → 逐题转换

### 铁律

保留模板完整导言区（`\documentclass` 到 `\begin{document}`），只替换正文。

### 地理学科公式与符号规则

- 行内 `$...$`，行间 `\[...\]`
- 温度：`$^\circ$C` 或 `℃`
- 经纬度：`$120^\circ$E`、`$30^\circ$N`
- 分数用 `\frac{}{}`
- 专有名词保留原文（如"秦岭-淮河线"、"喀斯特地貌"）

### 题型编号约定（地理试卷）

| 题型 | 环境 |
|-----|------|
| 选择题 | `\begin{enumerate}[itemsep=0.3em]` |
| 多选题 | `\begin{enumerate}[start=N]` |
| 填空题/综合题 | `\begin{examenum}[start=N, itemsep=2.5cm]` |

### 图片插入规则

所有图片宽度不得超过 `0.35\textwidth`，显示在题目内容右侧。

1. **小装饰图** → `\includegraphics[height=0.6em]`（行内）
2. **地图/示意图（列表环境外）** → `wrapfigure` 右侧环绕
3. **地图/示意图（列表环境内）** → `minipage` 左右并排
4. **TikZ 地图** → `\resizebox{0.35\textwidth}{!}{...}`

### 答案文档特例

- `\graphicspath` 必须替换为实际 `{图片目录}/`
- 选项图用 `\eqimg[0.15]{imageN.png}`（DOCX）；PDF 优先直接用 LaTeX 公式
- 每题结构：题目文本 → `\daan{答案}` → `\jieti` → `\xijie`
- 不需要生成教师版

### 页数控制

学生版严格匹配试卷标注页数；超页时加 `\linespread{1.05}\selectfont`。

## Step 5: 生成教师版

**注意：答案文档跳过此步。**

- 前面选择题/填空题大题不分页
- 解答题每题单独分页
- 从 `[start=N, itemsep=2.5cm]` 中移除 `itemsep`

> ⚠️ Python 里匹配 LaTeX 命令必须用 raw string（`r"\begin"`）。

## Step 6: 编译 → 验证

**试题文档**（学生版 + 教师版各编译两次）：
```bash
xelatex -interaction=nonstopmode "<输出文件名>.tex"
xelatex -interaction=nonstopmode "<输出文件名>.tex"
grep -E "Overfull|Error" "<输出文件名>.log" | grep -v "infwarerr"
```

**答案文档**（只编译一个版本）：
```bash
xelatex -interaction=nonstopmode "<输出文件名>.tex"
xelatex -interaction=nonstopmode "<输出文件名>.tex"
grep -E "Overfull|Error" "<输出文件名>.log" | grep -v "infwarerr"
```

## Step 7: 清理

- **删除**：临时目录、`gen_teacher.py`、`.aux`/`.log`/`.out` 辅助文件
- **保留**：
  - 试题文档 → 学生版 `.tex` + 教师版 `.tex` + 两个 `.pdf` + 图片
  - 答案文档 → 一个 `.tex` + 一个 `.pdf` + `{图片目录}/`
