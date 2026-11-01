#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pdf_extract.py — PDF → Markdown 提取脚本（MinerU Open SDK 封装）

从零实现，封装 ``mineru-open-sdk``（MinerU 云端 API），把单个 PDF 解析为
Markdown + 图片，供后续 MD→TeX 流水线使用。

--------------------------------------------------------------------------
CLI
--------------------------------------------------------------------------
    python pdf_extract.py <pdf路径> --output-dir <输出目录> \
        [--language ch] [--model vlm] [--ocr] [--pages 1-10] [--timeout 1800]

参数：
    <pdf路径>          必填，本地 PDF 文件路径（也支持 http(s) URL）
    --output-dir DIR   输出目录（默认 ./math-output）
    --language LANG    文档语言，默认 ch（中文试卷）。英文设 en
    --model MODEL      pipeline | vlm | html（默认取 ~/.mineru/config.yaml 的
                       model 字段，缺省 vlm）
    --ocr              强制启用 OCR（扫描件）。不加则由服务端自动判定
    --pages RANGE      页码范围，如 "1-10" 或 "1-10,15"（默认整篇）
    --timeout SEC      单文件轮询超时秒数（默认 1800）
    --retries N        网络/任务失败时的额外重试次数（默认 1）
    --token TOKEN      MinerU API token（默认取环境变量 MINERU_TOKEN，
                       再取 ~/.mineru/config.yaml 的 token 字段）
    --config PATH      自定义 MinerU 配置文件路径
    --extra-formats ...额外的导出格式（逗号分隔），透传给 SDK

--------------------------------------------------------------------------
输出约定（后续流水线依赖，勿改）
--------------------------------------------------------------------------
    Markdown  ->  <输出目录>/<pdf基名>.md
    图片      ->  <输出目录>/<pdf基名>/images/*
    额外      ->  <输出目录>/<pdf基名>/content_list.json（结构化块列表，便于调试）

其中 <pdf基名> = 输入 PDF 去掉扩展名的文件名。

--------------------------------------------------------------------------
说明
--------------------------------------------------------------------------
* MinerU SDK 自身只读取环境变量 ``MINERU_TOKEN``，不会自动读
  ``~/.mineru/config.yaml``，因此本脚本负责解析该配置文件并注入 token
  （配置文件优先于环境变量，见 ``resolve_token``）。
* 配置文件中若存在 ``model`` 字段（如 ``model: vlm``）则作为默认模型。
* Windows 下强制 UTF-8 标准流，避免 GBK 控制台因中文/emoji 崩溃。
* 全程只读源 PDF，绝不修改源文件。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

# ── 强制 UTF-8 标准流（必须在其它输出之前执行） ──────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # 某些被重定向的流不支持 reconfigure，忽略
        pass


# =========================================================================
# 常量与日志
# =========================================================================

DEFAULT_CONFIG = Path.home() / ".mineru" / "config.yaml"
DEFAULT_OUTPUT_DIR = "math-output"
DEFAULT_LANGUAGE = "ch"          # 本仓库全部为中文数学试卷
DEFAULT_MODEL = "vlm"            # 与 SKILL.md / config.yaml 一致（精准模式）
DEFAULT_TIMEOUT = 1800           # 秒；MinerU 走网络 API，单份 1~3 分钟
MAX_FILE_MB = 200                # MinerU 单文件上限
VALID_MODELS = ("pipeline", "vlm", "html")


def log(msg: str) -> None:
    """带刷新的日志输出（避免长时间任务无回显）。"""
    print(msg, flush=True)


def die(msg: str, code: int = 1) -> "None":
    """打印错误并退出。"""
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


# =========================================================================
# 配置读取
# =========================================================================

def load_mineru_config(config_path: Path) -> dict:
    """读取 ~/.mineru/config.yaml，返回 dict；文件不存在或解析失败返回 {}。"""
    if not config_path.exists():
        return {}
    try:
        import yaml  # PyYAML（环境已安装）
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log(f"[WARN] 解析配置文件失败（{config_path}）：{exc}")
        return {}


def resolve_token(args_token: str | None, config: dict) -> str:
    """token 解析优先级：命令行 > 配置文件 > 环境变量 MINERU_TOKEN。

    注意：SKILL.md 规定 token 配置在 ``~/.mineru/config.yaml``，因此配置文件
    优先级高于环境变量——避免机器上遗留的、非 MinerU 格式的 MINERU_TOKEN
    环境变量（如其它平台的 JWT）遮蔽真正的 ``sk-`` token。
    """
    if args_token:
        return args_token.strip()
    cfg_token = str(config.get("token", "") or "").strip()
    if cfg_token:
        return cfg_token
    return os.environ.get("MINERU_TOKEN", "").strip()


def resolve_model(args_model: str | None, config: dict) -> str:
    """model 解析优先级：命令行 > 配置文件 model > 默认 vlm。"""
    if args_model:
        return args_model
    cfg_model = str(config.get("model", "") or "").strip()
    return cfg_model or DEFAULT_MODEL


# =========================================================================
# 结果落盘
# =========================================================================

def save_result(result, pdf_path: Path, out_dir: Path) -> dict:
    """把 ExtractResult 按输出约定落盘，返回统计信息 dict。

    输出：
        <out_dir>/<stem>.md
        <out_dir>/<stem>/images/<img>
        <out_dir>/<stem>/content_list.json（若有）
    """
    stem = pdf_path.stem
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / f"{stem}.md"
    bundle_dir = out_dir / stem
    img_dir = bundle_dir / "images"

    markdown = result.markdown or ""
    md_path.write_text(markdown, encoding="utf-8")

    # 图片落盘：用 basename 作为文件名，全部扁平放入 images/
    img_dir.mkdir(parents=True, exist_ok=True)
    img_count = 0
    used_names: set[str] = set()
    for img in (result.images or []):
        name = Path(img.name).name
        # 极端情况下重名，加序号避免覆盖
        if name in used_names:
            p = Path(name)
            name = f"{p.stem}_{len(used_names)}{p.suffix}"
        used_names.add(name)
        (img_dir / name).write_bytes(img.data)
        img_count += 1

    # 结构化块列表（调试 / 后续可选消费）
    cl_count = 0
    if result.content_list is not None:
        try:
            import json
            (bundle_dir / "content_list.json").write_text(
                json.dumps(result.content_list, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            cl_count = len(result.content_list)
        except Exception as exc:  # noqa: BLE001
            log(f"[WARN] 写入 content_list.json 失败：{exc}")

    return {
        "md_path": md_path,
        "bundle_dir": bundle_dir,
        "img_dir": img_dir,
        "md_chars": len(markdown),
        "img_count": img_count,
        "content_blocks": cl_count,
    }


# =========================================================================
# 主流程
# =========================================================================

def extract_with_progress(client, source: str, *, model: str, ocr,
                          language: str, pages: str | None,
                          timeout: int, poll_interval: float = 5.0):
    """提交任务并轮询，实时打印进度，返回首个 ExtractResult。

    直接调用 client.extract() 会静默阻塞 1~3 分钟；这里改用
    submit + get_batch 手动轮询，便于输出进度与超时控制。
    """
    submit_kwargs = {"model": model, "language": language}
    if ocr is not None:
        submit_kwargs["ocr"] = ocr
    if pages:
        submit_kwargs["pages"] = pages

    batch_id = client.submit(source, **submit_kwargs)
    log(f"[INFO] 任务已提交，batch_id={batch_id}")

    deadline = time.monotonic() + timeout
    last_line = ""
    while True:
        results = client.get_batch(batch_id)
        if not results:
            log("[WARN] get_batch 返回空列表，继续轮询…")
        else:
            r = results[0]
            if r.state in ("done", "failed"):
                # 进度条收尾
                if last_line:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                if r.state == "failed":
                    die(f"MinerU 解析失败：err_code={r.err_code} error={r.error}", 4)
                return r
            progress = f" {r.progress}" if getattr(r, "progress", None) else ""
            state = r.state or "running"
            line = f"[INFO] 解析中… state={state}{progress}   "
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
            last_line = line

        if time.monotonic() > deadline:
            die(f"等待 MinerU 任务超时（>{timeout}s），batch_id={batch_id}", 5)
        time.sleep(poll_interval)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf_extract.py",
        description="用 MinerU SDK 把 PDF 提取为 Markdown + 图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("pdf", help="输入 PDF 路径（或 http(s) URL）")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR,
                   help=f"输出目录（默认 {DEFAULT_OUTPUT_DIR}）")
    p.add_argument("--language", default=DEFAULT_LANGUAGE,
                   help=f"文档语言，中文 ch / 英文 en（默认 {DEFAULT_LANGUAGE}）")
    p.add_argument("--model", default=None, choices=list(VALID_MODELS),
                   help="pipeline | vlm | html（默认取配置文件，否则 vlm）")
    p.add_argument("--ocr", action="store_true",
                   help="强制启用 OCR（扫描件）；不加则由服务端自动判定")
    p.add_argument("--pages", default=None,
                   help='页码范围，如 "1-10" 或 "1-10,15"')
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"单文件轮询超时秒数（默认 {DEFAULT_TIMEOUT}）")
    p.add_argument("--retries", type=int, default=1,
                   help="网络/任务失败时的额外重试次数（默认 1）")
    p.add_argument("--token", default=None,
                   help="MinerU API token（覆盖配置文件/环境变量）")
    p.add_argument("--config", default=str(DEFAULT_CONFIG),
                   help=f"MinerU 配置文件路径（默认 {DEFAULT_CONFIG}）")
    p.add_argument("--extra-formats", default=None,
                   help="额外导出格式，逗号分隔（透传 SDK）")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # ── 1. 校验输入 ──────────────────────────────────────────────────
    source = args.pdf
    is_url = source.startswith("http://") or source.startswith("https://")
    pdf_path = None
    if not is_url:
        pdf_path = Path(source)
        if not pdf_path.exists():
            die(f"PDF 不存在：{pdf_path}", 2)
        if not pdf_path.is_file():
            die(f"不是文件：{pdf_path}", 2)
        size_mb = pdf_path.stat().st_size / 1024 / 1024
        if size_mb > MAX_FILE_MB:
            die(f"文件过大（{size_mb:.1f}MB > {MAX_FILE_MB}MB），MinerU 拒绝", 3)
    else:
        from urllib.parse import urlparse
        pdf_path = Path(Path(urlparse(source).path).name or "download")

    # ── 2. 读取配置 / 解析 token、model ─────────────────────────────
    config = load_mineru_config(Path(args.config))
    token = resolve_token(args.token, config)
    if not token:
        die(
            "未找到 MinerU token。请设置环境变量 MINERU_TOKEN，"
            f"或在 {args.config} 写入 token: 'xxx'（获取：https://mineru.net/apiManage/token）",
            3,
        )
    model = resolve_model(args.model, config)

    extra_formats = None
    if args.extra_formats:
        extra_formats = [s.strip() for s in args.extra_formats.split(",") if s.strip()]

    # ── 3. 打印运行参数 ─────────────────────────────────────────────
    log("=" * 66)
    log(f"  source   : {source}")
    log(f"  output   : {Path(args.output_dir).resolve()}")
    log(f"  model    : {model}")
    log(f"  language : {args.language}")
    log(f"  ocr      : {'on' if args.ocr else 'auto'}")
    log(f"  pages    : {args.pages or '(all)'}")
    log(f"  timeout  : {args.timeout}s")
    log(f"  token    : {'*' * 8} (len={len(token)})")
    log("=" * 66)

    # ── 4. 调用 SDK（带重试） ───────────────────────────────────────
    try:
        from mineru import MinerU
        from mineru import exceptions as mineru_exc
    except ImportError:
        die("未安装 mineru-open-sdk，请执行：pip install mineru-open-sdk", 3)

    ocr_arg = True if args.ocr else None
    attempts = max(1, args.retries + 1)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        client = None
        try:
            log(f"[INFO] 开始提取（第 {attempt}/{attempts} 次）…")
            client = MinerU(token=token)
            if extra_formats:
                # extra_formats 通过 extract 透传；这里仍走手动轮询，
                # 因此额外格式走 submit 不支持，简单回退到 extract
                result = client.extract(
                    source, model=model, ocr=ocr_arg, language=args.language,
                    pages=args.pages, extra_formats=extra_formats,
                    timeout=args.timeout,
                )
            else:
                result = extract_with_progress(
                    client, source, model=model, ocr=ocr_arg,
                    language=args.language, pages=args.pages, timeout=args.timeout,
                )
            break
        except SystemExit:
            raise
        except mineru_exc.TimeoutError as exc:
            last_exc = exc
            log(f"[WARN] 超时：{exc}")
        except mineru_exc.QuotaExceededError as exc:
            last_exc = exc
            log(f"[WARN] 配额超限：{exc}")
        except mineru_exc.AuthError as exc:
            die(f"鉴权失败（token 无效？）：{exc}", 3)
        except mineru_exc.ExtractFailedError as exc:
            last_exc = exc
            log(f"[WARN] 解析失败：{exc}")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log(f"[WARN] 第 {attempt} 次尝试异常：{type(exc).__name__}: {exc}")
            log(traceback.format_exc())
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass

        if attempt < attempts:
            backoff = 5 * attempt
            log(f"[INFO] {backoff}s 后重试…")
            time.sleep(backoff)
    else:
        die(f"提取失败（已尝试 {attempts} 次）：{last_exc}", 6)

    # ── 5. 落盘 ─────────────────────────────────────────────────────
    if not result.markdown or not result.markdown.strip():
        log("[WARN] MinerU 返回的 Markdown 为空，仍按约定落盘（请检查是否扫描件需 --ocr）")

    stats = save_result(result, pdf_path, Path(args.output_dir))

    log("-" * 66)
    log(f"[OK] 提取完成")
    log(f"     Markdown : {stats['md_path']}  ({stats['md_chars']} 字符)")
    log(f"     图片目录 : {stats['img_dir']}")
    log(f"     图片数量 : {stats['img_count']}")
    log(f"     结构块数 : {stats['content_blocks']}（content_list.json）")
    log("-" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())