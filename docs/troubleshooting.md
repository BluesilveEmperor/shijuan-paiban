# 常见问题与排障

> SKILL.md 只留最高频 4 条；编译、编码、图片、编号类问题在此查。

## LaTeX 编译

| 症状 | 原因 | 修复 |
|------|------|------|
| `Overfull \hbox` | 公式或选项超宽 | 选项改 2 列；`\dfrac` 改 `\frac` |
| `Undefined control sequence` | 缺少宏包 | 在导言区添加 `\usepackage{...}` |
| 中文不显示 | 非 ctex 模板 | 确认模板用 `ctexart` |
| 编译有 `Missing $` | 花括号不匹配 | 检查 `$...$` 配对 |
| 页数超限 | 添加了 2.5cm 间隙 | 加 `\linespread{1.05}\selectfont` |
| 解答题编号从 1 开始 | `start` 值不对 | `start = 单选题数 + 多选题数 + 填空题数 + 1` |
| 题干「如图①②③」丢字 | 默认字体缺圈号字形 | 模板已用 `newunicodechar` 映射，勿删（`STRUCT-GLYPH-001`） |
| `Missing character: There is no 郤` | 字体缺该码位，字**静默消失** | `python scripts/quality/scan_log.py *.log` 查全部缺字；语文卷用 `\fullglyph{郤}`，或把 `Noto Serif CJK SC` 提前到 `\ywkai` 候选链 |
| `Font \zf@basefont=SimSun not found` | Linux/macOS 没有 Windows 字体 | `ywexam.sty` 已按候选链自动回退（SimSun→Noto Serif→Source Han→Songti SC）；日志有 `Package ywexam Warning` 即已回退 |
| `Bad character code (-15)` | `\xeCJKDeclareCharClass` 区间写法非法 | 删掉该声明；罗马数字改 ASCII（`md2chinese` 已自动转） |
| 编译返回非零码但 PDF 正常 | `lastpage` / 交叉引用未稳定 | 以 PDF 是否生成 + 日志有无 `!` 为准（`build.py` 已内置）；连编两次 |
| `\subans` 里换行报错 / 换行被吞 | 参数是 `m` 型，不能含 `\par` `\\` 空行 | 拆成多个 `\subans`（IR 里 `subans.text` 传列表） |
| 题干与材料之间多一行空白 | 主观题 `space: true` 且题干后紧跟内容块 | 删 `space`（`md2chinese` 已自动），确需留白写 `keep_space: true` |

## 图片

| 症状 | 原因 | 修复 |
|------|------|------|
| 图片错位/消失 | 列表环境中用了 `wrapfigure` | 改用 `minipage` 左右并排 |
| 图片过大溢出 | 未限宽/限高 | 单图 `0.30\textwidth`、并排加 `height=Xcm,keepaspectratio` |
| 答案中 WMF 过多 | 未批量转换 | 用 Python + Pillow 批量渲染 600 DPI |

## Python / 环境

| 症状 | 原因 | 修复 |
|------|------|------|
| `UnicodeEncodeError` | Windows GBK 编码 | 命令前加 `PYTHONIOENCODING=utf-8` |
| Python 匹配不到 LaTeX | 字符串转义 | 用 raw string `r"\begin"` |
| 分页/定位逻辑没生效 | `\b` 被当作退格符 | 所有含 `\b` 的字符串前加 `r` |
| MinerU 解析失败 | Token / 网络 / 文件过大 | 检查配置；单文件 ≤ 200MB / 600 页 |

## 答题卡

| 症状 | 做法 |
|------|------|
| 解答题写不开 | `--pages 5` |
| 页面太空 / 太多页 | `--pages 3` 或 `--block 3` |
| 选择题挤成一坨 | `--percol 3` |
| 解析出的题量不对 | 先 `--print-spec` 核对，再用 `--single/--multi/--blanks/--solves` 覆盖 |

详见 [answer-sheet.md](answer-sheet.md)。
