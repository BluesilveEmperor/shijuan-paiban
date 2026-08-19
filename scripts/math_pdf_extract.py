#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MinerU SDK PDF -> Markdown + images extractor.

内嵌于 geo-paper-format skill，用于 PDF 格式的地理试卷提取。
CLI 接口与 math-reference-read 保持一致，SKILL.md 工作流 1-B 可直接调用：
  python math_pdf_extract.py <pdf> --output-dir ./geo-output --language ch
"""
import argparse, os, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_token():
    """从 ~/.mineru/config.yaml 读取 token 与可选 model。"""
    cfg = Path.home() / ".mineru" / "config.yaml"
    if not cfg.exists():
        sys.exit("[ERROR] ~/.mineru/config.yaml 不存在。获取 token: https://mineru.net/apiManage/token")
    txt = cfg.read_text(encoding="utf-8")
    data = yaml.safe_load(txt) if yaml else None
    if not isinstance(data, dict):
        # pyyaml 缺失时的简易行解析降级
        data = {}
        for line in txt.splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip("'\"")
    tok = data.get("token")
    if not tok:
        sys.exit("[ERROR] ~/.mineru/config.yaml 中 token 为空")
    return tok, data.get("model")


def main():
    p = argparse.ArgumentParser(description="MinerU SDK PDF -> Markdown + images")
    p.add_argument("pdf", help="PDF 文件路径")
    p.add_argument("--output-dir", default="./geo-output")
    p.add_argument("--model", default=None, help="pipeline / vlm / html，默认 vlm")
    p.add_argument("--ocr", action="store_true", help="扫描件启用 OCR")
    p.add_argument("--language", default="en", help="文档语言：英文=en，中文=ch")
    p.add_argument("--no-formula", action="store_true", help="禁用公式识别")
    p.add_argument("--no-table", action="store_true", help="禁用表格识别")
    p.add_argument("--pages", default=None, help="页码范围，如 1-10,15")
    a = p.parse_args()

    from mineru import MinerU

    token, cfg_model = load_token()
    model = a.model or cfg_model or "vlm"

    src = str(Path(a.pdf).resolve())
    out = Path(a.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 提取 {os.path.basename(src)}  model={model} lang={a.language}")
    cli = MinerU(token=token)
    kw = dict(model=model, ocr=a.ocr, language=a.language,
              formula=not a.no_formula, table=not a.no_table, timeout=1800)
    if a.pages:
        kw["pages"] = a.pages
    res = cli.extract(src, **kw)

    stem = Path(src).stem

    # ── Markdown ──
    md = getattr(res, "markdown", None) or getattr(res, "md", None) or ""
    md_path = out / f"{stem}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"[OK] markdown -> {md_path} ({len(md)} chars)")

    # ── 图片 ──
    imgs = getattr(res, "images", None) or []
    n = 0
    if imgs:
        img_dir = out / stem / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(imgs, dict):
            iterable = imgs.items()
            for name, data in iterable:
                if not data:
                    continue
                (img_dir / os.path.basename(name)).write_bytes(data)
                n += 1
        else:
            for im in imgs:
                name = (getattr(im, "name", None)
                        or getattr(im, "filename", None)
                        or f"img_{n}.png")
                data = getattr(im, "data", None) or getattr(im, "content", None)
                if data is None:
                    continue
                (img_dir / os.path.basename(name)).write_bytes(data)
                n += 1
        print(f"[OK] {n} 张图片 -> {img_dir}")
    else:
        print("[INFO] 无独立图片对象返回")

    print(f"[DONE] {stem}")


if __name__ == "__main__":
    main()
