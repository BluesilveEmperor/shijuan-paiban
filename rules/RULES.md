# 排版规则全量快照

> 本文件由 `scripts/gen_rules_doc.py` 自动生成，请勿手改。
> 修改规则请编辑 `rules/layout.yaml`。

<!-- 本区块由 scripts/gen_rules_doc.py 从 rules/layout.yaml 生成，请勿手改 -->

### 结构约束

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `STRUCT-ENV-001` | 选择题外层容器 | 外层 enumerate + 内层 tasks | 禁止：单独使用 tasks 作为题目列表容器<br>tasks 环境无编号能力，单独使用导致题目无序号 |
| `STRUCT-ENV-002` | 解答题环境 | examenum | 模板以 newlist 定义三级嵌套 examenum，普通 enumerate 无法复用模板缩进体系 |
| `STRUCT-BLANK-001` | 填空题空位 | \blank（模板已定义，下划线 2cm） | 自造下划线导致同一份试卷内空位宽度不一致 |
| `STRUCT-GLYPH-001` | 圈号字符 ①-⑩ 字形映射 | 导言区用 newunicodechar 把 ①-⑩ 映射到 \mycircled | ctexart 默认字体缺 ①-⑩ 字形，直接写会静默丢字——题干「如图①②③所示」渲染成「如图 所示」且编译不报错（ir_geometry 实测） |

### 图片排版

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `IMG-W-001` | 单张图片宽度硬上限 | 0.35\textwidth | 超过 0.35 时图注被挤出页边（2024 新课标Ⅱ卷第 19 题实测） |
| `IMG-W-002` | 单张题目配图默认宽度 | 0.30\textwidth | 0.30 在 4 页卷中留出足够文本环绕空间，与 IMG-W-001 的硬上限不冲突 |
| `IMG-W-003` | 并排图片宽度与高度 | 2 张并排：minipage 0.42\textwidth，图高 3cm<br>3 张并排：minipage 0.28\textwidth，图高 2.5cm | 并排不限高时三视图会把整道题顶到下一页 |
| `IMG-W-004` | 选项图片宽度 | 0.12\textwidth | 4 × 0.12 = 0.48，为 label 与 column-sep 留出余量 |
| `IMG-ALIGN-001` | 图片对齐方式 | \centering | 禁止：`\raggedleft`<br>raggedleft 使图注与图片左边缘错位，图注必须居中于图片正下方 |
| `IMG-SCENE-001` | 图片场景选择 | 小装饰图（行内） → \includegraphics[height=0.6em]<br>列表内单图（无论有无子问） → minipage 左右并排（0.62 文字 + 0.30 图片）<br>图片作为选项 → tasks(4)，图宽 0.12\textwidth<br>图片与长选项并排 → minipage 左选项右图片<br>多张图片并排 → figure[H] + minipage，必须限高<br>TikZ 图 → \resizebox{0.35\textwidth}{!}{...}<br>图片位于 \\begin{examenum} 之前（列表外） → wrapfigure{r}{0.30\textwidth} 右侧环绕 | 实测 wrapfigure 放在 examenum 列表内会静默丢图——图片完全不渲染且编译不报错（evals/fixtures/ir_geometry 第 2 题）。因此列表内单图一律走 minipage，wrapfigure 仅限列表外场景 |

### 选项排版

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `TASKS-COL-001` | tasks 列数判定 | 含图片且平均长度 < 80 字符 → 4 列<br>含图片且平均长度 ≥ 80 字符 → 2 列<br>平均可见长度 > 25 字符（含公式或纯文字） → 2 列<br>默认（简短选项，含短公式如 $\{0\}$） → 4 列 | 原规则「含公式即 2 列」会把 $\{0\}$ 这类短选项也判成 2 列，与真实试卷排版不符（evals/fixtures/standard 实测）；改为只看可见长度 |
| `TASKS-COL-002` | 禁止竖排图片选项 | 禁止 tasks(1) | 图片竖排浪费半页空间，且与相邻题目间距失衡 |

### 题目编号

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `ENUM-START-001` | 解答题起始编号 | start = 单选题数 + 多选题数 + 填空题数 + 1 | 8+3+3 配置 → start=15；手算错误是历史最高频问题 |
| `ENUM-RESUME-001` | 答案文档编号衔接 | 第一个 enumerate 不带 start，后续统一用 [resume] | 各题型独立计数会使答案文档编号从 1 反复重新开始 |

### 间距与页数

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `PAGE-001` | 学生版页数 | 严格匹配试卷标注页数 | 试卷标注「共 4 页」而实际 5 页属硬伤 |
| `PAGE-002` | 超页压缩手段（按优先级） | 减小解答题 itemsep；导言区加 \linespread{1.05}\selectfont；最后手段：调整 margin | 先动行距会破坏整体观感，应优先调 itemsep |
| `PAGE-003` | 解答题 itemsep 经验值 | 4 页 3 题：2.0 ~ 2.5cm<br>4 页 4 题：1.8 ~ 2.2cm<br>4 页 5 题：1.5 ~ 2.0cm<br>4 页 6 题：1.2 ~ 1.5cm<br>itemsep < 1.0cm 仍超页：降 linespread 至 0.95 | 10 份高考试卷实测区间 |
| `PAGE-004` | 教师版移除 itemsep | 教师版不保留 itemsep（分页已替代间隙作用） | 保留 itemsep 会让教师版页数失控 |

### 答题空间

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `ANS-001` | 答题空间命令与留白量 | \answerc：1.5em，compact 模式（自学）<br>\answern：3em，normal 模式（作业，默认）<br>\answere：5em，exam 模式（测试） | 三个命令定义在 templates/gaokao-template.tex 导言区 |
| `ANS-002` | 答题空间插入位置 | 每道解答题 \item 内容结束后；最后一道解答题不插入 | 末题插入会在页尾留大片空白 |
| `ANS-003` | 答题空间禁止线条 | 仅用 \vspace 留白 | 禁止：`\rule`、tcolorbox、`\fbox`、虚线、角标<br>用户明确要求纯留白，保持试卷整洁 |
| `ANS-004` | 教师版三种模式 | compact：itemsep 0.5em，题下 2em，文件名后缀 -教师版-紧凑<br>normal（默认）：itemsep 1.5em，题下 6em，文件名后缀 -教师版<br>exam：Q18 起每题独占一页，移除 itemsep，文件名后缀 -教师版-考试 | v3 由 onepage/space 两模式扩展而来；旧后缀 -教师版-答题空间 已废弃 |

### 输入提取

| ID | 规则 | 取值 | 说明 |
|----|------|------|------|
| `EXTRACT-001` | 图片目录命名 | DOCX 答案文档：Images-<文件名去扩展名><br>DOCX 试题文档：media<br>PDF 输入：Images-<PDF文件名去扩展名> | graphicspath 与目录名不一致时图片全部丢失且不报错 |
| `EXTRACT-002` | 扫描件判定 | pandoc 输出仅含 ![](media/imageN.png) 且无正文 → 走 MinerU OCR | 扫描件 DOCX 用 pandoc 只能拿到整页图片，提取不到任何文字 |
| `EXTRACT-003` | WMF 转 PNG | Pillow 渲染，600 DPI | xelatex 不直接支持 WMF，残留 WMF 会导致编译失败 |

> 规则版本 v2，更新于 2026-11-01。修改规则请编辑 `rules/layout.yaml` 后运行 `python scripts/gen_rules_doc.py`。
