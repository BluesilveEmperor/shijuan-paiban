#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evolve.py - 失败归因与规则候选生成

读取结构化失败记录，按 rule_id 聚合，生成规则候选清单。
候选只是「提案」，不会自动改规则——必须人工确认后编辑 rules/layout.yaml，
再用 eval_run.py --compare 做 A/B 门禁。

数据来源：
  reports/failures.json          评估运行产生的失败（eval_run.py 自动写）
  <dir>/**/failures.jsonl        真实任务运行产生的失败（logger.record_failure 写）

用法:
  python scripts/evolve.py                          # 读 reports/failures.json
  python scripts/evolve.py --from log-runtime       # 读运行日志目录
  python scripts/evolve.py --min-support 2          # 至少出现 2 次才进候选
  python scripts/evolve.py --gate                   # 额外跑一次 eval A/B 门禁

退出码:
  0  无候选 / 已生成候选
  1  --gate 时评估分数低于基线
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("[FATAL] 需要 PyYAML: pip install PyYAML")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
RULES_YAML = ROOT / "rules" / "layout.yaml"
CANDIDATES = ROOT / "rules" / "candidates.yaml"
EVAL_FAILURES = ROOT / "reports" / "failures.json"

SUGGESTION = {
    "error": "规则被违反：检查执行路径是否绕过了该规则（渲染器 / 模板 / SKILL.md 提示词），"
             "或规则取值本身已不适用",
    "warning": "规则未达标：评估阈值是否过严，或取值需要更新",
    "info": "参考性规则，考虑是否提升为 warning",
}


# ────────────────────────── 读取 ──────────────────────────

def load_eval_failures(path=EVAL_FAILURES):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    out = []
    for item in data:
        out.append({
            "rule_id": item.get("rule_id") or "",
            "symptom": item.get("detail", ""),
            "source": item.get("case", "eval"),
            "kind": item.get("kind", "eval"),
        })
    return out


def load_runtime_failures(log_dir):
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return []
    out = []
    for path in log_dir.rglob("failures.jsonl"):
        for line in path.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append({
                "rule_id": rec.get("rule_id") or "",
                "symptom": rec.get("symptom", ""),
                "source": rec.get("task") or path.parent.name,
                "kind": rec.get("stage") or "runtime",
            })
    return out


def load_rule_meta():
    if not RULES_YAML.exists():
        return {}
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8")) or {}
    return {r["id"]: r for r in data.get("rules", [])}


# ────────────────────────── 聚合 ──────────────────────────

def aggregate(failures, min_support=1):
    groups = defaultdict(lambda: {"count": 0, "sources": set(), "samples": []})
    for f in failures:
        rid = f["rule_id"] or "(未归因)"
        g = groups[rid]
        g["count"] += 1
        g["sources"].add(f["source"])
        if f["symptom"] and len(g["samples"]) < 3 and f["symptom"] not in g["samples"]:
            g["samples"].append(f["symptom"])

    meta = load_rule_meta()
    candidates = []
    for rid, g in groups.items():
        if rid != "(未归因)" and g["count"] < min_support:
            continue
        rule = meta.get(rid, {})
        severity = rule.get("severity", "error" if rid != "(未归因)" else "info")
        candidates.append({
            "rule_id": rid,
            "count": g["count"],
            "source_count": len(g["sources"]),
            "sources": sorted(g["sources"])[:8],
            "title": rule.get("title", "—"),
            "severity": severity,
            "current_value": _value_of(rule),
            "samples": g["samples"],
            "suggested_action": (
                "规则 ID 缺失：检查 validate_tex / render_tex 是否给该问题分配了 rule_id"
                if rid == "(未归因)"
                else SUGGESTION.get(severity, SUGGESTION["error"])
            ),
            "status": "pending",
        })

    candidates.sort(key=lambda c: (-c["count"], c["rule_id"]))
    return candidates


def _value_of(rule):
    if not rule:
        return ""
    rtype = rule.get("type", "scalar")
    if rtype == "decision":
        return " / ".join(f"{c['when']} → {c['value']}" for c in rule.get("cases", []))[:160]
    if rtype == "table":
        return "；".join(f"{r['k']}：{r['v']}" for r in rule.get("rows", []))[:160]
    if rtype == "list":
        return "；".join(str(x) for x in rule.get("items", []))[:160]
    return str(rule.get("value", ""))[:160]


# ────────────────────────── 输出 ──────────────────────────

def print_table(candidates, total):
    if not candidates:
        print(f"没有失败记录（共 {total} 条），无需生成候选。")
        return
    print(f"共 {total} 条失败，聚合为 {len(candidates)} 个候选：\n")
    print(f"{'规则 ID':<20} {'次数':>4} {'来源':>4}  标题")
    print("-" * 72)
    for c in candidates:
        print(f"{c['rule_id']:<20} {c['count']:>4} {c['source_count']:>4}  {c['title']}")
    print()
    for c in candidates:
        if c["rule_id"] == "(未归因)":
            continue
        print(f"[{c['rule_id']}] {c['title']}")
        print(f"  当前取值：{c['current_value']}")
        for s in c["samples"]:
            print(f"  样本：{s}")
        print(f"  建议：{c['suggested_action']}")
        print()


def write_candidates(candidates, source_label, min_support):
    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source_label,
        "min_support": min_support,
        "note": "候选仅为提案。人工确认后编辑 rules/layout.yaml，"
                "再运行 gen_rules_doc.py 与 eval_run.py --compare 做门禁。",
        "candidates": candidates,
    }
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return CANDIDATES


def run_gate():
    """A/B 门禁：当前改动必须不低于基线分。"""
    baseline = ROOT / "reports" / "baseline.json"
    if not baseline.exists():
        print("\n[WARN] 没有基线，跳过门禁（先运行 eval_run.py --baseline）")
        return 0
    print("\n运行 A/B 门禁 ...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "eval_run.py"), "--compare"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    tail = [ln for ln in (result.stdout or "").strip().split("\n") if ln][-3:]
    for ln in tail:
        print("  " + ln)
    if result.returncode != 0:
        print("  [FAIL] 门禁未通过：" + (result.stderr or "").strip()[:200])
    else:
        print("  [PASS] 门禁通过")
    return result.returncode


def main():
    ap = argparse.ArgumentParser(description="失败归因与规则候选生成")
    ap.add_argument("--from", dest="log_dir", help="运行日志目录（含 failures.jsonl）")
    ap.add_argument("--min-support", type=int, default=1, help="进入候选的最小出现次数")
    ap.add_argument("--gate", action="store_true", help="生成候选后跑 eval A/B 门禁")
    ap.add_argument("--no-write", action="store_true", help="只打印，不写 candidates.yaml")
    args = ap.parse_args()

    if args.log_dir:
        failures = load_runtime_failures(args.log_dir)
        source_label = f"runtime:{args.log_dir}"
    else:
        failures = load_eval_failures()
        source_label = "reports/failures.json"

    candidates = aggregate(failures, args.min_support)
    print_table(candidates, len(failures))

    if not args.no_write:
        path = write_candidates(candidates, source_label, args.min_support)
        print(f"候选已写入 {path}")

    if args.gate:
        return run_gate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
