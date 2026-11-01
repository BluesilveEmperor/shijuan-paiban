---
name: shijuan-paiban
description: >-
  将试卷文件（DOCX 或 PDF）自动转换为 LaTeX 排版并编译为 PDF，可同时生成配套答题卡。
  支持两种输入格式：
  - DOCX 输入：使用 pandoc 提取文本 + 解包取图片
  - PDF 输入：使用 MinerU SDK (mineru-open-sdk) 提取为 Markdown + 图片
  能自动识别文件名含"答案"的文档并使用参考答案模板排版。
  当用户说"用模板排版这个docx""把这个word转成tex""重新排版试卷""排版这个答案""处理这个答案文档"
  或"排版这个pdf""把这个pdf转成tex"时，
  或者用户引用的文件名（含 @ 或路径）中包含"答案"字样时，立即使用本技能。
  用户说"生成答题卡""做一份答题卡""配个答题卡""出A3答题卡"时也使用本技能。
  即使看起来只是"转一下格式""排个版"，也要调用此技能。不要问用户"是否要使用 skill"——直接执行。
compatibility:
  require_tools:
    - Bash
    - Read
    - Write
    - Edit
  require_skills:
    - docx
---

# 试卷 → LaTeX 自动排版

## 工作流概览

```mermaid
flowchart TD
    A[用户提供文件路径] --> B{文件类型?}
    B -- ".docx" --> C[1-A. pandoc 尝试提取]
    C --> C1{输出类型?}
    C1 -- "含文本" --> F[2-A. 解包 DOCX 取图片 / WMF→PNG]
    C1 -- "仅图片 扫描件" --> C2[1-A-OCR. 解包取页面图 + MinerU OCR]
    B -- ".pdf" --> D[1-B. 检查 MinerU SDK 配置]
    D --> E[1-B. MinerU SDK 提取 Markdown + 图片]
    F --> H[3. 读模板 → 知能力]
    C2 --> H
    E --> G[2-B. 确认图片位置 + 设置图片目录]
    G --> H
    H --> I[4. 写 LaTeX → 逐题转换]
    I --> J{答案文档?}
    J -- 是 --> K[5. 跳过教师版生成]
    J -- 否 --> L[5. 生成教师版 → 解答题分页]
    L --> LB[5-B. 生成答题卡 A4/A3]
    K --> M[6. 编译 → 验证]
    LB --> M
    M --> N[7. 清理]
    N --> O[8. 日志采集与上传]
```

## 一句话原则

用户提供 **试卷文件路径**（DOCX 或 PDF）和 **模板路径** → 你全自动完成提取、转换、编译。用户不需要知道任何脚本路径。

需要答题卡时，追加一条命令即可（见「步骤 5-B」），题量与分值自动从排好的试卷 `.tex` 里读。

## 输入格式自动识别

**根据文件扩展名自动选择提取流程：**
- **`.docx` 输入** → 先用 pandoc 尝试提取文本：
  - **含文本内容** → pandoc 方案 + 解包取图片
  - **仅图片（扫描件 DOCX）** → 解包取页面图 + MinerU SDK OCR 识别
- **`.pdf` 输入** → 使用 MinerU SDK 提取 Markdown + 图片

## 关键约定：图片目录命名

**图片目录名自动推导规则**（用户可覆盖）：

**DOCX 输入时：**
- **答案文档**（文件名含"答案"）：取 DOCX 文件名去掉 `.docx`，加前缀 `Images-`
- **试题文档**（不含"答案"）：固定为 `media`

**PDF 输入时：**
- 图片目录名取 PDF 文件名去掉 `.pdf`，加前缀 `Images-`

**在后续所有步骤中，用 `{图片目录}` 代表推导出的目录名。**

## 零配置检测

```bash
DOCX_SKILL_DIR=$(find ~/.claude/skills -maxdepth 2 -name "SKILL.md" -path "*/docx/SKILL.md" -exec dirname {} \; 2>/dev/null | head -1)
```

## 使用前环境检查（必须首先执行）

```bash
# 1. 检查 XeLaTeX
xelatex --version 2>/dev/null && echo "[OK] XeLaTeX" || echo "[ERROR] XeLaTeX 未安装"
# 2. 检查 pandoc
pandoc --version 2>/dev/null && echo "[OK] pandoc" || echo "[ERROR] pandoc 未安装"
# 3. 检查 Python
python --version 2>/dev/null || python3 --version 2>/dev/null || echo "[ERROR] Python 未安装"
# 4. 检查 Pillow（DOCX 需要）
python -c "from PIL import Image; print('[OK] Pillow')" 2>/dev/null || echo "[WARN] Pillow 未安装"
# 5. 检查 MinerU SDK（PDF 需要）
python -c "import mineru; print('[OK] MinerU SDK')" 2>/dev/null || echo "[WARN] MinerU SDK 未安装"
# 6. 检查 MinerU 配置（PDF 需要）
[ -f ~/.mineru/config.yaml ] && echo "[OK] MinerU 配置" || echo "[WARN] MinerU 配置不存在"
# 7. 检查 Git
git --version 2>/dev/null && echo "[OK] Git" || echo "[WARN] Git 未安装"
```

**缺少时的处理：**

| 检查项 | 缺少时的处理 |
|--------|-------------|
| XeLaTeX | **必须安装**：提示用户安装 TeX Live 或 MiKTeX |
| pandoc | **必须安装**：提示用户安装 pandoc |
| Python | **必须安装**：提示用户安装 Python 3.8+ |
| Pillow | **DOCX输入需要**：运行 `pip install Pillow` |
| MinerU SDK | **PDF输入需要**；**扫描件DOCX也需要**：运行 `pip install mineru-open-sdk` |
| MinerU 配置 | **PDF输入需要**；**扫描件DOCX也需要**：引导用户配置 Token（见下方） |

### MinerU SDK 配置引导（PDF输入必须）

> "使用 MinerU SDK 解析 PDF 需要配置 API Token。
> 1. 确保已安装：`pip install mineru-open-sdk`
> 2. 创建配置：`mkdir -p ~/.mineru`
> 3. 编辑 `~/.mineru/config.yaml`，写入：`token: '你的API密钥'`
> 4. 获取密钥：https://mineru.net/apiManage/token
> 配置完成后重新运行即可。"

**⚠️ 只有所有必须项（XeLaTeX、pandoc、Python）都通过后，才能继续执行后续步骤。**

---

## 标准工作流（按顺序执行）

### 步骤 1：读取文件 → 看结构

#### 1-A. DOCX 输入

**首先用 pandoc 尝试提取文本：**
```bash
pandoc "<docx路径>" -t markdown --wrap=none --track-changes=all
```

**判断输出类型：**
- **输出包含文本内容**（标题、题目文本等）→ 按原有 pandoc 方案继续（步骤 2-A 取图片，步骤 4 转换）
- **输出仅包含图片**（扫描件 DOCX，pandoc 只能提取 `![](media/imageN.png)`）→ **走 MinerU OCR 方案**：

```bash
# 1. 解包 DOCX 提取页面图片
TEST_DIR="<输出目录>"
mkdir -p "$TEST_DIR/media"
python3 << 'PYEOF'
import zipfile, os
docx_path = "<docx路径>"
out_dir = "$TEST_DIR/media"
with zipfile.ZipFile(docx_path, 'r') as z:
    for f in z.namelist():
        if f.startswith('word/media/') and not f.endswith('/'):
            basename = os.path.basename(f)
            z.extract(f, os.path.join(out_dir, "tmp_media"))
            os.rename(os.path.join(out_dir, "tmp_media", f), os.path.join(out_dir, basename))
import shutil
shutil.rmtree(os.path.join(out_dir, "tmp_media"), ignore_errors=True)
print(f"提取 {len(os.listdir(out_dir))} 张页面图片")
PYEOF

# 2. 对每张页面图片执行 MinerU OCR
MATH_EXTRACT=$(find ~/.claude/skills -path "*/shijuan-paiban*/scripts/math_pdf_extract.py" 2>/dev/null | head -1)
for img in "$TEST_DIR/media"/image*.png; do
    PYTHONIOENCODING=utf-8 python "$MATH_EXTRACT" "$img" --output-dir "$TEST_DIR/mineru-out" --language ch
done
```

**⚠️ 扫描件 DOCX 的 MinerU 输出处理：**
- 每张页面图片会生成一个独立的 `.md` 文件（如 `image1.md`, `image2.md`...）
- 按顺序合并所有 `.md` 文件的内容，即为完整试卷文本
- 公式已为 LaTeX 格式，可直接嵌入
- 图片引用路径需对应到 `$TEST_DIR/media/` 目录
- **跳过步骤 2-A**（图片已在 OCR 过程中提取），直接进入步骤 3

#### 1-B. PDF 输入（MinerU SDK 方案）

先检查 MinerU 配置：
```python
from pathlib import Path
cfg = Path.home() / ".mineru" / "config.yaml"
if cfg.exists():
    import yaml
    token = yaml.safe_load(cfg.read_text(encoding="utf-8")).get("token", "")
    print(f"[OK] token 有效 (len={len(token))" if token else "[WARN] token 为空")
else:
    print("[WARN] 配置文件不存在")
```

配置好后执行提取：
```bash
MATH_EXTRACT=$(find ~/.claude/skills -path "*/shijuan-paiban*/scripts/math_pdf_extract.py" 2>/dev/null | head -1)
PYTHONIOENCODING=utf-8 python "$MATH_EXTRACT" "<pdf路径>" --output-dir ./math-output --language ch
```

**脚本参数：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--output-dir` | `./math-output` | 输出目录 |
| `--model` | `vlm` | pipeline / vlm / html |
| `--ocr` | 关闭 | 扫描件启用 OCR |
| `--language` | `en` | 中文用 `ch` |
| `--pages` | 全部 | 如 `"1-10,15"` |

**MinerU 限制：** 单文件 ≤ 200MB / 600 页；免费版日限额 2000 页

### 步骤 2：提取图片

#### 2-A. DOCX 输入（解包取图片）

**试题文档（无"答案"字样）：**
```bash
python "$DOCX_SKILL_DIR/scripts/office/unpack.py" "<docx路径>" "<临时目录>/"
cp "<临时目录>/word/media/"*.png "<docx所在目录>/"
```

**答案文档（文件名含"答案"）：**
```bash
python "$DOCX_SKILL_DIR/scripts/office/unpack.py" "<docx路径>" "<临时目录>/"

# 推导图片目录名
img_dir="Images-$(basename "<docx路径>" .docx)"

# 复制 PNG
mkdir -p "<docx所在目录>/$img_dir"
cp "<临时目录>/word/media/"*.png "<docx所在目录>/$img_dir/"

# 批量转换 WMF → PNG（600 DPI）
python3 << 'PYEOF'
import os, zipfile, glob
from PIL import Image

docx = glob.glob("*.docx")[0]
img_dir = "Images-" + os.path.basename(docx).replace(".docx", "")

with zipfile.ZipFile(docx, 'r') as z:
    for name in z.namelist():
        if 'media' in name and name.lower().endswith('.wmf'):
            z.extract(name, "tmp_media")
            os.rename(f"tmp_media/{name}", f"{img_dir}/{os.path.basename(name)}")
os.system("rm -rf tmp_media")

for fname in sorted(os.listdir(img_dir)):
    if not fname.lower().endswith('.wmf'):
        continue
    img = Image.open(f"{img_dir}/{fname}")
    w, h = img.size
    scale = 600 / 72.0
    new_w = max(int(w * scale), 30)
    new_h = max(int(h * scale), 30)
    img.resize((new_w, new_h), Image.LANCZOS).save(
        f"{img_dir}/{fname.replace('.wmf', '.png')}",
        dpi=(600, 600), quality=90)
    os.remove(f"{img_dir}/{fname}")
PYEOF
```

#### 2-B. PDF 输入（MinerU SDK 自动提取图片）

MinerU 已完成提取，只需确认位置：
```bash
ls ./math-output/  # 确认 .md 和图片文件存在
# 设置 {图片目录} 变量
```

### 步骤 3：读模板 → 知能力

**模板文件位置：** `templates/` 目录（与本 SKILL.md 同级）

**自动模板选择规则：**
| 条件 | 模板文件 |
|------|---------|
| 文件名含"答案" | `templates/gaokao-answer-template.tex` |
| 文件名含"专题"/"专项" | `templates/zhuanti_*.tex` 系列 |
| 文件名含"周练"/"周测"/"周考" | `templates/zhoukan_*.tex` 系列 |
| 文件名含"错题"/"纠错"/"订正" | `templates/cuoti_*.tex` 系列 |
| 默认（高考数学试卷） | `templates/gaokao-template.tex` |

**读取模板后，重点关注：**
- 选择题环境（`tasks`? `choice`?）
- 大题编号（`examenum`? 普通 `enumerate`?）
- 是否已加载 `graphicx`、`wrapfig`
- 自定义命令（`\blank`? `\mycircled`?）
- 当前是否有 `\linespread` 设置

**模板能力清单（manifest）：** 参见 `templates/manifest.json`

### 步骤 4：写 LaTeX → 逐题转换

保留模板的 **完整导言区**，只替换 `\begin{document}` 到 `\end{document}` 之间的正文。

**⚠️ 详细的转换规则见 `docs/conversion-rules.md`，此处仅列核心约束：**

#### 结构约束（不可违反）
1. **选择题外层必须用 `enumerate`，内层选项才用 `tasks`**。禁止单独使用 `tasks` 作为题目列表容器
2. **解答题必须用 `examenum` 环境**，start 值 = 单选题数 + 多选题数 + 填空题数 + 1
3. **填空题空位用 `\blank`**（模板已定义）
4. **图片宽度不得超过 `0.35\textwidth`**

#### 题型结构速查
```latex
% 单选
\begin{enumerate}[itemsep=0.3em]
    \item 题目内容
    \begin{tasks}(4)  % 简短选项4列，长选项2列
        \task A \task B \task C \task D
    \end{tasks}
\end{enumerate}

% 多选
\begin{enumerate}[start=9, itemsep=0.5em]
    \item 题目内容
    \begin{tasks}(2)
        \task A \task B \task C \task D
    \end{tasks}
\end{enumerate}

% 填空
\begin{enumerate}[start=12, itemsep=0.8em]
    \item 题目内容 \blank.
\end{enumerate}

% 解答
\begin{examenum}[start=15, itemsep=2.5cm]
    \item （13分）题目描述．
    \begin{examenum}
        \item 第1问；
        \item 第2问．
    \end{examenum}
\end{examenum}
```

#### 图片排版约束

**通用规则**：
- **始终用 `\centering`，禁止 `\raggedleft`**（图注始终在图片正下方）
- 单张图片最大宽度 `0.35\textwidth`
- 图片与选项并排时用 `minipage` 左右布局
- 多图并排时添加 `height=Xcm,keepaspectratio` 限制高度

**场景速查**：

| 场景 | 方案 |
|------|------|
| 小装饰图 | 行内 `\includegraphics[height=0.6em]` |
| 几何图在列表外 | `wrapfigure` 右侧环绕 |
| 几何图在列表内（有子问） | `minipage` 左右并排 |
| 单张插图无子问 | `wrapfigure{r}{0.30\textwidth}` 右侧环绕（图在 item 前） |
| 图片作为选项 | `tasks(4)` 一行4张，`0.12\textwidth` |
| 图片+选项并排 | `minipage` 左选项右图片 |
| 多张图片并排 | 2张：`0.42\textwidth`+`height=3cm`；3张：`0.28\textwidth`+`height=2.5cm` |
| TikZ 图 | `\resizebox{0.35\textwidth}{!}{...}` |

**图片+选项布局决策**：

| 条件 | 布局方式 |
|------|---------|
| 选项简短（< 10字） | 图片在上，选项在下 |
| 选项较长（> 15字）或含公式 | `minipage` 左右并排 |
| 选项与图片高度相当 | `minipage` 左右并排 |

**禁止事项**：
- ❌ `\raggedleft`（导致图注不对齐）
- ❌ `tasks(1)` 竖排图片选项
- ❌ 图片宽度超过 `0.30\textwidth`（单张，默认）
- ❌ 多图并排时不限制高度
- ❌ 图片+长选项时上下布局（导致选项重叠）

#### 答题空间插入规则（学生版）

**模板已定义三个命令**（纯留白，无线条无边框）：

| 命令 | 留白量 | 适用模式 |
|------|--------|---------|
| `\answerc` | 1.5em | compact（自学） |
| `\answern` | 3em | normal（作业） |
| `\answere` | 5em | exam（测试） |

**插入位置**：每道解答题的 `\item` 内容结束后、下一 `\item` 之前：

```latex
\begin{examenum}[start=15, itemsep=1.5em]
    \item （13分）题目描述．
    \begin{examenum}
        \item 第1问；
        \item 第2问．
    \end{examenum}
    \answern  % ← 在此处插入答题空间

    \item （15分）下一题...
\end{examenum}
```

**规则**：
- 最后一道解答题后**不插入**答题空间（避免尾部留白过多）
- 答题空间命令前需有空行（`\par` 已包含在命令内）
- **禁止**使用 `\rule`、`tcolorbox`、`\fbox` 等任何带线条的命令
- 教师版由 `gen_teacher.py` 自动生成，无需手动插入

#### itemsep 计算公式

**目标**：让解答题均匀分布在目标页数内，避免前两题挤在一起、后两题间距过大。

```
可用空间(cm) = 页高(29.7) - 上边距 - 下边距 - 页眉页脚 - 选择题/填空题占用 - 解答题题目本身占用
itemsep(cm) = 可用空间 / 解答题数
```

**经验值（4页试卷，margin=2cm）**：

| 解答题数 | 建议 itemsep | 说明 |
|---------|-------------|------|
| 3 题 | 2.0 ~ 2.5cm | 空间充裕 |
| 4 题 | 1.8 ~ 2.2cm | 适中 |
| 5 题 | 1.5 ~ 2.0cm | 标准配置 |
| 6 题 | 1.2 ~ 1.5cm | 偏紧凑 |

**调整顺序**：
1. 先用经验值编译一次
2. 如果超页 → 减小 itemsep 或降低 linespread
3. 如果页数有余 → 增大 itemsep 让分布更均匀
4. 如果 itemsep < 1.0cm 仍超页 → 降低 linespread 到 0.95

#### tasks 列数自动判断

**规则**：根据选项内容自动选择列数。

```python
def auto_tasks_cols(options):
    """自动判断 tasks 列数"""
    has_image = any('includegraphics' in opt for opt in options)
    has_formula = any('$' in opt for opt in options)
    avg_len = sum(len(re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', opt)) for opt in options) / len(options)
    
    if has_image:
        return 4 if avg_len < 80 else 2
    elif avg_len > 25 or has_formula:
        return 2
    else:
        return 4
```

**判断表**：

| 条件 | 列数 | 示例 |
|------|------|------|
| 选项含图片，平均长度 < 80 字符 | 4 列 | 绳结图、电路图 |
| 选项含图片，平均长度 ≥ 80 字符 | 2 列 | 带文字说明的图 |
| 选项含公式或平均长度 > 25 字符 | 2 列 | 三角函数、不等式 |
| 选项简短（< 15 字符） | 4 列 | 纯数字、简单字母 |

**示例**：
```latex
% 简短选项 → tasks(4)
\begin{tasks}(4)
    \task $\dfrac{1}{2}$ \task $\dfrac{\sqrt{2}}{2}$ \task $\dfrac{\sqrt{3}}{2}$ \task $1$
\end{tasks}

% 长选项/含公式 → tasks(2)
\begin{tasks}(2)
    \task 双曲正弦函数是增函数
    \task $\tanh(x+y) = \dfrac{\tanh x + \tanh y}{1 + \tanh x \tanh y}$
\end{tasks}

% 图片选项 → tasks(4)
\begin{tasks}(4)
    \task \includegraphics[width=0.12\textwidth]{a.jpg}
    \task \includegraphics[width=0.12\textwidth]{b.jpg}
    \task \includegraphics[width=0.12\textwidth]{c.jpg}
    \task \includegraphics[width=0.12\textwidth]{d.jpg}
\end{tasks}
```

#### 答案文档特殊处理
- `\graphicspath` 必须对齐 `{图片目录}`
- 答案块结构：题目文本 → `\daan{...}` → `\jieti` → `\xijie`
- 解答题多问：`\xiaoI` / `\xiaoII` / `\xiaoIII`
- 选项为图片时用 `\eqimg[0.15]{imageN.png}`
- **不需要生成教师版，不需要 `itemsep` 间距**

#### 页数控制与间距调整
- 学生版页数必须匹配试卷标注
- 超页时：导言区添加 `\linespread{1.05}\selectfont`
- **解答题 `itemsep` 调整原则**：让5道解答题均匀分布在2-3页内
  - 默认 `itemsep=2.5cm`，根据实际页数调整：
    - 4页试卷且5道解答题 → `itemsep=1.5cm` ~ `2.0cm`
    - 4页试卷且解答题内容少 → `itemsep=2.0cm` ~ `2.5cm`
  - 目标是避免前两题挤在一起、后两题间距过大的不均匀现象
- 教师版移除 `itemsep`（分页替代了间隙作用）

#### 答案文档的同目录试题检测
当处理答案文档时，**三段式匹配**检测同目录下对应的 `.tex` 试题文件：

```python
import os, re

def find_matching_tex(input_path):
    input_dir = os.path.dirname(input_path)
    input_stem = os.path.basename(input_path)
    for ext in ('.docx', '.pdf'):
        if input_stem.endswith(ext):
            input_stem = input_stem[:-len(ext)]
            break

    # 第一阶段：精确剥离答案后缀
    for pat in [r'-答案$', r'_答案$', r'答案$', r'答案-', r'答案_']:
        cand = re.sub(pat, '', input_stem)
        tex_path = os.path.join(input_dir, cand + '.tex')
        if os.path.exists(tex_path):
            return tex_path

    # 第二阶段：公共前缀匹配（≥3字符）
    clean_stem = re.sub(r'[-_ ]?答案[-_ ]?', '', input_stem)
    tex_files = [f for f in os.listdir(input_dir)
                 if f.endswith('.tex') and '教师版' not in f
                 and not f.lower().startswith('gaokao')
                 and 'template' not in f.lower()]
    best, best_score = None, 0
    for tf in tex_files:
        stem = tf.replace('.tex', '')
        i = 0
        while i < min(len(clean_stem), len(stem)) and clean_stem[i] == stem[i]:
            i += 1
        if i > best_score:
            best_score, best = i, tf
    if best_score >= 3:
        return os.path.join(input_dir, best)

    # 第三阶段：回退
    return None
```

### 步骤 5：生成教师版 → 三种模式

**注意：答案文档（文件名含"答案"）跳过此步。**

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `compact` | 解答题紧凑排版，下方留 2em | 自学、参考 |
| `normal`（默认） | 每道解答题下方留 6em 答题空间 | 课后作业、练习册 |
| `exam` | 解答题每题独占一页 | 课堂测试、考试模拟 |

**通用规则（三种模式均遵守）：**
- 前面三个大题（一～三）不分页，连续排版
- **学生版也同步生成**：学生版每道解答题下方留白（`\answerc` / `\answern` / `\answere`），纯留白无线条

**模式 A：`compact`（紧凑）**
- 解答题 `\itemsep=0.5em`
- 每道解答题下方留 `\vspace{2em}`（教师版）/ `\answerc`（学生版）
- 适合自学、参考

**模式 B：`normal`（标准，默认）**
- 解答题 `\itemsep=1.5em`
- 每道解答题下方留 `\vspace{6em}`（教师版）/ `\answern`（学生版）
- 适合课后作业、练习册

**模式 C：`exam`（考试）**
- Q17 跟在「四、解答题」标题后，Q18 起每题独占一页
- 移除 `itemsep`（分页替代了间隙作用）
- 适合课堂测试、考试模拟

**⚠️ Python 字符串转义陷阱：搜索 LaTeX 命令必须用 raw string `r"\begin"`，否则 `\b` 会被当作退格符。**

```python
# gen_teacher.py
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "normal"  # compact | normal | exam

with open("学生版.tex", "r", encoding="utf-8") as f:
    content = f.read()

# ── 模式参数 ──
MODE_CONFIG = {
    "compact": {"itemsep": "0.5em",  "vspace": r"\vspace{2em}",  "student_space": r"\answerc"},
    "normal":  {"itemsep": "1.5em",  "vspace": r"\vspace{6em}",  "student_space": r"\answern"},
    "exam":    {"itemsep": None,     "vspace": r"\newpage",      "student_space": r"\answere"},
}
cfg = MODE_CONFIG[mode]

start_num = 15  # ← 根据实际题量调整（单选题数 + 多选题数 + 填空题数 + 1）
start_marker = rf"\begin{{examenum}}[start={start_num}, itemsep=2.5cm]"
end_marker = r"\end{examenum}"

start_idx = content.find(start_marker)
end_idx = content.rfind(end_marker)
exam_block = content[start_idx:end_idx + len(end_marker)]
lines = exam_block.split('\n')
depth = 0
item_count = 0
new_lines = []

for line in lines:
    if r"\begin{examenum}" in line and f"[start={start_num}" not in line:
        depth += 1
    elif r"\end{examenum}" in line:
        if depth > 0:
            depth -= 1
        else:
            new_lines.append(line)
            if mode == "exam":
                new_lines.append(r"\newpage")
            else:
                new_lines.append(cfg["vspace"])
            continue

    stripped = line.lstrip()
    if mode == "exam" and stripped.startswith(r"\item ") and depth == 0:
        item_count += 1
        if item_count >= 2:
            new_lines.append(r"\newpage")

    new_lines.append(line)

modified_block = '\n'.join(new_lines)

# 替换 itemsep
if cfg["itemsep"]:
    modified_block = modified_block.replace(
        f"[start={start_num}, itemsep=2.5cm]",
        f"[start={start_num}, itemsep={cfg['itemsep']}]"
    )
else:
    modified_block = modified_block.replace(
        f"[start={start_num}, itemsep=2.5cm]",
        f"[start={start_num}]"
    )

# 生成后缀
SUFFIX = {
    "compact": "-教师版-紧凑",
    "normal":  "-教师版",
    "exam":    "-教师版-考试",
}
suffix = SUFFIX[mode]
new_content = content[:start_idx] + modified_block + content[end_idx + len(end_marker):]

with open(f"{suffix}.tex", "w", encoding="utf-8") as f:
    f.write(new_content)

# 同时生成带答题空间的学生版
student_content = content.replace(
    f"[start={start_num}, itemsep=2.5cm]",
    f"[start={start_num}, itemsep={cfg['itemsep'] or '1.5em'}]"
)
# 在每道 \item 后插入学生答题空间命令（简化：在 \end{examenum} 前插入）
# 实际实现需在循环中逐 item 插入，此处为示意
with open(f"学生版-答题空间.tex", "w", encoding="utf-8") as f:
    f.write(student_content)
```

**使用方式：**
```bash
# 模式 A：紧凑
python gen_teacher.py compact

# 模式 B：标准（默认）
python gen_teacher.py
# 或
python gen_teacher.py normal

# 模式 C：考试
python gen_teacher.py exam
```

### 步骤 5-B：生成答题卡（可选）

**触发条件**：用户要求"配答题卡""生成答题卡""做A3答题卡"，或试卷是考试/测试用途需要作答区。
答案文档不生成答题卡。

**一条命令搞定**（自动识别题量 + 自动推算版面 + 自动编译）：

```bash
python scripts/gen_answer_sheet.py "<试卷.tex>"
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--layout` | `a4` | `a4` / `a3` / `both`（a3 每张纸并排两个 A4 版面，对折成册） |
| `--pages` | 自动 | 强制版面数（a4=页数，a3=张数） |
| `--block` | `2` | 每面最多几道解答题 |
| `--percol` | `4` | 选择题每列题数 |
| `--title` / `--subject` | 自动 | 覆盖卷头文字 |
| `--bw` | 关 | 黑白版（不印彩色框线） |
| `--no-compile` | 关 | 只出 `.tex` 不编译 |
| `--no-figs` | 关 | 不附带解答题的图/三线表，只出纯答题区 |
| `--print-spec` | — | 只打印解析结果，用于核对题量与附图 |
| `--suffix` | `答题卡` | 输出文件名后缀（同名手工版已存在时换个后缀即可） |
| `--force` | 关 | 允许覆盖非本脚本生成的文件（默认拒绝） |
| `--single/--multi/--blanks/--solves` | — | 解析失败时手工兜底 |

**两道安全防护（默认开启）：**

- **拒绝非学生版输入**：文件名含 `答案` / `教师版` / `答题卡` / `解析` / `详解` 时直接报错退出（退出码 4）——答题卡只能从学生版试题解析。
- **不覆盖手工版**：目标 `.tex` 已存在且开头没有本脚本的生成标记时，跳过并提示（退出码 5），原文件分毫不动。确认要替换加 `--force`，或换个 `--suffix`。

**自动识别的题量来源**（读试卷 `.tex` 正文，不依赖文件名）：

| 项 | 识别方式 |
|----|---------|
| 单选 / 多选 | 扫 `\section*{一、…}`、`\noindent\textbf{二、…}` 等小节标题，按"单选/多选/多项选择/多项符合"分类，再数该小节内**顶层** `\item`（自动跳过嵌套 `examenum`） |
| 填空 | 同上，"填空题"小节 |
| 解答题 | 数顶层 `\item`，并从 `（本题满分 13 分）` / `（本小题满分 13 分）` / `（13分）` / `(13 分)` 中取分值 |
| 卷头 | 收集 `\textbf{…}`（容许一层嵌套，如 `\textbf{\LARGE{…}}`）与 `\subtitle{}` / `\subjecttitle{}` / `\title{}`，剔除「绝密★启用前」「试卷类型」「本试卷共…」「一、选择题…」等干扰项，再按「含考试/高考/联考/期末…」加权取最高分；`\\` 换行转全角空格（普通空格会被 ctex 吞掉） |

**版面数自动推算**（复刻 `answersheet.sty` 的分页算法，取最小可行值）：

1. 先找"可行"的最小版面数：**不能有空版面**（多出来的版面会变成一整片空白答题框），且每面解答题数 ≤ `block`；
2. 再看每分能摊到多少答题高度：`可用高度 / 总分 ≥ 1.05cm` 才认可，否则在 +1～+3 版面内找一个达标的；
3. 实测：新高考 19 题 → 4 版面（与宏包预设一致）；22/23 题 → 4 版面（比宏包注释的 5 更紧凑，要更宽松就 `--pages 5`）。

#### 解答题附图 / 三线表（默认开启）

立体几何的题图、统计题的表格会自动搬到答题卡对应题目的作答区，学生直接在图上画辅助线、在表里填数——不用另外打印试题。

| 内容 | 判定 | 放置方式 |
|------|------|---------|
| 单个 `tikzpicture` / `\includegraphics` | 角图 | 作答区右上角，容器宽 6cm |
| `center` 块里并排多图、含 `minipage` | 通栏 | 作答区顶部居中，容器宽 15cm |
| `tabular` / `tabularx` / `longtable`（含三线表） | 通栏 | 同上 |

- **提取粒度**：优先整块取 `center` 环境（保留「图(1) 图(2) 并排」「图 + 图注」的原版式），再捡散落的 `tikzpicture` / `\includegraphics` / `tabular`；同题多个图表会合并成一次调用（宏包按题号存储，重复调用会互相覆盖）。
- **依赖自动跟随**：原卷导言区里 `diagbox` / `booktabs` / `multirow` / `makecell` 等图表宏包、以及 `\usetikzlibrary{…}`、`\graphicspath{…}` 会一并带过来（`geometry` / `fancyhdr` / `hyperref` 这类版式宏包**绝不**搬）。所以 `\diagbox` 斜线表头也能正常排。
- **放不下就降密度**：图是硬内容，压过分隔线会盖住下一题。脚本先估图高，超过答题框 85% 就自动改成「每题独占一面」（`block=1`），并打印 `[INFO]`；单面 24.5cm 仍放不下才 `[WARN]` 让用户手工删减。**不在 TeX 里现场缩放**——量高度易错，缩出来的字号也不可控。
- **编译兜底**：带图版编译失败时（原卷图引用了答题卡里没有的宏/图片），自动退回无图版重编并打印错误摘要，保证答题卡本身一定能出。
- **不要图**：`--no-figs`。

**想调整时**（按优先级）：

| 症状 | 做法 |
|------|------|
| 解答题写不开 | `--pages 5`（加版面） |
| 页面太空 / 太多页 | `--pages 3`，或 `--block 3` |
| 选择题挤成一坨 | `--percol 3`（每列 3 题） |
| 黑白印刷 | `--bw` |
| 某题图太大、自动变成每题一面 | 想要紧凑就 `--no-figs`，或先删原卷里多余的图 |
| 解析出的题量不对 | 先 `--print-spec` 核对，再用 `--single/--multi/--blanks/--solves` 覆盖 |

**输出物**（与试卷同目录）：

```
<卷名>-答题卡.tex / .pdf        A4，4 个版面
<卷名>-答题卡-A3.tex / .pdf     A3 横向，2 张纸（--layout a3/both 时）
answersheet.sty                 宏包副本，供日后单独重编
```

**⚠️ 答题卡必须 xelatex 连编两次**（模板用 `remember picture` 定位，一次页码与坐标不准）。
脚本已自动连编两次并清理 `.aux/.log`。

**⚠️ 版式参数改动后若位置错乱**：删掉同名 `.aux` 再连编两次。

**模板本体**：`templates/answer-sheet/answersheet.sty`（宏包）+ `answer_sheet.tex`（骨架，含三档卷型预设注释）。
需要换配色改 `--color`（任意 xcolor 颜色名，默认 `GKpink`）。

**宏包侧的附图接口**（手工建卡时用）：

```latex
\begin{document}
\gkFig{16}{\begin{tikzpicture}...\end{tikzpicture}}   % 右上角小图
\gkBlock{19}{\begin{tabular}{...}...\end{tabular}}   % 顶部通栏（宽表）
\gkMake
\end{document}
```

参数是**题号**（不是第几道）；宏包用 `\long` 定义，内容里可以有空行。

### 步骤 6：编译 → 验证

**试题文档（编译两个版本，各两次）：**
```bash
cd "<输出目录>"
xelatex -interaction=nonstopmode "文件名.tex"
xelatex -interaction=nonstopmode "文件名.tex"
grep -E "Overfull|Error" "文件名.log" | grep -v "infwarerr"
pdfinfo "文件名.pdf" 2>/dev/null | grep Pages

# 教师版（onepage）
xelatex -interaction=nonstopmode "文件名-教师版.tex"
xelatex -interaction=nonstopmode "文件名-教师版.tex"

# 教师版（space）
xelatex -interaction=nonstopmode "文件名-教师版-答题空间.tex"
xelatex -interaction=nonstopmode "文件名-教师版-答题空间.tex"
```

**答案文档（只编译一个版本）：**
```bash
cd "<输出目录>"
xelatex -interaction=nonstopmode "文件名.tex"
xelatex -interaction=nonstopmode "文件名.tex"
pdfinfo "文件名.pdf" 2>/dev/null | grep Pages
```

**验证要点：**
- 学生版/答案版页数应与试卷标注一致
- 教师版（onepage）页数不超过 7 页
- 解答题编号正确
- 答案文档的【答案】【解析】【详解】结构显示正确

**⚠️ 编译后执行结构验证：**
```bash
python scripts/validate_tex.py "文件名.tex"
```
如验证失败，根据报告修正后重新编译。

**⚠️ 编译后执行视觉验证：**
```bash
pdftoppm -png -r 150 "文件名.pdf" preview
```
用 Read 工具查看 preview-*.png，确认：图片位置正确、公式渲染正常、无文字溢出。如有问题，修正后重新编译。

### 步骤 7：清理
```bash
rm -rf "<临时目录>"
rm -f gen_teacher.py
rm -f .aux .log .out  # 所有版本
```

**保留：**
- 试题文档：`.tex` 源文件（学生版+教师版×2）、`.pdf`、图片
- 答案文档：`.tex` 源文件、`.pdf`、`{图片目录}/`
- 答题卡：`<卷名>-答题卡.tex/.pdf`（及 `-A3` 版）、`answersheet.sty`

### 步骤 8：日志采集与上传

```python
import sys
sys.path.insert(0, "<skill目录>/scripts")
from logger import TaskLogger
from uploader import silent_upload

logger = TaskLogger(log_dir="log-runtime", task_name="试卷排版")
step = logger.start_step("步骤名称")
# ... 执行步骤 ...
logger.end_step(step, status="成功")

# 上传
silent_upload(log_runtime_dir="log-runtime", task_name="试卷排版")
```

---

## 专题卷 & 周练卷 & 错题卷

### 模板选择规则

| 文件名特征 | 模板系列 | 版本 |
|-----------|---------|------|
| 含"专题"/"专项" | `zhuanti_*.tex` | 四件套（student/teacher/onepage/content） |
| 含"周练"/"周测"/"周考" | `zhoukan_*.tex` | 四件套 |
| 含"错题"/"纠错"/"订正" | `cuoti_*.tex` | 三件套（student/teacher/content） |

### 专题卷变量表

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `zhuantiName` | 专题名称 | 必填 |
| `zhuantiGrade` | 年级 | 必填 |
| `zhuantiDate` | 日期 | 必填 |
| `tierNames` | 分层名称 | 基础巩固,能力提高,拔高挑战 |
| `saqItemSep` | 解答题间距 | 2.5cm（学生版），教师版自动改 0.3em |

### 周练卷变量表

| 变量 | 说明 | 备注 |
|------|------|------|
| `zhoukanMode` | 模式 | limited（限时30-45min）/ homework |
| `mcqCount` | 单选题数量 | **必须指定** |
| `msqCount` | 多选题数量 | **必须指定** |
| `blankCount` | 填空题数量 | **必须指定** |
| `saqCount` | 解答题数量 | **必须指定** |

### 错题卷变量表

| 变量 | 说明 |
|------|------|
| `cuotiTitle` | 标题 |
| `cuotiSource` | 错题来源 |
| `cuotiDate` | 日期 |

**错题卷结构（每道错题）：** 题目 → 错误解法（灰色）→ 错因分析（红，教师版可见）→ 正确解法（绿，教师版可见）→ 方法总结（棕，教师版可见）→ 同类变式（青，教师版可见）

---

## 题库维护与批量整理

### 题库现有结构

```
题库根目录/
├── 高考真题（模拟）卷\        # 190 个成卷文件夹 + 5 个年份源目录（2022.6–2026.6，源目录不动）
│   └── <卷名>\               # 每卷：试题 tex + *答案.tex + Images-*\ + build.py
├── 考研数学真题卷\
│   ├── 2008年\ … 2025年\     # 18 个年份文件夹：数学（一/二/三）真题+解答共 6 tex + Images ×3 + build.py
│   ├── 2024-<大学>\          # 71 个高校文件夹：高等代数/数学分析 tex 对 + build.py
│   └── 题库\                 # 书稿工程：main.tex → chapters/2024/content → 各校 content → solutions/body
│                              # build.py 为书稿版（只编 main.tex ×3，禁止单编章节 tex）
└── 高三数学\                  # 源材料 + .math-output（MD 中间产物）
```

### 一键编译脚本 build.py（两种变体）

| 变体 | 位置 | 行为 |
|------|------|------|
| 通用版 | 每个试卷/高校/年份文件夹 | 编译文件夹内全部 `*.tex` ×2，统计 log 中 `^!` 行数为错误数，清理 `.aux/.log/.out`，保留 PDF |
| 书稿版 | `题库/` | 只编译 `main.tex` ×3（目录页码稳定），其余同上 |

- `find_xelatex()` 按机器实际探测，顺序：`shutil.which('xelatex'/'xelatex.exe')` → 常见安装位置逐一试探（如 `<盘符>:\texlive\<年份>\bin\windows\xelatex.exe`、`/mnt/<盘符>/texlive/...`、`/usr/local/bin/xelatex`、`/usr/bin/xelatex`），命中即用；**不要假设固定盘符/年份**
- 新整理的含 tex 文件夹都应部署一份 `build.py`（从任一已有文件夹复制母本即可）

### MD→TEX 批量流水线（scripts/）

| 脚本 | 用途 |
|------|------|
| `md2tex.py` / `md2ans.py` | MD 中间产物 → 试题 tex / 答案 tex（`\eqimg` 宏、graphicspath 自动对齐） |
| `batch_convert.py` / `batch_convert_ans.py` | 批量处理整目录 |
| `convert_new_papers.py` | 新卷一键转换入口 |
| `split_combined.py` / `split_xj3.py` | 拆分合并卷 / 新课标卷 |
| `fix_md_corruptions*.py` / `fix_errors.py` / `fix_error_answers.py` / `finish_papers.py` | 中间产物修复与收尾 |

**回归测试**：`tests/test_fixed.py`、`tests/test_round3.py`。改流水线后必须全部通过。

### 整理规范（历次会话沉淀）

- **只动副本**：先复制到目标位置，再在副本里删除/改名；原件（桌面、源目录）永不修改
- **图片先核实再删**：全库 grep `\includegraphics` / `\graphicspath` 建引用集，未被引用的才删；`_chk`、`_tmp_*` 类临时图片目录通常整目录删
- **编译产物判定**：`pdfinfo` 看 Creator——`LaTeX with hyperref` 等即为编译产物可删；扫描原件/原始集合 PDF 保留
- **命名**：高校文件夹加年份前缀 `2024-<大学>`；按年份归组用 `<YYYY>年` 文件夹
- **全量验证**：整理完对全部文件夹并行编译，0 error 才算完成，验证产物随后清理：
  ```bash
  ls -d 20??年 | xargs -P 4 -I{} bash -c 'cd "{}" && python3 build.py'
  ```

### ⚠ WSL/PowerShell 执行纪律（Windows 主机）

- PowerShell 会吃掉 `$`、`$(...)`、`2>/dev/null`、内联 for——**含 `$` 的命令一律写成脚本文件**（存 `C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage\`）再 `wsl bash <script>` / `wsl python3 <script>`，不要内联
- Windows 版 `xelatex.exe` 不能写 WSL `/tmp`（`-output-directory=/tmp/...` 静默失败）：就地编译再清理
- TeX Live 安装位置因机而异，先探测（`where xelatex` / `shutil.which` / 遍历各盘 `?:\texlive\*\bin\windows\`），用探测结果，不写死路径

---

## 常见问题快速修复

| 症状 | 原因 | 修复 |
|------|------|------|
| `Overfull \hbox` | 公式或选项超宽 | 选项改 2 列；`\dfrac` 改 `\frac` |
| `Undefined control sequence` | 缺少宏包 | 在导言区添加 `\usepackage{...}` |
| 图片错位/消失 | 列表环境中用了 `wrapfigure` | 改用 `minipage` 左右并排 |
| 页数超限 | 添加了 2.5cm 间隙 | 加 `\linespread{1.05}\selectfont` |
| Python 匹配不到 LaTeX | 字符串转义 | 用 raw string `r"\begin"` |
| 教师版分页没生效 | `\b` 被当作退格符 | 所有含 `\b` 的字符串前加 `r` |
| 中文不显示 | 非 ctex 模板 | 确认模板用 `ctexart` |
| 编译有 Missing $ | 花括号不匹配 | 检查 `$...$` 配对 |
| 解答题编号从1开始 | start 值不对 | `start=单选题数+多选题数+填空题数+1` |
| 答案中 WMF 过多 | 未批量转换 | 用 Python+Pillow 批量渲染 600 DPI |
| MinerU 解析失败 | Token/网络/文件过大 | 检查配置；文件 ≤ 200MB/600 页 |
| `UnicodeEncodeError` | Windows GBK 编码 | 加 `PYTHONIOENCODING=utf-8` |
| 答题卡末页一片空白 | 版面数超过装填能力 | 脚本已规避；手改时减小 `pages` |
| 答题卡位置错乱/页脚页数不对 | 只编了一次 | xelatex 连编两次；仍异常则删 `.aux` 重编 |
| 答题卡题量识别错 | 小节标题非常规写法 | `--print-spec` 核对后用 `--single/--multi/--blanks/--solves` 覆盖 |
| 答题卡提示 `[SKIP] … 疑似手工版` | 目标文件名已被手工版占用 | 换 `--suffix`，或确认要替换后加 `--force` |
| 答题卡卷头文字不对 | 密级/说明文字被误判 | `--print-spec` 看「标题」，用 `--title` 直接指定 |
| 答题卡附图压线/盖住下一题 | 图比答题框还高 | 脚本会自动改成每题一面；仍不行就 `--no-figs` 或删原卷多余的图 |
| 附图里出现 `??` 或宏未定义 | 原卷用了答题卡没有的宏 | 已在白名单里的会自动带；其他用 `--no-figs`，或手工在生成 tex 里加 `\usepackage` |
| `\diagbox` / `\toprule` 未定义 | 原卷宏包没被识别 | 同上：白名单见 `scripts/gen_answer_sheet.py` 的 `SAFE_PKGS` |
| `File answersheet.sty not found` | 宏包不在 tex 同目录 | 脚本会自动复制；手工建卡时把 `.sty` 放到 tex 同目录 |

---

## 输出完成后检查仓库更新

```bash
# 检查 Git
python scripts/setup_git.py

# 双仓库并行检查更新
python scripts/update_repo.py --check  # 仅检查
python scripts/update_repo.py          # 检查并更新
```
