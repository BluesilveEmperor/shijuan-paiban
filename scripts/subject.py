#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subject.py — 学科差异的唯一配置入口

把原先散落在各脚本里的学科硬编码（答题卡命名、MD 输出目录、日志分支、
默认卷名、必备宏包）收敛到本文件 + 仓库根 ``shijuan.config.yaml``。

学科解析优先级（高 → 低）::

    1. 环境变量 SHIJUAN_SUBJECT（math / chinese）
    2. 仓库根 shijuan.config.yaml 的 ``subject:`` 字段
    3. "math"

用法::

    from subject import get_profile, get, sheet_stem

    get("md_output_dir")            # -> "math-output"
    get_profile("chinese")["name"]  # -> "语文"
    sheet_stem("2611数学卷-嘉兴一模", "a4")

只依赖标准库；PyYAML 缺失时降级为顶层 ``key: value`` 行解析。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "shijuan.config.yaml"

# 学科档案。新增学科只需在此加一项，并在 shijuan.config.yaml 里改 subject。
PROFILES = {
    "math": {
        "name": "数学",
        "md_output_dir": "math-output",       # MinerU 提取中间产物目录
        "log_branch": "log_runtime_math",     # 日志上传分支
        "paper_title": "数学试卷",             # render_tex 默认卷名
        "sheet_prefix_word": "数学",
        # 源卷「2611数学卷-嘉兴一模」→ 答题卡「2611数学答题卡（A4）-嘉兴一模」
        "sheet_prefix_re": r"^(?P<yy>\d{0,4})数学(?:卷|试卷)[-—](?P<exam>.+)$",
        "sheet_named": "{yy}{word}{kind}（{side}）-{exam}",
        # validate_tex 的 required_packages 检查项
        "required_packages": ("amsmath", "graphicx", "tasks", "enumitem", "fancyhdr"),
        "required_packages_answer": ("amsmath", "graphicx", "enumitem", "fancyhdr", "xcolor"),
        # match_paper 排除模板/衍生文件时用的文件名特征
        "template_hints": ("template", "gaokao"),
        # 解答题（长答题）列表环境；None 表示该学科不强制使用自定义环境
        "long_answer_env": "examenum",
        # 答题卡小节题型判定关键词（顺序：multi → single → fill → solve）
        "section_keywords": {
            "multi": ("多选", "多项选择", "不定项", "多项符合", "多个选项"),
            "single": ("单选", "选择"),
            "fill": ("填空",),
            "solve": ("解答", "计算", "证明", "综合"),
        },
    },
    "chinese": {
        "name": "语文",
        "md_output_dir": "chinese-output",
        "log_branch": "log_runtime_chinese",
        "paper_title": "语文试卷",
        "sheet_prefix_word": "语文",
        "sheet_prefix_re": r"^(?P<yy>\d{0,4})语文(?:卷|试卷)[-—](?P<exam>.+)$",
        "sheet_named": "{yy}{word}{kind}（{side}）-{exam}",
        # 语文卷不用 amsmath/tasks；ctex 由模板提供，这里只做存在性提示
        "required_packages": ("ctex", "graphicx", "enumitem", "fancyhdr", "lastpage"),
        "required_packages_answer": ("ctex", "graphicx", "enumitem", "fancyhdr",
                                     "xcolor", "lastpage"),
        "template_hints": ("template", "chinese"),
        # 语文长答题列表尚未定义专用环境，不强制（校验器据此跳过 STRUCT-ENV-002）
        "long_answer_env": None,
        # 语文小节标题形如「一、现代文阅读Ⅰ」「二、古代诗文阅读」；
        # 注意：同一小节常混合选择/主观题，答题卡分节仍需专门处理（已知限制）
        "section_keywords": {
            "multi": ("多选", "多项选择", "不定项"),
            "single": ("选择题",),
            "fill": ("默写", "名篇名句", "名句"),
            "solve": ("阅读", "语言文字运用", "诗歌", "文言文", "鉴赏", "简答"),
        },
    },
}

DEFAULT_SUBJECT = "math"
_cache: dict[str, str] = {}


def _parse_config(path: Path) -> dict:
    """读取 shijuan.config.yaml；无 PyYAML 时只解析顶层 key: value。"""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - 缺 PyYAML 或格式异常都走降级
        data = {}
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" in line and not line.startswith(("-", " ")):
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip().strip("'\"")
        return data


def resolve_subject(explicit: str | None = None) -> str:
    """按 优先级 确定当前学科 key；未知学科名直接报错，避免静默走数学默认值。"""
    if explicit is None:
        explicit = os.environ.get("SHIJUAN_SUBJECT") or _cache.get("config_subject")
    if explicit is None:
        if "config_subject" not in _cache:
            cfg = _parse_config(CONFIG_PATH)
            _cache["config_subject"] = str(cfg.get("subject") or DEFAULT_SUBJECT).strip()
        explicit = _cache["config_subject"]

    key = str(explicit).strip().lower() or DEFAULT_SUBJECT
    if key not in PROFILES:
        raise ValueError(
            f"未知学科 {key!r}，可选：{', '.join(sorted(PROFILES))}"
            f"（由 SHIJUAN_SUBJECT 或 {CONFIG_PATH.name} 指定）"
        )
    return key


def get_profile(subject: str | None = None) -> dict:
    """返回学科档案的浅拷贝（调用方可随意改字段名而不会污染全局）。"""
    prof = dict(PROFILES[resolve_subject(subject)])
    prof["subject"] = resolve_subject(subject)
    return prof


def get(key: str, default=None, subject: str | None = None):
    """取单个配置项。"""
    return get_profile(subject).get(key, default)


def sheet_stem(paper_stem: str, layout: str, suffix: str = "答题卡",
               subject: str | None = None) -> str:
    """由试卷名推导答题卡文件名（不含扩展名），layout ∈ {a4, a3}。

    数学分支行为与历史实现逐字节一致：
      2611数学卷-嘉兴一模 → 2611数学答题卡（A4）-嘉兴一模
      无前缀时回退 <卷名>-答题卡-A4
    """
    prof = get_profile(subject)
    side = "A4" if layout == "a4" else "A3"
    m = re.match(prof["sheet_prefix_re"], paper_stem)
    if m and m.group("exam"):
        return prof["sheet_named"].format(
            yy=m.group("yy"), word=prof["sheet_prefix_word"],
            kind=suffix, side=side, exam=m.group("exam"))
    return f"{paper_stem}-{suffix}-{side}"


def reset_cache() -> None:
    """清空已读配置（测试切学科时用）。"""
    _cache.clear()
