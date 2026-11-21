#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_english_roundtrip.py — 英语 IR 往返门禁：tex → english.json → tex

两种模式：

  默认      52 套成品 tex 全部做逐字节往返比对 + IR 结构断言；A 层 5 套 IR 基准文件一致
  --compile 额外用 XeLaTeX 编译 A 层 5 套的渲染结果，验证生成 tex 可独立编译

A 层干净卷（严格排除 OCR 硬异常）：1、11、13、15、29，见
docs/english-corpus-findings.md 第 6.2 节。
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "render"))

import render_english  # noqa: E402
import tex2english  # noqa: E402

FIX = ROOT / "evals" / "fixtures_english"
TEX_DIR = FIX / "tex"
IR_DIR = FIX / "ir"
CLEAN = (1, 11, 13, 15, 29)
FAILS = []


def parse(tex_path):
    return tex2english.parse_tex(tex_path.read_text(encoding="utf-8"),
                                 source=tex_path.name)


def check_static():
    files = sorted(TEX_DIR.glob("*.tex"))
    if len(files) != 52:
        FAILS.append(f"英语样本数应为 52，实际 {len(files)}")
    for tex in files:
        src = tex.read_text(encoding="utf-8")
        ir = parse(tex)
        gen, report = render_english.render_paper(ir)
        if gen != src:
            FAILS.append(f"{tex.name} 往返不是逐字节一致")
        meta = ir["meta"]
        if meta.get("subject") != "english":
            FAILS.append(f"{tex.name} meta.subject 错误")
        if meta.get("variant") not in ("full", "no_listening"):
            FAILS.append(f"{tex.name} variant 错误: {meta.get('variant')}")
        n_q = sum(1 for b in ir["blocks"] if b["type"] == "question")
        if n_q != meta.get("question_count"):
            FAILS.append(f"{tex.name} question 块数不一致 {n_q}/{meta.get('question_count')}")
        if not any(b["type"] == "choices" for b in ir["blocks"]):
            FAILS.append(f"{tex.name} 没有 choices 块")
        if not any(b["type"] == "cloze" for b in ir["blocks"]):
            FAILS.append(f"{tex.name} 没有 cloze 块")

    # A 层 IR 基准文件必须与解析器输出一致（防止 schema 漂移无人察觉）
    for idx in CLEAN:
        tex = next((p for p in files if p.name.startswith(f"{idx:02d}_")), None)
        if tex is None:
            FAILS.append(f"A 层 #{idx} 找不到源 tex")
            continue
        ir_path = IR_DIR / f"{tex.stem}.english.json"
        if not ir_path.is_file():
            FAILS.append(f"{ir_path.name} 缺失（先跑 tex2english.py）")
            continue
        saved = json.loads(ir_path.read_text(encoding="utf-8"))
        if saved != parse(tex):
            FAILS.append(f"{ir_path.name} 与当前解析器输出不一致")

    print(f"[PASS] 52 套 tex → IR → tex 逐字节一致；A 层 {len(CLEAN)} 份 IR 基准匹配"
          if not FAILS else "[FAIL] 静态往返检查有失败")


def check_compile():
    xelatex = shutil.which("xelatex")
    if not xelatex:
        print("[SKIP] 未找到 XeLaTeX，跳过英语往返编译")
        return
    files = sorted(TEX_DIR.glob("*.tex"))
    for idx in CLEAN:
        tex = next((p for p in files if p.name.startswith(f"{idx:02d}_")), None)
        if tex is None:
            continue
        gen, _ = render_english.render_paper(parse(tex))
        with tempfile.TemporaryDirectory(prefix="eng-roundtrip-") as td:
            work = Path(td)
            for name in ("英语试卷.cls", "英语试卷.sty"):
                shutil.copy2(ROOT / "templates" / "english" / name, work / name)
            rendered = work / "gen.tex"
            rendered.write_text(gen, encoding="utf-8")
            ok = True
            for _ in range(2):
                rc = subprocess.run(
                    [xelatex, "-interaction=nonstopmode", rendered.name],
                    cwd=str(work), capture_output=True, text=True,
                    encoding="utf-8", errors="replace").returncode
                if rc != 0:
                    ok = False
                    break
            pdf = work / "gen.pdf"
            if not ok or not pdf.is_file():
                FAILS.append(f"A 层 #{idx} 渲染结果编译失败")
            else:
                print(f"[PASS] A 层 #{idx} 渲染结果编译通过（{pdf.stat().st_size} bytes）")


def main():
    check_static()
    if "--compile" in sys.argv:
        check_compile()
    if FAILS:
        for f in FAILS:
            print("FAIL", f)
        return 1
    print("英语 IR 往返回归通过"
          + ("（含编译）" if "--compile" in sys.argv else "（静态）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
