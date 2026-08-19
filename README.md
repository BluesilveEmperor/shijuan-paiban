# 地理试卷 → LaTeX 自动排版

将地理试卷文件（DOCX 或 PDF）自动转换为 LaTeX 排版并编译为 PDF 的 Skill。

## 核心特性

- **双格式输入**：支持 DOCX 和 PDF 两种输入格式，自动识别分流
- **DOCX 通道**：pandoc 提取文本 + 解包取图片 + WMF 批量转 PNG
- **PDF 通道**：基于 MinerU SDK 提取 Markdown + 图片，公式已为 LaTeX 格式可直接引用
- **自动模板选择**：根据文件名是否含"答案"自动选用试题模板或答案模板
- **三段式试题匹配**：答案文档自动查找同目录对应的 `.tex` 试题文件
- **教师版生成**：试题文档自动生成解答题分页的教师版
- **图片智能处理**：WMF→PNG 批量转换（DOCX）、wrapfigure/minipage 环绕排版、`\graphicspath` 自动对齐
- **编译验证**：自动 XeLaTeX 编译、Overfull 检测、页数验证

## 快速开始

### 前置条件

**通用依赖：**
- XeLaTeX（TeX Live / MiKTeX）
- Python 3.8+
- pandoc

**DOCX 输入额外依赖：**
- Pillow（`pip install Pillow`）— WMF→PNG 转换
- docx skill（解包脚本）

**PDF 输入额外依赖：**
- MinerU SDK（`pip install mineru-open-sdk`）
- MinerU API Token（[获取地址](https://mineru.net/apiManage/token)）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/BluesilveEmperor/shijuan-paiban.git
cd shijuan-paiban
git checkout geogebra

# 2. 安装通用依赖
pip install Pillow

# 3. 如需 PDF 输入支持
pip install mineru-open-sdk
mkdir -p ~/.mineru
echo "token: '你的API密钥'" > ~/.mineru/config.yaml
```

> **注意**：MinerU API Token 请前往 https://mineru.net/apiManage/token 注册获取。

## 使用方法

### DOCX 输入

```bash
# 排版 DOCX 试题文档
"帮我把 2025年高考地理真题.docx 排版成 LaTeX"

# 排版 DOCX 答案文档（文件名含"答案"自动识别）
"排版这个地理答案文档 2025地理-答案.docx"
```

**流程**：pandoc 提取 → 解包取图片/WMF→PNG → 模板排版 → 编译验证

### PDF 输入

```bash
# 排版 PDF 试卷
"帮我把 2025年高考地理真题.pdf 排版成 LaTeX"

# 排版 PDF 答案文档
"排版这个地理pdf 答案 2025地理-答案.pdf"
```

**流程**：检查 MinerU 配置 → MinerU SDK 提取 Markdown+图片 → 模板排版 → 编译验证

## 工作流概览

```
用户提供文件路径
    ↓
识别文件类型 (.docx / .pdf)
    ├── .docx → pandoc 提取结构 → 解包取图片/WMF→PNG
    └── .pdf  → 检查 MinerU SDK → MinerU 提取 Markdown+图片
    ↓
读模板 → 知能力（自动选择试题/答案模板）
    ↓
写 LaTeX → 逐题转换
    ├── 答案文档 → 跳过教师版
    └── 试题文档 → 生成教师版（解答题分页）
    ↓
编译 → 验证（XeLaTeX × 2）
    ↓
清理辅助文件
```

## 模板系统

### 自动模板选择

| 条件 | 使用模板 |
|------|---------|
| 文件名含"答案" | `gaokao-geo-answer-template.tex`（答案模板） |
| 明显是地理试卷 | `gaokao-geo-template.tex`（试题模板） |
| 用户明确指定 | 按指定模板 |

### 内嵌模板

两个模板已内嵌在 SKILL.md 中，无需额外文件：

- **gaokao-geo-template.tex**：地理试卷模板，支持学生版/教师版
  - 12pt + 2.5cm 边距、tasks 选择题环境、examenum 大题编号
  - 自定义命令：`\blank`、`\geoimg` 等

- **gaokao-geo-answer-template.tex**：地理参考答案模板
  - `\daan{...}` 答案、`\jieti` 解析、`\xijie` 详解
  - `\xiaoI`/`\xiaoII` 小问详解、`\eqimg` 公式图片

## 图片处理

### DOCX 输入

| 场景 | 处理方式 |
|------|---------|
| 试题文档图片 | 解包到 `media/` 目录 |
| 答案文档 PNG | 复制到 `Images-{文件名}/` 目录 |
| 答案文档 WMF | 批量转 PNG（600 DPI），保存到 `Images-{文件名}/` |
| 列表环境外图片 | `wrapfigure` 右侧环绕 |
| 列表环境内图片 | `minipage` 左右并排 |

### PDF 输入

MinerU SDK 自动提取图片，保存到输出目录。图片目录命名为 `Images-{PDF文件名}`。

## 三段式试题匹配

答案文档自动查找同目录对应的 `.tex` 试题文件：

1. **精确剥离**：移除 `-答案`/`_答案`/`答案` 等后缀后匹配 `.tex`
2. **公共前缀匹配**：计算与同目录 `.tex` 文件的最长公共前缀（≥3字符）
3. **回退**：以上均失败时从输入文件中提取题目文本

## 答案文档 vs 试题文档

| 特性 | 试题文档 | 答案文档 |
|------|---------|---------|
| 模板 | gaokao-geo-template.tex | gaokao-geo-answer-template.tex |
| 教师版 | 生成（解答题分页） | 不生成 |
| 选项排版 | `tasks` 环境 | `\eqimg` 或 LaTeX 公式 |
| 答案结构 | 无 | `\daan` → `\jieti` → `\xijie` |
| 页数控制 | 严格匹配标注页数 | 无限制 |

## 常见问题

| 症状 | 修复 |
|------|------|
| Overfull \hbox | 选项改 2 列；`\dfrac` 改 `\frac`；缩短公式 |
| 图片错位/消失 | 列表环境中改用 `minipage` 方案 |
| 页数超限 | 加 `\linespread{1.05}\selectfont` 压缩行距 |
| MinerU 解析失败（PDF） | 检查 Token；文件 ≤ 200MB/600 页；扫描件加 `--ocr` |
| UnicodeEncodeError（Windows） | 加 `PYTHONIOENCODING=utf-8` 前缀 |
| 中文不显示 | 确认模板用 `ctexart` |

## MinerU API 限制（PDF 输入）

| 限制项 | 数值 |
|--------|------|
| 单文件大小 | ≤ 200MB |
| 单文件页数 | ≤ 600 页 |
| 日限额（免费版） | 2000 页 |
| 上传链接有效期 | 24 小时 |
| 解析结果保存 | 30 天 |

## 文件结构

```
shijuan-paiban/ (geogebra 分支)
├── SKILL.md               # Skill 主文档（完整工作流 + 嵌入式模板）
├── README.md              # 本文件
├── references/
│   ├── latex-pipeline-reference.md    # 流水线步骤详细规则
│   ├── 01-clean-exam.md               # 原有清洗步骤规则
│   ├── 02-tag-structure.md            # 原有结构打标规则
│   ├── 03-tag-placeholders-anchor.md  # 原有占位符规则
│   ├── 04-tag-images-anchor.md        # 原有图片理解规则
│   ├── 05-map-images.md               # 原有图片映射规则
│   └── 06-typeset-exam.md             # 原有排版规则
├── scripts/
│   └── math_pdf_extract.py  # MinerU SDK PDF→Markdown 提取脚本
├── templates/
│   ├── gaokao-geo-template.tex        # 地理试卷 LaTeX 模板
│   └── gaokao-geo-answer-template.tex # 地理参考答案 LaTeX 模板
└── ...
```

## 依赖 Skill

- **docx**：DOCX 解包脚本（`scripts/office/unpack.py`）
- **PDF 提取脚本已内嵌**：`scripts/math_pdf_extract.py`（封装 MinerU SDK）

## 相关链接

- [MinerU 官网](https://mineru.net)
- [shijuan-paiban 主仓库](https://github.com/BluesilveEmperor/shijuan-paiban)

## 许可证

MIT License
