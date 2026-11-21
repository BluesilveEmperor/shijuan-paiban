# 52 份卷子 LaTeX 转排测试

用 `LaTeX/英语试卷.cls` + `LaTeX/英语试卷.sty`，对 52 份「试题.pdf」做自动转排测试。

## 目录

| 目录 | 内容 |
|---|---|
| `md/` | mineru（vlm 精准模式）OCR 出来的原始 markdown，52 份 |
| `tex/` | 转换后的 LaTeX 源 + 编译产物（`.pdf` / `.aux` / `.log`） |
| `_报告.txt` | 每份的题量 / 选项块 / 完形数 / 页数 / 编译结果 |
| `_质检.txt` | 题号连续性、环境配对、OCR 残留标记检查 |

## 复现步骤

```bash
# 1) OCR（mineru-open-sdk，token 在 ~/.mineru/config.yaml）
python ocr52.py      # 产物 md/*.md
# 2) 转换 + 编译
python batch.py      # 产物 tex/*.tex + tex/*.pdf
# 3) 质检
python qa.py
```

转换脚本 `md2tex.py` 的识别规则：

- `第×部分 …` → `\parttitle`；`第×节（…）` → `\sectitle`
- `听第 N 段材料…` → 普通段落
- `注意事项：` → `notice` 环境
- `N. …` 后接 A/B/C（D）选项 → `\question` + `choices`
  - 3 选项 → `choices(3)`（听力）
  - 4 选项 → `choices(2)`（阅读）或 `\cz`（完形，题号+四选项同行）
  - 5 个及以上 → `choices(1)`（七选五 A–G）
- `___N___` → `\blanknum{N}`（题号居中压下划线）
- 表格（markdown 或 HTML `<table>`）→ `tabular`
- `Paragraph 1: …` → `\writingpara` + 续写作答行

## 已做的前后处理

- 空位 `\blanknum{N}`：题号**居中压在下划线**上（`\underline{\makebox[2.4em]{\hfil N\hfil}}`）；
  没有题号的空位输出 `\blanknum{}`（空白下划线）。
- 表格：两列表给第二列 `p{…}` 固定宽度并加竖线；完形的 HTML 选项表还原成 `\cz` 逐行。
- OCR 把公式包成 `$…$` / `^{\text{…}}` / `\mathrm{…}` / `\%` / `\*` / `\textasciitilde` 的，一律还原成纯文本。
- 英文里的中文标点已归一：`，；：（）！？、` → 英文标点；
  贴着英文的 `“”` → 直引号 `"`，中文语境里的 `“”` 保留。

## 已知需人工核对的地方

1. 个别卷子的选项在 OCR 里就丢了/串行，需对照原 PDF 补（`_质检.txt` 里的「断档」一栏）。
2. 作文作答区行数按「每块空行 ×4」估算，与原卷未必一致。
3. 表格若原卷是跨栏宽表，需手工调列宽。

## 关于「断档 36,37,38,39,40」

新高考七选五的 5 个空是**埋在短文里**的，卷面上没有题号，所以 `_质检.txt` 里普遍显示
断档 36–40，这是正常的，不是漏题。
