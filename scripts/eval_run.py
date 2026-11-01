#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_run.py - 技能评估执行器

把 evals/fixtures/manifest.json 里的样本真正跑一遍：
  复制到工作目录 → xelatex 编译 ×2 → 解析 log → 页数 → validate_tex → 断言打分

三级评分：
  HARD   编译失败 / 结构 error → 该用例记 0（一票否决）
  STRUCT 结构断言（环境、列数、编号、答题空间、禁止项）
  LAYOUT 页数是否达标、Overfull 是否超阈值

用法:
  python scripts/eval_run.py                       # 跑全部用例
  python scripts/eval_run.py --only standard       # 只跑指定用例
  python scripts/eval_run.py --baseline            # 跑完写入 reports/baseline.json
  python scripts/eval_run.py --compare             # 与基线对比，分数下降返回 1
  python scripts/eval_run.py --keep                # 保留编译中间产物

退出码:
  0  全部通过且不低于基线
  1  存在 HARD 失败，或 --compare 时分数下降
  2  环境缺失（xelatex 不可用）
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "evals" / "fixtures"
REPORTS = ROOT / "reports"
WORK = REPORTS / "work"
BASELINE = REPORTS / "baseline.json"

sys.path.insert(0, str(SCRIPTS))
from validate_tex import TexValidator  # noqa: E402

BUILD_ARTIFACTS = (".aux", ".log", ".out", ".toc", ".synctex.gz", ".pdf")

# 断言 → 规则 ID，供 evolve.py 归因
RULE_OF_ASSERTION = {
    "envs": "STRUCT-ENV-001",
    "forbidden_envs": "STRUCT-ENV-001",
    "tasks_cols": "TASKS-COL-001",
    "examenum_start": "ENUM-START-001",
    "answer_space": "ANS-001",
    "commands": "STRUCT-BLANK-001",
    "min_images": "EXTRACT-001",
    "forbidden": "IMG-ALIGN-001",
}


# ────────────────────────── 编译 ──────────────────────────

def compile_tex(tex: Path, workdir: Path, passes=2):
    """返回 (ok, errors, overfull, pages, log_tail)"""
    errors, overfull, ok = [], 0, False
    for _ in range(passes):
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-file-line-error", tex.name],
            cwd=workdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
        ok = result.returncode == 0

    log = workdir / (tex.stem + ".log")
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    for line in log_text.split("\n"):
        if line.startswith("!"):
            errors.append(line.strip())
    overfull = len(re.findall(r"^Overfull \\[hv]box", log_text, re.M))

    pages = None
    pdf = workdir / (tex.stem + ".pdf")
    if pdf.exists() and shutil.which("pdfinfo"):
        out = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).stdout or ""
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        pages = int(m.group(1)) if m else None

    return ok and not errors, errors, overfull, pages, log_text[-800:]


# ────────────────────────── 断言 ──────────────────────────

def _tasks_cols(content):
    return sorted(int(n) for n in re.findall(r"\\begin\{tasks\}\((\d+)\)", content))


def check_expect(content, spec, tex_path):
    """返回 [(name, passed, detail, rule_id)]"""
    results = []

    def add(name, passed, detail):
        # 断言名可能带前缀（env:/cmd:/no:），按前缀归类到规则 ID
        base = name.split(":")[0] if ":" in name else name
        results.append((name, passed, detail, RULE_OF_ASSERTION.get(base, "")))

    for env in spec.get("envs", []):
        add(f"env:{env}", f"\\begin{{{env}}}" in content, f"需要环境 {env}")

    for env in spec.get("forbidden_envs", []):
        add(f"no_env:{env}", f"\\begin{{{env}}}" not in content, f"不应出现环境 {env}")

    if "tasks_cols" in spec:
        actual = _tasks_cols(content)
        expect = sorted(spec["tasks_cols"])
        add("tasks_cols", actual == expect, f"期望 {expect}，实际 {actual}")

    if "examenum_start" in spec:
        m = re.search(r"\\begin\{examenum\}\[start=(\d+)", content)
        actual = int(m.group(1)) if m else None
        add("examenum_start", actual == spec["examenum_start"],
            f"期望 start={spec['examenum_start']}，实际 {actual}")

    if "answer_space" in spec:
        cfg = spec["answer_space"]
        # 只统计实际调用，排除导言区 \newcommand{\answern}{...} 定义行
        actual = sum(
            1 for line in content.split("\n")
            if cfg["cmd"] in line and "\\newcommand" not in line
        )
        add("answer_space", actual == cfg["count"],
            f"{cfg['cmd']} 期望 {cfg['count']} 次，实际 {actual} 次")

    for cmd in spec.get("commands", []):
        add(f"cmd:{cmd}", cmd in content, f"需要命令 {cmd}")

    for bad in spec.get("forbidden", []):
        add(f"no:{bad}", bad not in content, f"不应出现 {bad}")

    if "min_images" in spec:
        n = sum(
            len(re.findall(r"\\includegraphics", line))
            for line in content.split("\n") if "\\newcommand" not in line
        )
        add("min_images", n >= spec["min_images"],
            f"期望 ≥{spec['min_images']} 张图，实际 {n} 张")

    return results


# ────────────────────────── 单用例 ──────────────────────────

def run_case(case, keep=False):
    cid = case["id"]
    workdir = WORK / cid
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    if case.get("ir"):
        # IR 用例：先用 render_tex 渲染，再走同一套检查
        ir_path = FIXTURES / case["ir"]
        tex = workdir / case.get("tex_name", "paper.tex")
        render = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_tex.py"),
             str(ir_path), "-o", str(tex)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if render.returncode != 0:
            return {
                "id": cid, "title": case.get("title", cid), "score": 0.0,
                "hard_failed": True, "compile_ok": False, "pages": None,
                "expected_pages": case.get("expected_pages"), "overfull": 0,
                "errors": [render.stderr.strip()[:300]],
                "hard_failures": [{"kind": "render", "detail": render.stderr.strip()[:300],
                                   "rule_id": ""}],
                "validator": {"error_count": 0, "warning_count": 0,
                              "rule_ids": [], "warnings": []},
                "assertions": [], "layout": [],
                "struct_ratio": 0.0, "layout_ratio": 0.0,
            }
        # 图片目录（若 IR 引用图片）
        img_src = ir_path.parent / "images"
        if img_src.is_dir():
            images_dir = json.loads(ir_path.read_text(encoding="utf-8")) \
                .get("meta", {}).get("images_dir", "media")
            shutil.copytree(img_src, workdir / images_dir)
    else:
        src = FIXTURES / case["tex"]
        src_dir = src.parent
        for item in src_dir.iterdir():
            if item.suffix in BUILD_ARTIFACTS:
                continue
            dst = workdir / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        tex = workdir / src.name

    content = tex.read_text(encoding="utf-8")

    compiled, errors, overfull, pages, log_tail = compile_tex(tex, workdir)

    # 结构验证：页数交给 LAYOUT 单独判，这里不传 expected_pages
    report = TexValidator(str(tex), is_answer=case.get("is_answer", False)).validate()

    hard_fail = []
    if not compiled:
        hard_fail.append({"kind": "compile", "detail": errors[:5] or ["编译未通过"],
                          "rule_id": "", "log": log_tail})
    for e in report["errors"]:
        hard_fail.append({"kind": "structure", "detail": e["message"],
                          "rule_id": e["rule_id"], "line": e.get("line")})

    assertions = check_expect(content, case.get("expect", {}), tex)
    struct_pass = sum(1 for _, ok, _, _ in assertions if ok)
    struct_total = len(assertions) or 1

    # LAYOUT
    layout_items = []
    exp_pages = case.get("expected_pages")
    if exp_pages is not None:
        layout_items.append(("page_count", pages == exp_pages,
                             f"期望 {exp_pages} 页，实际 {pages} 页"))
    max_overfull = case.get("max_overfull", 2)
    layout_items.append(("overfull", overfull <= max_overfull,
                         f"Overfull {overfull} 处（阈值 {max_overfull}）"))
    layout_pass = sum(1 for _, ok, _ in layout_items if ok)
    layout_total = len(layout_items) or 1

    if hard_fail:
        score = 0.0
    else:
        score = 0.6 * (struct_pass / struct_total) + 0.4 * (layout_pass / layout_total)

    if not keep:
        for f in workdir.glob("*"):
            if f.suffix in (".aux", ".log", ".out", ".toc", ".synctex.gz"):
                f.unlink(missing_ok=True)

    return {
        "id": cid,
        "title": case.get("title", cid),
        "score": round(score, 4),
        "hard_failed": bool(hard_fail),
        "compile_ok": compiled,
        "pages": pages,
        "expected_pages": exp_pages,
        "overfull": overfull,
        "errors": errors[:5],
        "hard_failures": hard_fail,
        "validator": {
            "error_count": report["error_count"],
            "warning_count": report["warning_count"],
            "rule_ids": report["rule_ids"],
            "warnings": [{"rule_id": w["rule_id"], "message": w["message"]}
                         for w in report["warnings"]],
        },
        "assertions": [
            {"name": n, "passed": ok, "detail": d, "rule_id": r}
            for n, ok, d, r in assertions
        ],
        "layout": [{"name": n, "passed": ok, "detail": d} for n, ok, d in layout_items],
        "struct_ratio": round(struct_pass / struct_total, 4),
        "layout_ratio": round(layout_pass / layout_total, 4),
    }


# ────────────────────────── 报告 ──────────────────────────

def write_markdown(scorecard, path):
    lines = [
        "# 评估报告",
        "",
        f"- 总分：**{scorecard['total_score']:.1f} / 100**",
        f"- 用例数：{scorecard['case_count']}",
        f"- HARD 失败：{scorecard['hard_fail_count']}",
        f"- 生成时间：{scorecard['timestamp']}",
        "",
        "| 用例 | 得分 | 页数 | Overfull | 结构 error | HARD |",
        "|------|------|------|----------|-----------|------|",
    ]
    for c in scorecard["cases"]:
        lines.append(
            f"| {c['id']} | {c['score']*100:.0f} | {c['pages']} "
            f"| {c['overfull']} | {c['validator']['error_count']} "
            f"| {'FAIL' if c['hard_failed'] else 'ok'} |"
        )
    lines.append("")

    failed = [c for c in scorecard["cases"] if c["score"] < 1.0]
    if failed:
        lines.append("## 未满分用例明细")
        lines.append("")
        for c in failed:
            lines.append(f"### {c['id']} — {c['title']}")
            for hf in c["hard_failures"]:
                lines.append(f"- **HARD** `{hf.get('rule_id') or '-'}` {hf['detail']}")
            for a in c["assertions"]:
                if not a["passed"]:
                    lines.append(f"- 断言 `{a['name']}` 未通过：{a['detail']}（`{a['rule_id']}`）")
            for l in c["layout"]:
                if not l["passed"]:
                    lines.append(f"- 布局 `{l['name']}` 未通过：{l['detail']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="技能评估执行器")
    ap.add_argument("--only", nargs="*", help="只跑指定用例 id")
    ap.add_argument("--baseline", action="store_true", help="写入基线")
    ap.add_argument("--compare", action="store_true", help="与基线对比，分数下降返回 1")
    ap.add_argument("--keep", action="store_true", help="保留编译中间产物")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    if not shutil.which("xelatex"):
        print("[FATAL] 找不到 xelatex，无法执行评估", file=sys.stderr)
        return 2

    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
        if not cases:
            print(f"[FATAL] 没有匹配的用例: {args.only}", file=sys.stderr)
            return 1

    REPORTS.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases:
        if not args.json:
            print(f"[..] {case['id']} ...", end="", flush=True)
        r = run_case(case, keep=args.keep)
        results.append(r)
        if not args.json:
            flag = "HARD-FAIL" if r["hard_failed"] else f"{r['score']*100:.0f}"
            print(f"\r[OK] {case['id']:<12} {flag}")

    total = sum(r["score"] for r in results) / len(results) * 100
    scorecard = {
        "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_score": round(total, 2),
        "case_count": len(results),
        "hard_fail_count": sum(1 for r in results if r["hard_failed"]),
        "cases": results,
    }

    (REPORTS / "scorecard.json").write_text(
        json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(scorecard, REPORTS / "report.md")

    # 结构化失败清单，供 evolve.py 消费
    failures = []
    for r in results:
        for hf in r["hard_failures"]:
            failures.append({
                "case": r["id"], "rule_id": hf.get("rule_id", ""),
                "kind": hf["kind"], "detail": str(hf["detail"]),
            })
        for a in r["assertions"]:
            if not a["passed"]:
                failures.append({
                    "case": r["id"], "rule_id": a["rule_id"],
                    "kind": "assertion", "detail": a["detail"],
                })
        for l in r["layout"]:
            if not l["passed"]:
                failures.append({
                    "case": r["id"], "rule_id": "PAGE-001",
                    "kind": "layout", "detail": l["detail"],
                })
    (REPORTS / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.baseline:
        BASELINE.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        if not args.json:
            print(f"\n[OK] 基线已写入 {BASELINE}")

    if args.json:
        print(json.dumps(scorecard, ensure_ascii=False, indent=2))
    else:
        print(f"\n总分 {total:.1f}/100   HARD 失败 {scorecard['hard_fail_count']}/{len(results)}")
        print(f"报告: {REPORTS / 'report.md'}")

    if args.compare:
        if not BASELINE.exists():
            print("[WARN] 没有基线文件，跳过对比（先跑 --baseline）", file=sys.stderr)
            return 0
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
        delta = total - base["total_score"]
        if not args.json:
            print(f"基线 {base['total_score']:.1f} → 当前 {total:.1f}  (Δ {delta:+.1f})")
        if delta < -0.01:
            print("[FAIL] 分数低于基线，改动被拒绝", file=sys.stderr)
            return 1

    return 1 if scorecard["hard_fail_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
