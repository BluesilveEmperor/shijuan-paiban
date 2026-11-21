# 题库维护与批量整理

> 本文件收纳与「排版核心流程」无关的题库运维知识：题库结构、`build.py` 部署、整理规范、
> Windows/WSL 执行纪律。技能主流程见 [SKILL.md](../SKILL.md)。

## 题库根目录

路径不写死在代码里。优先读环境变量 `SHIJUAN_LIBRARY`，未设置时默认 `D:\Music\试题加题库`
（本机历史位置）。换机器只改环境变量，不改文档。下文用 `{题库根}` 代指该目录。

## 题库结构（截至 2026-11 快照）

```
{题库根}\
├── 高考真题（模拟）卷\        # 190 个成卷文件夹 + 5 个年份目录（2022.6–2026.6，已补 build.py）
│   └── <卷名>\               # 每卷：试题 tex + *答案.tex + Images-*\ + build.py
├── 考研数学真题卷\
│   ├── 2008年\ … 2025年\     # 18 个年份文件夹：数学（一/二/三）真题+解答共 6 tex + Images ×3 + build.py
│   ├── 2024-<大学>\          # 71 个高校文件夹：高等代数/数学分析 tex 对 + build.py
│   └── 题库\                 # 书稿工程：main.tex → chapters/2024/content → 各校 content → solutions/body
│                              # build.py 为书稿版（只编 main.tex ×3，禁止单编章节 tex）
└── 高三数学\                  # 源材料 + .math-output（MD 中间产物）
```

## build.py（两种变体）

母本：`scripts/build/build.py`（单文件自包含，只依赖标准库；`rich` / `tqdm` 可选）。

| 变体 | 位置 | 行为 |
|------|------|------|
| 通用版 | 每个试卷/高校/年份文件夹 | 编译文件夹内全部 `*.tex` ×2，统计 log 中 `^!` 行数为错误数，清理 `.aux/.log/.out`，保留 PDF |
| 书稿版 | `题库/` | 只编译 `main.tex` ×3（目录页码稳定），其余同上；根目录只有 `main.tex` 时通用版自动切换为书稿版 |

- 以脚本所在目录为工作目录，可从任意位置运行（如 `python "D:\...\某卷\build.py"`）
- `find_xelatex()` 按机器实际探测：`shutil.which` → 各盘 `texlive\<年份>\bin\windows` → MiKTeX → Linux/macOS 路径，命中即用；**不假设固定盘符/年份**
- 新整理的含 tex 文件夹都应部署一份 `build.py`。`scripts/build/finalize_paper.py` 会自动部署

## 整理规范（历次会话沉淀）

- **只动副本**：先复制到目标位置，再在副本里删除/改名；原件（桌面、源目录）永不修改
- **图片先核实再删**：全库 grep `\includegraphics` / `\graphicspath` 建引用集，未被引用的才删；`_chk`、`_tmp_*` 类临时图片目录通常整目录删
- **编译产物判定**：`pdfinfo` 看 Creator——`LaTeX with hyperref` 等即为编译产物可删；扫描原件/原始集合 PDF 保留
- **命名**：高校文件夹加年份前缀 `2024-<大学>`；按年份归组用 `<YYYY>年` 文件夹
- **全量验证**：整理完对全部文件夹并行编译，0 error 才算完成，验证产物随后清理：

  ```bash
  ls -d 20??年 | xargs -P 4 -I{} bash -c 'cd "{}" && python3 build.py'
  ```

## Windows / WSL 执行纪律

- PowerShell 会吃掉 `$`、`$(...)`、`2>/dev/null`、内联 for——**含 `$` 的命令一律写成脚本文件**
  （存 `C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage\`）再 `wsl bash <script>` /
  `wsl python3 <script>`，不要内联
- Windows 版 `xelatex.exe` 不能写 WSL `/tmp`（`-output-directory=/tmp/...` 静默失败）：就地编译再清理
- TeX Live 安装位置因机而异，先探测（`where xelatex` / `shutil.which` / 遍历各盘
  `?:\texlive\*\bin\windows\`），用探测结果，不写死路径

## 历史流水线（已归档，勿当现役）

`scripts/legacy/` 收纳了早期「Markdown 直转 LaTeX」路线与特定批次的数学批处理脚本：

| 脚本 | 原用途 |
|------|--------|
| `md2tex.py` | MD → 高考数学 LaTeX（被 `test_fixed/round2/round3` 引用） |
| `md2exam.py` | 试题 MD → 试卷 LaTeX（`md2ans` 的清洗函数来源） |
| `md2ans.py` | 答案 MD → 参考答案 LaTeX |
| `gen_paper.py` | 专题/周练/错题卷变量替换 + 编译 |
| `table_convert.py` | Markdown 表格 → LaTeX tabular |
| `pdf_extract_unwired.py` | 未接线的 PDF 提取重写版（现役为 `scripts/extract/pdf_extract.py`） |

现役路线：

- 数学：MinerU/DOCX → `paper.json` → `scripts/render/render_tex.py`
- 语文：MinerU → `scripts/render/md2chinese.py` → `scripts/render/render_chinese.py`
