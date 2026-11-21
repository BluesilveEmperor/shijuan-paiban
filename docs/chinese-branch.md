# 语文试卷分支（chinese）

> 只在处理语文卷时适用。数学卷用 `paper.json` + `render_tex.py`；语文卷的 IR、模板、
> 产物命名都不相同，不要混用。

## 学科开关

- 仓库根 `shijuan.config.yaml` 的 `subject: chinese`（chinese 分支默认）
- 临时覆盖：`SHIJUAN_SUBJECT=chinese`
- 差异项集中在 `scripts/subject.py`：MD 输出目录、日志分支、答题卡命名、必备宏包、题型关键词

## 与数学分支的差异

| 维度 | 数学 | 语文 |
|------|------|------|
| IR | `paper.json`：sections → questions，渲染器做排版决策 | `chinese.json`：线性 block 流（16 种），渲染器主要做块→命令直译（仅选项排布/图宽做少量决策） |
| 模板 | `templates/math/gaokao-template.tex` / `gaokao-answer-template.tex` | `templates/chinese/ywexam.sty`（ctexart + xeCJKfntef，18 命令 / 4 环境） |
| 题号 | 自动编号 | 手工写入 `\question{12}{…}` |
| 选项 | `tasks` 横排 | `choices` 纵排 A. B. C. D. |
| 答案宏 | `\daan` / `\jieti` | `\ans` / `\subans` / `\scorenote` |

## 批量流水线（PDF → 成品）

```bash
python scripts/ops/batch_chinese.py --only "2511杭州一模"        # 单卷试跑
python scripts/ops/batch_chinese.py --start 14 --limit 10        # 分批：第 15 套起跑 10 套
python scripts/ops/batch_chinese.py                              # 全部 52 套
```

流程：PDF → MinerU OCR（缓存在 `.yw-ocr/`，重跑不重复计费）→ `md2chinese.py`
→ `render_chinese.py` → xelatex ×2。每卷产物：

```
语文卷-<考试名>.tex / .pdf
语文答案-<考试名>.tex / .pdf
ywexam.sty
build.py
images/                     （原卷有图时）
```

**命名规则**：考试名以文件夹名优先（去掉开头 4 位年月号），源 PDF 名仅在文件夹名冗长或不合法时
兜底；试题与答案共用同一考试名。实现见 `scripts/render/chinese_naming.py`，源文件名互相矛盾的
少数目录用 `OVERRIDES` 人工指定。

**OCR 模式自动切换**：首选 `vlm`；试题卷解析后若四选项题不足 4 组、或正文出现散落的
`A./B./C./D.`，自动改用 `pipeline` 重识别并取较优结果（日志标注 `[切换pipeline: ...]`）。
两种模式的 md 分目录缓存，不会互相覆盖。改首选模式只需调整 `batch_chinese.py` 的
`PRIMARY_MODEL` 常量，备选会自动反向切换。

**OCR 局限（必须交代）**：MinerU 会漏识个别题干或答案行。渲染器对题号不连续只告警、不自动
补空题，以免编造内容。批量结果中约半数卷存在缺号，出卷前必须对照原卷人工补齐
（`[WARN] 题号不连续：缺失 [...]` 会打印在批量日志里）。

## 实战踩坑清单（2026-11 无锡期中卷复盘）

> 一次真实排版（9 页 PDF：试题 6 页 + 答案 3 页图片 → 试题 8 页 + 答案 4 页）暴露的
> 全部问题与对策。**标「已自动」的由脚本处理，不需要人工改 IR。**

### 环境与字体

| 症状 | 原因 | 对策 |
|------|------|------|
| `git clone` 技能失败、默认分支是数学 | 仓库默认分支非 chinese | 显式拉 `chinese` 分支，或用分支 zip 包安装 |
| `ctex.sty` / `xecjk` / `fandol` 找不到 | 只装了基础 TeX Live | `apt install texlive-xetex texlive-lang-chinese texlive-latex-extra texlive-science` |
| MinerU 安装报 PEP 668 / `typing_extensions` 冲突 | 系统 Python 受外部管理 | 用 venv 隔离：`python -m venv .venv && .venv/bin/pip install mineru-open-sdk` |
| `Font \zf@basefont=SimSun not found` | 模板字体是 Windows 独占 | **已自动**：`ywexam.sty` 按 `SimSun → Noto Serif CJK SC → Source Han Serif SC → Songti SC` 回退，楷体同链；日志会出现 `Package ywexam Warning` 提示已回退。不要再手工改 sty 的字体名 |
| 罗马数字 Ⅰ Ⅱ Ⅲ 缺字形（字直接消失） | 西文字体/楷体无该码位 | **已自动**：`md2chinese` 把 Ⅰ-Ⅻ 转 ASCII（I/II/III）。手工写 IR 时也别用罗马数字 |
| 裸圈号 ①-⑳ 缺字形 | 同上 | **已自动**：`md2chinese` 与 `render_chinese` 都转成 `\xq{n}`（textcircled 绘制） |
| 生僻字缺字形（如「郤」） | 楷体 `AR PL KaitiM GB` 覆盖不全 | 手工：`\fullglyph{郤}` 单字切到覆盖最全的 CJK 衬线字体；或把 `Noto Serif CJK SC` 提到 `\ywkai` 候选链首位 |
| 编译报 `Bad character code (-15)` | 为罗马数字加的 `\xeCJKDeclareCharClass{CJK}{"2160-"216F}` 本身非法 | 删掉该声明（罗马数字已改 ASCII，声明无用） |

### OCR 提取与校对

| 位置/症状 | 处理 |
|------|------|
| 选项整条漏识（只剩后半句） | 有文字层的页用 `pdftotext -layout` 交叉核对；答案页是整页图片时用「视觉识别 + MinerU」双源 |
| 句尾被截断（「……有序递进的」后缺内容） | 对照原图补全；`scan_log` 查不出，只能逐题核 |
| 题号与选项挤在一行、多题合并 | **已自动**：`md2chinese` 按行首正则 + 「≥2 空格」拆行；断句选项串后紧跟题号的（`…EF 11. 下列…`）也已单独切 |
| 答案缺题号（9、11、23） | 9：空标题需人工补；11：`EF 11.` 挤行（已自动）；23：`23（60分）` 无点号（**已自动**，`RE_QNUM_SCORE`） |
| 卷首「语 文 / 2026.11 / 标题 / 副标题」重复 | **已自动**：`dedupe_leading_noise` 只清开头 6 块内的等价标题与栏目行 |
| 表格材料/表格题变成一行字 | MinerU 直出 `<table><tr><td>`，旧版把标签一剥、单元格全挤一行 | **已自动**：`extract_tables` 整块转 `tabular`（rowspan/colspan 忽略），进 IR 的 `raw` 块；表格里的圈号也转 `\xq`（否则缺字形丢字） |
| 多列表格右侧溢出（作文评分标准表） | 6 列 `p{0.15\linewidth}` 没扣 `\tabcolsep`，实测右溢 25.9pt | **已自动**：列宽改成 `\dimexpr 0.98\linewidth/N-2\tabcolsep\relax` |
| 答案长句右溢出 0.5~1cm | 半角括号/引号混排断不开 | 模板已设 `\emergencystretch=3em` 兜底（只在断不开时生效；12 套成品往返像素仍完全一致） |
| 整道题凭空消失（如第 15 题） | 题号黏在上一条注释/句子末尾：`【注】①…③土锉：…炊具。15.下列对…`，整行被当成 note 读走 | **已自动**：`split_inline_questions` 在「句末标点 + 题号 + 汉字」处切开 |
| 整道题凭空消失（如第 6 题） | 题干被排成标题行 `## 6.下列对本文…`，只认行首原始文本就漏了 | **已自动**：题号识别改用去 `#` 后的正文 |
| 答案卷 PDF 里印出 `## 15. (3分)…` | 答案题号也被排成标题行，未命中的行原样落进段落，`#` 被转义成可见字符 | **已自动**：答案侧同样用去 `#` 的正文，既识别题号也不再把 `##` 印出来 |
| `<sup>①</sup>` 等 HTML 残留 | **已自动**：去标签保留圈号（转 `\xq{}`），`<br>` 当换行 |
| 图片路径指向 `images/xxx.jpg` | 统一拷到工作目录并把 IR 里的 `path` 改成相对文件名（见 `figure` 块） |

> 原则：OCR 只能当「初稿」。定稿前逐页比对原卷——漏识/错识都不会触发任何自动告警。

双源校对的最小做法：

```bash
# 有文字层的页：本地文字层当基准（快、免费、可靠）
pdftotext -layout 原卷.pdf - | sed -n '1,120p'
# 整页图片（无文字层，如拍照答案）：MinerU 出初稿 + 视觉识别核对，不一致处回看原图
```

### LaTeX 排版

| 症状 | 原因 | 对策 |
|------|------|------|
| 诗歌（诗题+引导语+8 句）挤成一整段 | MinerU 把整块压成一个 para | 拆成 `lead` + `heading` + `poem`（每两句一行）+ `note`；渲染器会给 `[HINT] 疑似诗歌被压成一段` |
| 2 字选项占 4 行、整卷多一页 | 所有选项都走 `choices` 纵排 | 加 `choices_layout: "inline"`（`md2chinese` 对 ≤8 字选项**已自动**加），渲染为 `choicesinline`（tasks 四列） |
| 答案页出现两行重复大标题 | `\answertitle{标题}{副标题}` 两个参数都显示 | IR 里 `meta.subtitle: ""`（模板已支持空副标题，只出一行） |
| 一条答案里的「示例一 / 示例二」分不开 | `\subans{m+m}` 的参数不能含 `\par` / `\\` / 空行 | `subans` 的 `text` 传**列表**，渲染器拆成多个 `\subans`（第一个带 label，其余 label 空） |
| 题干与下面材料/断句之间多一行空白 | 主观题带 `space: true`，但题干后紧跟内容块 | **已自动**：`md2chinese` 删 `space`；手工 IR 同理会收到 `[HINT]`，确需留白写 `keep_space: true` |
| para 里「原句/改写/说明」三行挤成一段 | 行间是单换行，LaTeX 视作同段 | 行间改空行分段，或用 `subans` 列表 |
| 试卷 9 页、末页几乎空 | `\linespread{1.5}` + 11pt 放大 | 逐档压行距（见下表），**不要改 margin**（会与原卷版心错位） |
| 地图/示意图被整体推到下一页 | 图太宽放不下，与题干分页隔开 | `figure` 块 `width` 逐档缩：`0.72 → 0.52 → 0.44`；`keep: true` 加 `\nopagebreak`；OCR 直出用 `md2chinese --fig-width 0.44` |
| 原图带「学科网」等水印、字迹发虚 | 原卷截图是低清位图 | 矢量重绘（SVG）后替换：地名/番号/铁路/集结圈逐项还原，导出 2 倍 PNG，IR 里指向新图；`map_redraw.svg` 一并留在工作目录，便于复现与再改 |

行距实测（同一份无锡卷）：

| `linespread` | 试卷 | 答案 |
|---|---|---|
| 1.5（默认） | 9 页 | 4 页 |
| **1.35** | **8 页** | **4 页** |
| 1.30 | 8 页 | 3 页 |
| 1.25 | 8 页 | 3 页 |

写进 IR：`"meta": {"linespread": 1.35}`（渲染为 `\ywlinespread{1.35}`）。

### 批量流程本身

| 症状 | 原因 | 对策 |
|------|------|------|
| 批量跑到某卷卡住不动，无任何输出 | 旧版 OCR 用 `Popen(..., stdout=PIPE)` + `communicate(timeout)`：MinerU 是网络长轮询（SDK 内部 timeout=1800s），超时杀进程后孙进程仍持有管道句柄，`communicate()` 等不到 EOF，整批冻结（实测一份卡 20 分钟、进程全空闲） | 已修：子进程输出改重定向到 `*.ocr.log` 文件，`proc.wait(timeout)` + `taskkill /F /T` 硬杀进程树，超时只废该文档、批量继续 |
| 不知道卡在哪一步 | 旧版整批只在末尾打印 | 已修：每个文档打印 `[OCR] 卷名 ← pdf (model=…, timeout=…)` |
| 单份 OCR 超过时限 | 大页数/排队 | `--ocr-timeout 420`（默认 300s） |
| 卷首「阅读Ⅰ」被改成「阅读I」 | 罗马数字缺字形默认转 ASCII | 想要原字形加 `--keep-roman`（Windows 有 SimSun/Noto 时可用；Linux 上仍推荐默认） |

### 编译与验证

```bash
# 1. 编译（build.py 以「PDF 生成且日志无 ! 错误」判定成功，不看返回码）
python build.py

# 2. 日志体检：缺字形 / Overfull / ! 报错 一次看全
python "{SKILL_DIR}/scripts/quality/scan_log.py" "语文试题卷.log"
python "{SKILL_DIR}/scripts/quality/scan_log.py" . --fail-on missing   # CI 用

# 3. 逐页视觉核对（改完一定要看图，缺字形不会报错）
python "{SKILL_DIR}/scripts/quality/visual_verify.py" "语文试题卷.pdf" --dpi 150
```

- `xelatex` 因 `lastpage` 交叉引用返回非零码但 PDF 正常 → `build.py` 已按 PDF 判定，
  日志会打 `[提示] … 按成功处理`。
- 缺字形（`Missing character`）**不阻断编译**，字直接消失；`scan_log.py` 是唯一的自动检出手段。
- 压页/调图后必须逐页看：地图是否紧跟第 1 题选项、诗歌四联是否成行、短选项是否横排、
  作文题是否完整。

### 复盘验证（无锡卷，2026-11）

用上面这套流程重跑该卷 OCR md，与人工修正后的 IR 逐项比对：

| 指标 | 自动解析（`md2chinese`） | 人工修正 IR | 结论 |
|------|------|------|------|
| 题号 | 1–23 连续 | 1–23 连续 | ✅ 不再缺 9/11/23 |
| `space` 题号 | 1、4、5、8、14、16、19、20、21 | 同 | ✅ 7 道错位留白已自动去掉 |
| `choices_layout` | 仅第 18 题 inline | 同 | ✅ 短选项自动横排 |
| 选择题选项数 | 8 组 ×4 | 同 | ✅ |

行距链路同样可复现：默认 `1.5` 编出 **9 页**，`meta.linespread: 1.35` 编出 **8 页**，
`meta.subtitle: ""` 让答案卷只出一行大标题、4 页；与原交付件页数一致。

```bash
python scripts/render/md2chinese.py source/shiti_clean.md -o ir.json --kind shiti
python scripts/render/render_chinese.py ir.json -o 语文试题卷.tex --copy-sty
python scripts/quality/scan_log.py 语文试题卷.log
python build.py
```

### 真实题库抽测（2026-11，17 套）

从题库 `高中语文/` 抽 17 套不同来源的卷子跑全链路（OCR → IR → tex → PDF → 日志体检）：

| 卷 | 试题/答案页数 | 暴露的问题（已修） |
|----|------|------|
| 2605 Z20 | 10 / 7 | 表格题丢结构；题干排成 `## 6.`；题号黏在注释句末 |
| 2502深圳一模 | 10 / 4 | — |
| 2503湖北七市州 | 9 / 5 | — |
| 2504佛山二模 | 11 / 4 | HTML 对比表格 |
| 2508湖南雅礼 | 10 / 4 | 选项 8/10（OCR 缺，需人工核） |
| 2409武汉九调 | 9 / 2 | — |
| 2503泉州三模 | 10 / 3 | — |
| 2503济南一模 | 9 / 4 | — |
| 2503郑州二模 | 9 / 4 | VLM 幻觉行（已过滤） |
| 2504广州一模 | 9 / 5 | 答案评分标准 6 列表格右溢 25.9pt |
| 2504成都三诊 | 10 / 2 | 答案标题行 `## 15.` 把 `##` 印进 PDF |
| 2505义乌二模 | 9 / 4 | 三份源 PDF（答案/作文分开） |
| 2505苏锡常镇四市 | 9 / 4 | 6 列表格右溢 |
| 2506嘉兴高一期末 | 9 / 3 | 24 题结构（高一卷） |
| 2508浙江强基联盟 | 10 / 4 | — |
| 2509江苏苏州开学考 | 10 / 3 | 原卷作文题误编为 22（与上一题重号，需人工改 23） |
| 2511杭州一模 | 10 / 3 | 表格 |

- 17 套全部编译成功；24+34 份日志**无缺字形、无 Overfull、无报错**（`scan_log.py` 逐份检）。
- 试题卷题号基本都能到 23/24；答案卷缺号是原卷结构（选择题答案汇总成表、评分细则另起编号），
  只能人工对照原卷补齐，渲染器只告警不编造。
- 与题库里的旧成品页数大多一致，少数差 1 页：`space` 错位留白被自动去掉、卷首重复标题被去重、
  表格由「一行字」还原成真实表格后行高变化，属预期。

## 从成品 tex 反解 IR（回归基准）

```bash
python scripts/render/tex2chinese.py chinese-shiti.tex -o chinese-shiti.json
python scripts/render/render_chinese.py chinese-shiti.json -o out.tex --copy-sty
python tests/run_all.py --with-tex    # 12 份成品往返：页数 / 文本 / 逐页像素全同
```

`tex2chinese.py` 采取「保真优先」：能识别的块结构化，块间文本原样留在 `para` 块，不丢任何写法。

## 语文测试

`test_subject.py` / `test_chinese_naming.py` / `test_md2chinese.py` / `test_render_chinese.py` /
`test_chinese_fixtures.py` / `test_chinese_roundtrip.py` / `test_chinese_ir_fixes.py` /
`test_wuxi_regression.py`。默认走静态/结构检查；
编译门禁（`--with-tex`）会真跑 xelatex 并比对页数、文本与逐页像素。

`test_wuxi_regression.py` 用真实交付件当基准：`evals/fixtures_wuxi/` 里是同一份 OCR md 与
**人工逐条修正后的 IR**，断言自动解析已复现人工结果（题号 1–23、`space` 集合、第 18 题 inline），
`--compile` 再校验页数与交付件一致（试题 8 页 / 答案 4 页）。改 OCR 解析逻辑先跑它。
