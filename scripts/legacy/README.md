# scripts/legacy/ — 历史脚本（已归档）

本目录收纳两类**不再进入主流程**的代码：

1. 早期针对特定数学题库批次写的一次性批处理工具（2026-11-17 首次归档）
2. MD→LaTeX 直转路线（`md2tex` / `md2exam` / `md2ans`）与其配套生成器（2026-11-17 二次归档）

归档不等于删除：git 历史与这里的文件都保留，需要时仍可运行，但**不要在主流程里引用**。

## 为什么归档

- 硬编码个人路径 `D:\Music\试题加题库\高三数学`，换机器即失效
- 内嵌数学专用清洗逻辑（`_fix_math_spans` / `amsmath` / `\daan{}`）与 LaTeX 模板
- 部分脚本写死具体卷名（长沙一中、学军中学 2024-2025 学年 3 月月考）
- 主流程已改为「IR + 确定性渲染器」，或「语文块流 IR」

## 清单

### 数学 MD→TeX 直转（已被 IR 路线取代）

| 脚本 | 原用途 | 现状 |
|------|--------|------|
| `md2tex.py` | MD → 高考数学 LaTeX（`clean` / 表格 / 括号修复） | 仅被 `tests/legacy/` 三个回归测试引用 |
| `md2exam.py` | 试题 MD → 试卷 LaTeX | `md2ans` 复用其清洗函数 |
| `md2ans.py` | 答案 MD → 参考答案 LaTeX（`\eqimg`、graphicspath） | 已被答案模板渲染取代 |
| `gen_paper.py` | 专题/周练/错题卷变量替换 + 编译 | 变量表见 `docs/paper-variants.md` |
| `table_convert.py` | Markdown 表格 → LaTeX tabular | 功能已并入 md2tex / 渲染器 |
| `pdf_extract_unwired.py` | PDF 提取重写版（更全的 URL / 重试 / content_list） | **从未接线**；现役为 `scripts/extract/pdf_extract.py` |

### 特定批次批处理（2026-11-17 首次归档）

| 脚本 | 原用途 |
|---|---|
| `batch_convert.py` | 数学 MD→TEX 批量转换与清洗（`fix_common_issues`） |
| `batch_convert_ans.py` | 数学答案批量转换 |
| `batch_test.py` | 数学批量测试（路径由命令行传入，模板写死数学） |
| `convert_new_papers.py` | 新卷一键转换（依赖 `finish_papers` / `batch_convert`） |
| `finish_papers.py` | 数学题库批量收尾 |
| `split_combined.py` | 拆分「试题+答案」合并卷（写死长沙一中） |
| `split_xj3.py` | 拆分新课标卷（写死学军中学） |
| `build_zhuanti_zhoukan.bat` | 专题/周练卷四件套批量编译（与 `gen_paper.py` 配套） |
| `convert_docx.ps1` | Word COM 批量 DOCX→PDF，硬编码 3 份具体卷的路径 |

脚本之间的相对 import 在同目录下仍可用。

## 现役替代

| 场景 | 现役路径 |
|------|---------|
| 数学试卷 | `paper.json` → `scripts/render/render_tex.py` |
| 数学答案 | `paper.json` + `--template answer` → 同上 |
| 语文 | `scripts/render/md2chinese.py` → `scripts/render/render_chinese.py` |
| PDF 提取 | `scripts/extract/pdf_extract.py` |
| 收尾 | `scripts/build/finalize_paper.py` |

## 回滚

```bash
git mv scripts/legacy/md2tex.py scripts/render/   # 按需逐个移回
```
