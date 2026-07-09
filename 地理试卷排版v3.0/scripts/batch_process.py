# -*- coding: utf-8 -*-
"""
地理试卷批量处理脚本 v3.0

用法:
    # 批量处理目录下所有 docx 文件
    python batch_process.py --input-dir "v2.0/参考/" --output-dir "output/"

    # 处理指定文件列表
    python batch_process.py --files "试卷1.docx" "试卷2.docx" "试卷3.docx" --output-dir "output/"

    # 只执行 Step1（清洗+提取+转MD），为后续 AI 步骤做准备
    python batch_process.py --input-dir "v2.0/参考/" --step1-only

    # 只执行 Step6（排版），以已经完成的 final_exam.json 为输入
    python batch_process.py --step6-only --output-dir "output/"

功能:
    1. 批量执行 Step1（清洗+图片提取+MD转换），全自动
    2. 生成进度报告，标记每份试卷的 AI 步骤（Step2-5）状态
    3. 批量执行 Step6（排版），以已完成的 final_exam.json 为输入
    4. 输出批次汇总报告（JSON + HTML）
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 确保能导入同目录下的脚本
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from utils import docx_to_markdown, check_pending_symbols

# ============================================================================
# 配置
# ============================================================================

# 试卷类型分类（用于统计）
EXAM_CATEGORIES = {
    "纯文字": "S1",
    "少量图片": "S2",
    "材料题多": "S3",
    "格式混乱": "S4",
    "OCR误差大": "S5",
}


class BatchProcessor:
    """批量处理器：管理多份试卷的流水线执行和进度跟踪。"""

    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        self.summary = {
            "batch_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "started_at": datetime.now().isoformat(),
            "total_files": 0,
            "completed_step1": 0,
            "failed_step1": 0,
            "completed_step6": 0,
            "failed_step6": 0,
            "files": [],
        }

    def _get_exam_dir(self, exam_name: str) -> str:
        """获取单份试卷的工作目录。"""
        return os.path.join(self.output_dir, exam_name)

    def _read_log_errors(self, log_path: str) -> List[str]:
        """读取日志文件中的 ERROR 级别日志。"""
        errors = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "[ERROR]" in line or "[CRITICAL]" in line:
                        errors.append(line.strip())
        return errors

    # ========================================================================
    # Step 1: 清洗（全自动）
    # ========================================================================

    def run_step1(self, source_path: str, exam_name: str) -> Dict:
        """执行 Step1 清洗流水线。

        Args:
            source_path: 原始 docx 文件路径
            exam_name:  试卷名称（用于创建子目录）

        Returns:
            dict: {success: bool, statistics: dict, errors: list, warnings: list}
        """
        exam_dir = self._get_exam_dir(exam_name)
        cleaned_dir = os.path.join(exam_dir, "清洗产物")
        os.makedirs(cleaned_dir, exist_ok=True)

        result = {
            "exam_name": exam_name,
            "source_path": source_path,
            "step": "step1_clean_exam",
            "success": False,
            "started_at": datetime.now().isoformat(),
            "statistics": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # 1.1 执行 clean_docx.py
            cleaned_docx = os.path.join(cleaned_dir, "cleaned.docx")
            clean_log = os.path.join(cleaned_dir, "clean_log.txt")

            import subprocess
            rc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPT_DIR, "clean_docx.py"),
                    "--input", source_path,
                    "--output", cleaned_docx,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR,
            )

            if rc.returncode != 0:
                result["errors"].append(f"clean_docx.py 退出码 {rc.returncode}")
                result["errors"].append(rc.stderr.strip())
                return result

            if not os.path.exists(cleaned_docx) or os.path.getsize(cleaned_docx) == 0:
                result["errors"].append("clean_docx.py 未生成有效输出文件")
                return result

            clean_errors = self._read_log_errors(clean_log)
            if clean_errors:
                result["warnings"].extend(clean_errors[:5])

            # 1.2 执行 extract_images.py
            cleaned_no_images = os.path.join(cleaned_dir, "cleaned_no_images.docx")

            rc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPT_DIR, "extract_images.py"),
                    "--input", cleaned_docx,
                    "--output", cleaned_no_images,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR,
            )

            if rc.returncode != 0:
                result["errors"].append(f"extract_images.py 退出码 {rc.returncode}")
                result["errors"].append(rc.stderr.strip())
                return result

            # 统计图片数量
            images_dir = os.path.join(cleaned_dir, "images")
            image_count = 0
            if os.path.isdir(images_dir):
                image_count = len([
                    f for f in os.listdir(images_dir)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".wmf", ".emf"))
                ])

            # 1.3 转为 Markdown
            content_md = os.path.join(cleaned_dir, "content.md")
            image_manifest_path = os.path.join(cleaned_dir, "image_manifest.json")

            para_count = docx_to_markdown(
                cleaned_no_images,
                content_md,
                image_manifest_path=image_manifest_path if os.path.exists(image_manifest_path) else None,
            )

            # 1.4 检查未解析符号图片
            symbol_result = check_pending_symbols(cleaned_dir, content_md)

            # 汇总
            result["success"] = True
            result["statistics"] = {
                "content_paragraphs": para_count,
                "images_extracted": image_count,
                "small_symbol_images": symbol_result.get("small_images_count", 0),
                "symbols_report": bool(symbol_result.get("report_path")),
            }
            result["warnings"].extend(symbol_result.get("warnings", [])[:5])

        except Exception as e:
            result["errors"].append(f"Step1 异常: {str(e)}")
            result["errors"].append(traceback.format_exc())

        finally:
            result["finished_at"] = datetime.now().isoformat()

        return result

    # ========================================================================
    # Step 6: 排版（全自动，前提是 final_exam.json 已存在）
    # ========================================================================

    def run_step6(self, exam_name: str) -> Dict:
        """执行 Step6 排版。

        前提：output/{exam_name}/试卷数据/final_exam.json 必须存在（由 AI Step2-5 产出）。

        Returns:
            dict: {success: bool, statistics: dict, errors: list}
        """
        exam_dir = self._get_exam_dir(exam_name)
        final_json = os.path.join(exam_dir, "试卷数据", "final_exam.json")
        template = os.path.join(PROJECT_DIR, "assets", "template.dotx")
        images_dir = os.path.join(exam_dir, "清洗产物", "images")
        output_docx = os.path.join(exam_dir, "排版文档", "final_exam.docx")
        log_path = os.path.join(exam_dir, "排版文档", "typeset_log.txt")

        os.makedirs(os.path.join(exam_dir, "排版文档"), exist_ok=True)

        result = {
            "exam_name": exam_name,
            "step": "step6_typeset_exam",
            "success": False,
            "started_at": datetime.now().isoformat(),
            "statistics": {},
            "errors": [],
        }

        try:
            # 检查前置条件
            if not os.path.exists(final_json):
                result["errors"].append(f"final_exam.json 不存在: {final_json}")
                result["errors"].append("请先完成 Step2-5（AI 步骤），或检查 AI 产物是否落盘正确")
                return result

            if not os.path.exists(template):
                result["errors"].append(f"模板文件不存在: {template}")
                return result

            # 执行排版
            import subprocess
            rc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPT_DIR, "typeset_exam.py"),
                    "--json", final_json,
                    "--template", template,
                    "--images", images_dir if os.path.isdir(images_dir) else "",
                    "--output", output_docx,
                    "--log", log_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR,
            )

            if rc.returncode != 0:
                result["errors"].append(f"typeset_exam.py 退出码 {rc.returncode}")
                result["errors"].append(rc.stderr.strip())
                return result

            if not os.path.exists(output_docx) or os.path.getsize(output_docx) == 0:
                result["errors"].append("排版输出文件为空或不存在")
                return result

            # 读取质检报告统计
            quality_report = os.path.join(exam_dir, "排版文档", "quality_report.html")
            log_errors = self._read_log_errors(log_path)

            result["success"] = True
            result["statistics"] = {
                "output_size_kb": round(os.path.getsize(output_docx) / 1024, 1),
                "quality_report": os.path.exists(quality_report),
                "log_errors": len(log_errors),
            }
            if log_errors:
                result["errors"].extend(log_errors[:5])

        except Exception as e:
            result["errors"].append(f"Step6 异常: {str(e)}")
            result["errors"].append(traceback.format_exc())

        finally:
            result["finished_at"] = datetime.now().isoformat()

        return result

    # ========================================================================
    # 进度检查
    # ========================================================================

    def check_ai_status(self, exam_name: str) -> Dict:
        """检查 AI 步骤（Step2-5）的进度状态。

        Returns:
            dict: 各步骤的产物状态
        """
        exam_dir = self._get_exam_dir(exam_name)
        stage_dir = os.path.join(exam_dir, "中间数据")
        output_dir = os.path.join(exam_dir, "试卷数据")

        status = {
            "step2_structure": os.path.exists(os.path.join(stage_dir, "structure.json")),
            "step3_placeholders": os.path.exists(os.path.join(stage_dir, "with_placeholders.json")),
            "step4_images": os.path.exists(os.path.join(stage_dir, "image_descriptions.json")),
            "step5_final": os.path.exists(os.path.join(output_dir, "final_exam.json")),
        }
        status["ai_complete"] = all(status.values())
        status["ready_for_step6"] = status["step5_final"]

        return status

    # ========================================================================
    # 汇总报告
    # ========================================================================

    def generate_summary(self, file_results: List[Dict]) -> str:
        """生成批次汇总报告（JSON + HTML）。"""

        self.summary["finished_at"] = datetime.now().isoformat()
        self.summary["total_files"] = len(file_results)

        for r in file_results:
            self.summary["files"].append({
                "exam_name": r.get("exam_name", ""),
                "source": r.get("source_path", ""),
                "step1": "success" if r.get("step1_success") else "failed",
                "step6": "success" if r.get("step6_success") else ("pending" if not r.get("step6_attempted") else "failed"),
                "ai_status": r.get("ai_status", {}),
                "errors": r.get("errors", [])[:3],
            })

            if r.get("step1_success"):
                self.summary["completed_step1"] += 1
            else:
                self.summary["failed_step1"] += 1

            if r.get("step6_success"):
                self.summary["completed_step6"] += 1
            elif r.get("step6_attempted"):
                self.summary["failed_step6"] += 1

        # 写入 JSON
        json_path = os.path.join(self.output_dir, "batch_summary.json")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)

        # 生成 HTML
        html_path = os.path.join(self.output_dir, "batch_summary.html")
        self._generate_html_report(html_path)

        return json_path

    def _generate_html_report(self, html_path: str):
        """生成 HTML 格式的批次汇总报告。"""
        s = self.summary
        total = s["total_files"]
        step1_ok = s["completed_step1"]
        step1_fail = s["failed_step1"]
        step6_ok = s["completed_step6"]
        step6_fail = s["failed_step6"]
        step6_pending = total - step1_ok  # AI 未完成的

        rows = ""
        for f in s["files"]:
            step1_badge = '<span class="badge badge-ok">OK</span>' if f["step1"] == "success" else '<span class="badge badge-fail">FAIL</span>'
            step6_badge = ""
            if f["step6"] == "success":
                step6_badge = '<span class="badge badge-ok">OK</span>'
            elif f["step6"] == "failed":
                step6_badge = '<span class="badge badge-fail">FAIL</span>'
            else:
                step6_badge = '<span class="badge badge-pending">待AI</span>'

            ai = f.get("ai_status", {})
            ai_detail = ""
            if ai:
                ai_detail = f'S2:{"✓" if ai.get("step2_structure") else "✗"} S3:{"✓" if ai.get("step3_placeholders") else "✗"} S4:{"✓" if ai.get("step4_images") else "✗"} S5:{"✓" if ai.get("step5_final") else "✗"}'

            errors = "<br>".join(f.get("errors", []))

            rows += f"""<tr>
                <td>{f['exam_name']}</td>
                <td>{step1_badge}</td>
                <td class="ai-status">{ai_detail}</td>
                <td>{step6_badge}</td>
                <td class="error-cell">{errors}</td>
            </tr>"""

        step1_rate = f"{step1_ok}/{total}" if total > 0 else "N/A"
        step6_rate = f"{step6_ok}/{total}" if total > 0 else "N/A"

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>批量处理报告 - {s['batch_id']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei",sans-serif;background:#f0f2f5;color:#333;padding:20px;line-height:1.6}}
.container{{max-width:1100px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1a5276,#2980b9);color:#fff;padding:24px 36px;border-radius:12px 12px 0 0}}
.header h1{{font-size:22px;margin-bottom:6px}}
.header .sub{{font-size:13px;opacity:.8}}
.card{{background:#fff;padding:24px 36px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:16px}}
.card:last-child{{border-radius:0 0 12px 12px}}
.card h2{{font-size:16px;color:#1a5276;border-left:4px solid #2980b9;padding-left:10px;margin-bottom:14px}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}
.grid-item{{background:#f8f9fa;border-radius:8px;padding:14px;text-align:center}}
.grid-item .lbl{{font-size:12px;color:#7f8c8d}}
.grid-item .val{{font-size:24px;font-weight:700;color:#2c3e50}}
.grid-item.ok .val{{color:#27ae60}}
.grid-item.fail .val{{color:#e74c3c}}
.grid-item.pending .val{{color:#f39c12}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#eaf2f8;color:#1a5276;font-weight:600;padding:9px 12px;text-align:left;border-bottom:2px solid #d5dbdb}}
td{{padding:8px 12px;border-bottom:1px solid #ecf0f1}}
.ai-status{{font-family:monospace;font-size:11px;color:#7f8c8d}}
.error-cell{{font-size:11px;color:#c0392b;max-width:300px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-ok{{background:#e8f8e8;color:#27ae60}}
.badge-fail{{background:#fde8e8;color:#e74c3c}}
.badge-pending{{background:#fef3cd;color:#d68910}}
.progress-bar{{background:#ecf0f1;border-radius:8px;height:8px;margin-top:8px;overflow:hidden}}
.progress-fill{{background:#27ae60;height:100%;border-radius:8px;transition:width .3s}}
.footer{{text-align:center;font-size:12px;color:#bdc3c7;padding:20px 0}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>地理试卷批量处理报告</h1>
<div class="sub">批次: {s['batch_id']} | 共 {total} 份试卷</div>
</div>
<div class="card">
<h2>总体进度</h2>
<div class="grid">
<div class="grid-item"><div class="lbl">试卷总数</div><div class="val">{total}</div></div>
<div class="grid-item ok"><div class="lbl">Step1 清洗完成</div><div class="val">{step1_rate}</div></div>
<div class="grid-item fail"><div class="lbl">Step1 失败</div><div class="val">{step1_fail}</div></div>
<div class="grid-item ok"><div class="lbl">Step6 排版完成</div><div class="val">{step6_rate}</div></div>
<div class="grid-item pending"><div class="lbl">待 AI 步骤</div><div class="val">{step6_pending}</div></div>
</div>
<div class="progress-bar"><div class="progress-fill" style="width:{step1_ok/total*100 if total > 0 else 0}%"></div></div>
</div>
<div class="card">
<h2>文件详情</h2>
<table><thead><tr><th>试卷名称</th><th>Step1 清洗</th><th>AI 步骤 (S2-5)</th><th>Step6 排版</th><th>错误信息</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="footer">地理试卷排版 v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</div>
</body>
</html>'''

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="地理试卷批量处理 v3.0 - Step1 清洗 + Step6 排版（Step2-5 由 AI 执行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_process.py --input-dir "v2.0/参考/" --output-dir "output/"
  python batch_process.py --files "试卷1.docx" "试卷2.docx" --output-dir "output/"
  python batch_process.py --input-dir "v2.0/参考/" --step1-only
  python batch_process.py --step6-only --output-dir "output/" --exam-names "S1" "S2"
        """
    )
    parser.add_argument("--input-dir", "-d", help="输入目录（含 .docx 文件）")
    parser.add_argument("--files", "-f", nargs="+", help="指定文件列表")
    parser.add_argument("--output-dir", "-o", default="output/", help="输出根目录")
    parser.add_argument("--step1-only", action="store_true", help="仅执行 Step1（清洗）")
    parser.add_argument("--step6-only", action="store_true", help="仅执行 Step6（排版）")
    parser.add_argument("--exam-names", nargs="+", help="用于 --step6-only 时指定试卷名称列表")

    args = parser.parse_args()

    # 收集输入文件
    source_files = []

    if args.files:
        for f in args.files:
            if os.path.isfile(f) and f.lower().endswith(".docx"):
                source_files.append(os.path.abspath(f))
            else:
                print(f"警告: 文件不存在或非 docx 格式: {f}", file=sys.stderr)

    if args.input_dir:
        input_dir = os.path.abspath(args.input_dir)
        if os.path.isdir(input_dir):
            for root, dirs, files in os.walk(input_dir):
                for f in files:
                    if f.lower().endswith(".docx") and not f.startswith("~$"):
                        source_files.append(os.path.join(root, f))
        else:
            print(f"错误: 输入目录不存在: {input_dir}", file=sys.stderr)
            sys.exit(2)

    if not source_files and not args.step6_only:
        print("错误: 未找到任何 .docx 文件，请使用 --input-dir 或 --files 指定输入", file=sys.stderr)
        sys.exit(2)

    processor = BatchProcessor(args.output_dir)

    if args.step6_only:
        # 仅执行 Step6
        exam_names = args.exam_names or []
        if not exam_names:
            # 自动扫描所有包含 final_exam.json 的子目录
            for entry in os.listdir(args.output_dir):
                exam_dir = os.path.join(args.output_dir, entry)
                if os.path.isdir(exam_dir):
                    final_json = os.path.join(exam_dir, "试卷数据", "final_exam.json")
                    if os.path.exists(final_json):
                        exam_names.append(entry)

        if not exam_names:
            print("错误: 未找到可排版的试卷（缺少 final_exam.json）", file=sys.stderr)
            sys.exit(2)

        print(f"\n{'='*60}")
        print(f"执行 Step6 排版 ({len(exam_names)} 份试卷)")
        print(f"{'='*60}\n")

        results = []
        for name in exam_names:
            print(f"[排版] {name} ... ", end="", flush=True)
            r = processor.run_step6(name)
            r["step1_success"] = None
            r["step6_attempted"] = True
            r["step6_success"] = r.get("success", False)
            r["ai_status"] = processor.check_ai_status(name)
            results.append(r)
            status = "OK" if r["success"] else "FAIL"
            print(status)
            if not r["success"]:
                for err in r.get("errors", [])[:2]:
                    print(f"  - {err}")

        summary_path = processor.generate_summary(results)
        print(f"\n汇总报告: {summary_path}")
        print(f"HTML 报告: {os.path.join(args.output_dir, 'batch_summary.html')}")
        sys.exit(0)

    # Step1 清洗
    print(f"\n{'='*60}")
    print(f"执行 Step1 清洗 ({len(source_files)} 份试卷)")
    print(f"{'='*60}\n")

    step1_results = []
    for src in source_files:
        exam_name = os.path.splitext(os.path.basename(src))[0]
        # 清理文件名（移除特殊字符作为目录名）
        exam_name = exam_name.replace(" ", "_").replace("（", "(").replace("）", ")")

        print(f"[清洗] {exam_name} ... ", end="", flush=True)
        r = processor.run_step1(src, exam_name)
        r["step1_success"] = r.get("success", False)
        r["step6_attempted"] = False
        r["step6_success"] = False
        r["ai_status"] = processor.check_ai_status(exam_name)

        step1_results.append(r)
        status = "OK" if r["success"] else "FAIL"

        if r["success"]:
            stats = r.get("statistics", {})
            print(f"OK (段落:{stats.get('content_paragraphs', '?')}, 图片:{stats.get('images_extracted', '?')})")
        else:
            print("FAIL")
            for err in r.get("errors", [])[:2]:
                print(f"  - {err}")

        if args.step1_only:
            continue

    # 生成汇总报告
    summary_path = processor.generate_summary(step1_results)
    print(f"\n{'='*60}")
    print(f"Step1 完成: {processor.summary['completed_step1']}/{len(source_files)}")
    print(f"汇总报告: {summary_path}")
    print(f"HTML 报告: {os.path.join(args.output_dir, 'batch_summary.html')}")
    print(f"{'='*60}")

    if args.step1_only:
        print("\n提示: 下一步请通过 AI 执行每份试卷的 Step2-5")
        print("  (tag_structure → tag_placeholders → tag_images → map_images)")
        print("  然后重新运行: python batch_process.py --step6-only")
    else:
        print("\n提示: 请通过 AI 执行每份试卷的 Step2-5，完成后运行:")
        print("  python batch_process.py --step6-only --output-dir", args.output_dir)


if __name__ == "__main__":
    main()
