#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_rules_doc.py - 从 rules/layout.yaml 生成规则文档区块

单一事实源机制：
  rules/layout.yaml  ──►  本脚本  ──►  docs/conversion-rules.md（完整规则表）
                                     ──►  SKILL.md（规则索引）
                                     ──►  rules/RULES.md（全量快照）

用法:
  python scripts/gen_rules_doc.py            # 生成并写入
  python scripts/gen_rules_doc.py --check    # 只校验，不一致返回 1
  python scripts/gen_rules_doc.py --stdout   # 打印到标准输出

退出码:
  0  成功 / 已同步
  1  文档与 YAML 不一致（--check）
  2  YAML 本身有问题（重复 ID、缺字段、check 名不存在）
"""

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("[FATAL] 需要 PyYAML: pip install PyYAML")

SKILL_DIR = Path(__file__).resolve().parent.parent
RULES_YAML = SKILL_DIR / "rules" / "layout.yaml"

BEGIN_MARK = "<!-- RULES:BEGIN scope={scope} -->"
END_MARK = "<!-- RULES:END scope={scope} -->"
FULL_BEGIN = "<!-- RULES:BEGIN full -->"
FULL_END = "<!-- RULES:END full -->"
INDEX_BEGIN = "<!-- RULES:BEGIN index -->"
INDEX_END = "<!-- RULES:END index -->"

REQUIRED_FIELDS = ("id", "scope", "title", "severity", "evidence")
VALID_SEVERITY = ("error", "warning", "info")


# ────────────────────────── 加载与校验 ──────────────────────────

def load_rules(path=RULES_YAML):
    if not path.exists():
        sys.exit(f"[FATAL] 找不到规则文件: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _known_checks():
    """从 validate_tex 读取已实现的检查名，用于交叉校验 check 字段。"""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    try:
        from validate_tex import RULE_CHECKS  # noqa: WPS433
        return set(RULE_CHECKS)
    except Exception:
        return None


def validate(data):
    """返回 (errors, warnings)"""
    errors, warnings = [], []
    rules = data.get("rules") or []
    if not rules:
        errors.append("rules 为空")
        return errors, warnings

    scopes = data.get("scopes") or {}
    seen = {}
    known = _known_checks()

    for i, rule in enumerate(rules):
        rid = rule.get("id") or f"<第 {i+1} 条无 id>"
        for field in REQUIRED_FIELDS:
            if not rule.get(field):
                errors.append(f"{rid}: 缺少必填字段 {field}")
        if rid in seen:
            errors.append(f"{rid}: ID 重复")
        seen[rid] = True

        scope = rule.get("scope")
        if scope and scope not in scopes:
            errors.append(f"{rid}: scope '{scope}' 未在 scopes 中声明")

        sev = rule.get("severity")
        if sev and sev not in VALID_SEVERITY:
            errors.append(f"{rid}: severity '{sev}' 非法（应为 {'/'.join(VALID_SEVERITY)}）")

        rtype = rule.get("type", "scalar")
        if rtype == "decision" and not rule.get("cases"):
            errors.append(f"{rid}: type=decision 但缺少 cases")
        if rtype == "table" and not rule.get("rows"):
            errors.append(f"{rid}: type=table 但缺少 rows")
        if rtype == "list" and not rule.get("items"):
            errors.append(f"{rid}: type=list 但缺少 items")
        if rtype == "scalar" and not rule.get("value"):
            errors.append(f"{rid}: type=scalar 但缺少 value")

        chk = rule.get("check")
        if chk and known is not None and chk not in known:
            warnings.append(f"{rid}: check '{chk}' 在 validate_tex 中未实现（该规则暂无自动校验）")

    return errors, warnings


# ────────────────────────── 渲染 ──────────────────────────

def _cell(text):
    """Markdown 表格单元格转义。"""
    return str(text).replace("|", "\\|").replace("\n", " ")


def _rule_value(rule):
    rtype = rule.get("type", "scalar")
    if rtype == "decision":
        return "<br>".join(
            f"{_cell(c['when'])} → {_cell(c['value'])}" for c in rule["cases"]
        )
    if rtype == "table":
        return "<br>".join(f"{_cell(r['k'])}：{_cell(r['v'])}" for r in rule["rows"])
    if rtype == "list":
        return "；".join(_cell(x) for x in rule["items"])
    return _cell(rule.get("value", ""))


def _rule_note(rule):
    """禁止项 + 证据，作为表格里的补充说明。"""
    bits = []
    forbidden = rule.get("forbidden") or []
    if forbidden:
        bits.append("禁止：" + "、".join(f"`{x}`" if x.startswith("\\") else x for x in forbidden))
    if rule.get("evidence"):
        bits.append(rule["evidence"])
    return "<br>".join(bits)


def render_scope(data, scope):
    """渲染单个 scope 的规则表。"""
    title = (data.get("scopes") or {}).get(scope, scope)
    rows = [r for r in data["rules"] if r.get("scope") == scope]
    if not rows:
        return ""
    out = [f"### {title}", "", "| ID | 规则 | 取值 | 说明 |", "|----|------|------|------|"]
    for r in rows:
        out.append(
            f"| `{r['id']}` | {_cell(r['title'])} | {_rule_value(r)} | {_rule_note(r)} |"
        )
    out.append("")
    return "\n".join(out)


def render_full(data):
    """全量规则区块（按 scopes 声明顺序）。"""
    parts = [
        "<!-- 本区块由 scripts/gen_rules_doc.py 从 rules/layout.yaml 生成，请勿手改 -->",
        "",
    ]
    for scope in (data.get("scopes") or {}):
        block = render_scope(data, scope)
        if block:
            parts.append(block)
    parts.append(
        f"> 规则版本 v{data.get('version')}，更新于 {data.get('updated')}。"
        "修改规则请编辑 `rules/layout.yaml` 后运行 `python scripts/gen_rules_doc.py`。"
    )
    return "\n".join(parts)


def render_index(data):
    """紧凑索引，供 SKILL.md 使用。"""
    out = [
        "<!-- 本区块由 scripts/gen_rules_doc.py 从 rules/layout.yaml 生成，请勿手改 -->",
        "",
        "| ID | 规则 | 取值 |",
        "|----|------|------|",
    ]
    for r in data["rules"]:
        out.append(f"| `{r['id']}` | {_cell(r['title'])} | {_rule_value(r)} |")
    out.append("")
    out.append(
        "> 完整规则（含禁止项与证据）见 "
        "[docs/conversion-rules.md](docs/conversion-rules.md)，"
        "机器可读源见 [rules/layout.yaml](rules/layout.yaml)。"
    )
    return "\n".join(out)


# ────────────────────────── 注入 ──────────────────────────

def inject(text, begin, end, content):
    """把 content 注入到 begin/end 标记之间；标记不存在时返回 None。"""
    i = text.find(begin)
    if i < 0:
        return None
    j = text.find(end, i)
    if j < 0:
        return None
    return text[: i + len(begin)] + "\n" + content + "\n" + text[j:]


def sync_file(path, begin, end, content, check_only):
    """返回 (状态, 说明)。状态 ∈ {'updated', 'clean', 'missing-marker', 'not-found'}"""
    if not path.exists():
        return "not-found", f"{path} 不存在"
    original = path.read_text(encoding="utf-8")
    updated = inject(original, begin, end, content)
    if updated is None:
        return "missing-marker", f"{path} 缺少标记 {begin}"
    if updated == original:
        return "clean", f"{path} 已同步"
    if check_only:
        return "out-of-sync", f"{path} 与 rules/layout.yaml 不一致"
    path.write_text(updated, encoding="utf-8")
    return "updated", f"{path} 已更新"


# ────────────────────────── 主流程 ──────────────────────────

def main():
    ap = argparse.ArgumentParser(description="从 rules/layout.yaml 生成规则文档")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    ap.add_argument("--stdout", action="store_true", help="打印完整规则到标准输出")
    args = ap.parse_args()

    data = load_rules()

    errors, warnings = validate(data)
    for w in warnings:
        print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        return 2

    full = render_full(data)
    index = render_index(data)

    if args.stdout:
        print(full)
        return 0

    results = []

    # 1) 全量快照：rules/RULES.md 整篇生成
    snapshot = SKILL_DIR / "rules" / "RULES.md"
    snapshot_body = (
        "# 排版规则全量快照\n\n"
        "> 本文件由 `scripts/gen_rules_doc.py` 自动生成，请勿手改。\n"
        "> 修改规则请编辑 `rules/layout.yaml`。\n\n" + full + "\n"
    )
    if args.check:
        old = snapshot.read_text(encoding="utf-8") if snapshot.exists() else ""
        results.append(("clean" if old == snapshot_body else "out-of-sync",
                        f"{snapshot} {'已同步' if old == snapshot_body else '与 rules/layout.yaml 不一致'}"))
    else:
        snapshot.write_text(snapshot_body, encoding="utf-8")
        results.append(("updated", f"{snapshot} 已更新"))

    # 2) 完整规则表注入 docs/conversion-rules.md
    results.append(sync_file(
        SKILL_DIR / "docs" / "conversion-rules.md",
        FULL_BEGIN, FULL_END, full, args.check,
    ))

    # 3) 紧凑索引注入 SKILL.md
    results.append(sync_file(
        SKILL_DIR / "SKILL.md",
        INDEX_BEGIN, INDEX_END, index, args.check,
    ))

    bad = False
    for status, msg in results:
        if status in ("out-of-sync", "missing-marker", "not-found"):
            bad = True
            print(f"[FAIL] {msg}")
        elif status == "updated":
            print(f"[OK]   {msg}")
        else:
            print(f"[OK]   {msg}")

    if bad:
        print("\n修复：运行 python scripts/gen_rules_doc.py（不带 --check）重新生成。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
