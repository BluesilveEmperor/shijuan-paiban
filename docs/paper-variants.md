# 专题卷 / 周练卷 / 错题卷

> 三套「四件套 / 三件套」模板的变量表。模板在 `templates/math/`，
> `manifest.json` 的 `zhuanti` / `zhoukan` / `cuoti` 条目列出文件清单。

## 模板选择

| 文件名特征 | 模板系列 | 版本 |
|-----------|---------|------|
| 含"专题"/"专项" | `zhuanti_*.tex` | 四件套（student/teacher/onepage/content） |
| 含"周练"/"周测"/"周考" | `zhoukan_*.tex` | 四件套 |
| 含"错题"/"纠错"/"订正" | `cuoti_*.tex` | 三件套（student/teacher/content） |

`*_content.tex` 是唯一的题目正文，被 student / teacher / onepage 三个 wrapper `\input` 共享；
变量通过 `\providecommand` 定义，wrapper 可先设值再引入 content。

## 专题卷变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `zhuantiName` | 专题名称 | 必填 |
| `zhuantiGrade` | 年级 | 必填 |
| `zhuantiDate` | 日期 | 必填 |
| `tierNames` | 分层名称 | 基础巩固,能力提高,拔高挑战 |
| `saqItemSep` | 解答题间距 | 2.5cm |

## 周练卷变量

| 变量 | 说明 | 备注 |
|------|------|------|
| `zhoukanMode` | 模式 | limited（限时 30-45min）/ homework |
| `mcqCount` | 单选题数量 | **必须指定** |
| `msqCount` | 多选题数量 | **必须指定** |
| `blankCount` | 填空题数量 | **必须指定** |
| `saqCount` | 解答题数量 | **必须指定** |

## 错题卷变量

| 变量 | 说明 |
|------|------|
| `cuotiTitle` | 标题 |
| `cuotiSource` | 错题来源 |
| `cuotiDate` | 日期 |

错题卷结构（每道错题）：题目 → 错误解法（灰色）→ 错因分析（红，教师版可见）→
正确解法（绿，教师版可见）→ 方法总结（棕，教师版可见）→ 同类变式（青，教师版可见）。

## 生成方式

变量替换脚本 `gen_paper.py` 已归档到 `scripts/legacy/`（一次性批次工具，硬编码较多）。
常规做法是把 `*_content.tex` 的 `{{{var}}}}` 占位符替换后，用通用版 `build.py` 编译
student / teacher / onepage 三个 wrapper。
