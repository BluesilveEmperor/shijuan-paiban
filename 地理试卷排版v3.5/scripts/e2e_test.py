# -*- coding: utf-8 -*-
"""
端到端测试验证脚本 v3.0

用法:
    # 验证单份试卷的流水线产物
    python e2e_test.py --exam-dir "output/S1_test_sample/"

    # 验证批量 output 目录下的所有试卷
    python e2e_test.py --batch-dir "output/batch/" --output "output/e2e_report.html"

    # 仅验证 Step1 产物
    python e2e_test.py --exam-dir "output/S1_test_sample/" --step step1

功能:
    1. 逐步骤验证流水线产物的存在性和 Schema 合规性
    2. 按验收标准（F1-F6, Q1-Q5, P1-P3）逐项检查
    3. 生成 HTML 格式的端到端测试报告
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 确保能导入 validate_json
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)


# ============================================================================
# 验收标准定义
# ============================================================================

ACCEPTANCE_CRITERIA = {
    # 功能验收 (F1-F6)
    "F1": {
        "name": "六步流水线贯通",
        "description": "从原始 docx 到 final_exam.docx 全流程无人工干预",
        "method": "检查各步骤产物全部存在且 Schema 校验通过",
    },
    "F2": {
        "name": "主编排不越界",
        "description": "master_exam_layout.md 全程不出现题目语义分析",
        "method": "审查编排日志",
    },
    "F3": {
        "name": "每步产物可独立校验",
        "description": "任一步骤产物可通过 validate_json.py 校验",
        "method": "逐步骤调用 validate_json.py",
    },
    "F4": {
        "name": "可回滚重跑",
        "description": "任一步骤失败后，修复后可单独重跑该步骤",
        "method": "检查步骤间无隐式依赖",
    },
    "F5": {
        "name": "图片链路解耦",
        "description": "Step4 可与 Step2/3 并行执行",
        "method": "检查 Step4 输入不依赖 Step2/3 产物",
    },
    "F6": {
        "name": "兜底字段生效",
        "description": "混乱试卷产生 uncertain / unclassified_blocks",
        "method": "检查 structure.json 中的 uncertain 和 unclassified_blocks 字段",
    },

    # 质量验收 (Q1-Q5)
    "Q1": {
        "name": "结构识别准确率",
        "description": "≥ 95%（人工标注题号比对）",
        "method": "暂需人工标注基准",
    },
    "Q2": {
        "name": "图片映射正确率",
        "description": "≥ 90%（人工标注映射比对）",
        "method": "暂需人工标注基准",
    },
    "Q3": {
        "name": "排版成功率",
        "description": "≥ 95%（脚本退出码 0）",
        "method": "检查 typeset_exam.py 退出码",
    },
    "Q4": {
        "name": "占位合理性",
        "description": "≥ 90% 占位有充分依据",
        "method": "检查 placeholders 中 reason 字段非空率",
    },
    "Q5": {
        "name": "异常覆盖率",
        "description": "error_cases.md 覆盖 ≥ 8 类异常",
        "method": "统计 error_cases.md 中预定义异常数量",
    },

    # 性能验收 (P1-P3)
    "P1": {
        "name": "端到端耗时",
        "description": "≤ v2.0 同等试卷耗时的 1.2 倍",
        "method": "记录 total_elapsed 并与 v2.0 基准对比",
    },
    "P2": {
        "name": "脚本执行耗时",
        "description": "clean_docx + extract_images + format_docx 总计 ≤ 30 秒",
        "method": "记录各脚本耗时",
    },
    "P3": {
        "name": "Schema 校验耗时",
        "description": "单次校验 ≤ 1 秒",
        "method": "记录 validate_json.py 耗时",
    },
}


class E2ETester:
    """端到端测试器：验证流水线产物的完整性和合规性。"""

    def __init__(self, exam_dir: str):
        self.exam_dir = os.path.abspath(exam_dir)
        self.exam_name = os.path.basename(self.exam_dir)
        self.project_dir = os.path.dirname(SCRIPT_DIR)
        self.schema_path = os.path.join(self.project_dir, "schemas", "exam_paper.schema.json")

        self.results = {
            "exam_name": self.exam_name,
            "exam_dir": self.exam_dir,
            "tested_at": datetime.now().isoformat(),
            "steps": {},
            "acceptance": {},
            "overall_pass": False,
        }

    def _run_validate(self, json_path: str) -> Dict:
        """运行 Schema 校验并返回结果。"""
        import subprocess
        start = time.time()
        try:
            rc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPT_DIR, "validate_json.py"),
                    "--schema", self.schema_path,
                    "--json", json_path,
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_dir,
            )
            elapsed = time.time() - start
            result = json.loads(rc.stdout) if rc.stdout else {"valid": False, "error": "无输出"}
            result["exit_code"] = rc.returncode
            result["elapsed_sec"] = round(elapsed, 3)
            return result
        except subprocess.TimeoutExpired:
            return {"valid": False, "error": "Schema 校验超时 (>10s)", "elapsed_sec": 10.0}
        except json.JSONDecodeError:
            return {"valid": False, "error": f"无法解析校验输出: {rc.stdout[:200] if 'rc' in dir() else ''}", "elapsed_sec": 0}
        except Exception as e:
            return {"valid": False, "error": str(e), "elapsed_sec": 0}

    def _file_age_min(self, path: str) -> Optional[float]:
        """获取文件创建后的分钟数。"""
        if not os.path.exists(path):
            return None
        return (time.time() - os.path.getmtime(path)) / 60

    # ========================================================================
    # 逐步骤验证
    # ========================================================================

    def test_step1(self) -> Dict:
        """验证 Step1 产物。"""
        cleaned_dir = os.path.join(self.exam_dir, "清洗产物")
        checks = {
            "cleaned_no_images_docx": os.path.exists(os.path.join(cleaned_dir, "cleaned_no_images.docx")),
            "content_md": os.path.exists(os.path.join(cleaned_dir, "content.md")),
            "images_dir": os.path.isdir(os.path.join(cleaned_dir, "images")),
            "image_manifest": os.path.exists(os.path.join(cleaned_dir, "image_manifest.json")),
            "clean_log": os.path.exists(os.path.join(cleaned_dir, "clean_log.txt")),
        }

        # 检查 content.md 非空
        content_md = os.path.join(cleaned_dir, "content.md")
        content_lines = 0
        if os.path.exists(content_md):
            with open(content_md, "r", encoding="utf-8") as f:
                content_lines = len(f.readlines())

        # 统计图片
        images_dir = os.path.join(cleaned_dir, "images")
        image_count = 0
        if os.path.isdir(images_dir):
            image_count = len([f for f in os.listdir(images_dir) if not f.startswith(".")])

        # 检查日志中是否有错误
        log_errors = 0
        clean_log = os.path.join(cleaned_dir, "clean_log.txt")
        if os.path.exists(clean_log):
            with open(clean_log, "r", encoding="utf-8") as f:
                for line in f:
                    if "[ERROR]" in line or "[CRITICAL]" in line:
                        log_errors += 1

        passed = all(checks.values()) and content_lines > 0 and log_errors == 0
        return {
            "step": "step1_clean_exam",
            "passed": passed,
            "checks": checks,
            "statistics": {
                "content_lines": content_lines,
                "images_extracted": image_count,
                "log_errors": log_errors,
            },
            "issues": [] if passed else [
                f"缺失产物: {[k for k, v in checks.items() if not v]}" if not all(checks.values()) else "",
                "content.md 为空" if content_lines == 0 else "",
                f"日志含 {log_errors} 个 ERROR" if log_errors > 0 else "",
            ],
        }

    def test_step2(self) -> Dict:
        """验证 Step2 产物。"""
        structure_json = os.path.join(self.exam_dir, "中间数据", "structure.json")

        if not os.path.exists(structure_json):
            return {
                "step": "step2_tag_structure",
                "passed": False,
                "issues": ["structure.json 不存在"],
                "validation": None,
            }

        # Schema 校验
        validation = self._run_validate(structure_json)

        # 加载 JSON 进行字段检查
        stats = {}
        try:
            with open(structure_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            sections = data.get("document", {}).get("sections", [])
            total_questions = sum(len(s.get("questions", [])) for s in sections)
            uncertain_count = sum(
                1 for s in sections
                for q in s.get("questions", [])
                if q.get("uncertain")
            )
            unclassified = data.get("document", {}).get("unclassified_blocks", [])

            stats = {
                "sections": len(sections),
                "total_questions": total_questions,
                "uncertain_questions": uncertain_count,
                "unclassified_blocks": len(unclassified),
            }
        except Exception:
            pass

        passed = validation.get("valid", False)
        return {
            "step": "step2_tag_structure",
            "passed": passed,
            "validation": validation,
            "statistics": stats,
            "issues": [] if passed else [validation.get("error", "校验失败")],
        }

    def test_step3(self) -> Dict:
        """验证 Step3 产物。"""
        wp_json = os.path.join(self.exam_dir, "中间数据", "with_placeholders.json")

        if not os.path.exists(wp_json):
            return {
                "step": "step3_tag_placeholders",
                "passed": False,
                "issues": ["with_placeholders.json 不存在"],
                "validation": None,
            }

        validation = self._run_validate(wp_json)

        # 检查占位符质量
        stats = {"total_placeholders": 0, "with_reason": 0, "with_owner": 0}
        issues = []

        try:
            with open(wp_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            placeholder_ids = set()
            for section in data.get("document", {}).get("sections", []):
                for q in section.get("questions", []):
                    for ph in q.get("placeholders", []):
                        stats["total_placeholders"] += 1
                        if ph.get("reason"):
                            stats["with_reason"] += 1
                        if ph.get("owner_id"):
                            stats["with_owner"] += 1
                        pid = ph.get("placeholder_id")
                        if pid in placeholder_ids:
                            issues.append(f"重复的 placeholder_id: {pid}")
                        placeholder_ids.add(pid)

            if stats["total_placeholders"] > 0:
                if stats["with_reason"] < stats["total_placeholders"]:
                    issues.append(f"{stats['total_placeholders'] - stats['with_reason']} 个占位符缺少 reason")
                if stats["with_owner"] < stats["total_placeholders"]:
                    issues.append(f"{stats['total_placeholders'] - stats['with_owner']} 个占位符缺少 owner_id")
        except Exception as e:
            issues.append(f"JSON 解析失败: {e}")

        passed = validation.get("valid", False) and not issues
        return {
            "step": "step3_tag_placeholders",
            "passed": passed,
            "validation": validation,
            "statistics": stats,
            "issues": issues,
        }

    def test_step4(self) -> Dict:
        """验证 Step4 产物。"""
        id_json = os.path.join(self.exam_dir, "中间数据", "image_descriptions.json")

        if not os.path.exists(id_json):
            return {
                "step": "step4_tag_images",
                "passed": False,
                "issues": ["image_descriptions.json 不存在"],
                "validation": None,
            }

        # 检查图片计数与实际文件数一致
        images_dir = os.path.join(self.exam_dir, "清洗产物", "images")
        actual_count = 0
        if os.path.isdir(images_dir):
            actual_count = len([f for f in os.listdir(images_dir) if not f.startswith(".")])

        stats = {"image_count": 0, "actual_images": actual_count}
        issues = []

        try:
            with open(id_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            stats["image_count"] = data.get("image_count", 0)
            images = data.get("images", [])

            if stats["image_count"] != actual_count:
                issues.append(f"image_count ({stats['image_count']}) 与实际文件数 ({actual_count}) 不一致")

            uncertain_count = sum(1 for img in images if img.get("uncertain"))
            stats["uncertain_images"] = uncertain_count

            # 检查必填字段
            missing_fields = 0
            for img in images:
                for key in ["image_id", "file_name", "type", "summary", "keywords"]:
                    if not img.get(key):
                        missing_fields += 1
            if missing_fields > 0:
                issues.append(f"{missing_fields} 个必填字段缺失")

        except Exception as e:
            issues.append(f"JSON 解析失败: {e}")

        passed = len(issues) == 0
        return {
            "step": "step4_tag_images",
            "passed": passed,
            "statistics": stats,
            "issues": issues,
        }

    def test_step5(self) -> Dict:
        """验证 Step5 产物。"""
        final_json = os.path.join(self.exam_dir, "试卷数据", "final_exam.json")

        if not os.path.exists(final_json):
            return {
                "step": "step5_map_images",
                "passed": False,
                "issues": ["final_exam.json 不存在"],
                "validation": None,
            }

        validation = self._run_validate(final_json)

        stats = {}
        issues = []

        try:
            with open(final_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            mapping = data.get("image_mapping", [])
            images = data.get("images", [])
            validation_field = data.get("validation", {})

            image_ids = {img.get("image_id") for img in images}
            placeholder_ids = set()
            for section in data.get("document", {}).get("sections", []):
                for q in section.get("questions", []):
                    for ph in q.get("placeholders", []):
                        placeholder_ids.add(ph.get("placeholder_id"))

            mapped_ph = {m.get("placeholder_id") for m in mapping}
            mapped_img = {m.get("image_id") for m in mapping}

            stats = {
                "total_placeholders": len(placeholder_ids),
                "total_images": len(image_ids),
                "mapped_pairs": len(mapping),
                "unmapped": len(validation_field.get("unmapped_placeholders", [])),
                "unused": len(validation_field.get("unused_images", [])),
                "avg_confidence": round(
                    sum(m.get("confidence", 0) for m in mapping) / len(mapping), 2
                ) if mapping else 0,
            }

            # 引用有效性检查
            orphan_refs = mapped_ph - placeholder_ids
            if orphan_refs:
                issues.append(f"image_mapping 引用了不存在的占位符: {orphan_refs}")
            orphan_imgs = mapped_img - image_ids
            if orphan_imgs:
                issues.append(f"image_mapping 引用了不存在的图片: {orphan_imgs}")

            # validation 一致性
            if validation_field.get("has_unmapped_placeholders") != (len(validation_field.get("unmapped_placeholders", [])) > 0):
                issues.append("has_unmapped_placeholders 与实际不一致")
            if validation_field.get("has_unused_images") != (len(validation_field.get("unused_images", [])) > 0):
                issues.append("has_unused_images 与实际不一致")

        except Exception as e:
            issues.append(f"final_exam.json 解析失败: {e}")

        passed = validation.get("valid", False) and not issues
        return {
            "step": "step5_map_images",
            "passed": passed,
            "validation": validation,
            "statistics": stats,
            "issues": issues,
        }

    def test_step6(self) -> Dict:
        """验证 Step6 产物。"""
        dist_dir = os.path.join(self.exam_dir, "排版文档")
        # 最终排版结果放在 exam_dir 根级别
        exam_name = os.path.basename(self.exam_dir)
        docx_path = os.path.join(self.exam_dir, f"{exam_name}-排版后.docx")
        checks = {
            "final_exam_docx": os.path.exists(docx_path),
            "quality_report_html": os.path.exists(os.path.join(dist_dir, "quality_report.html")),
            "typeset_log": os.path.exists(os.path.join(dist_dir, "typeset_log.txt")),
        }

        # 检查 docx 大小
        docx_size = 0
        if os.path.exists(docx_path):
            docx_size = os.path.getsize(docx_path)

        # 检查日志错误
        log_errors = 0
        log_path = os.path.join(dist_dir, "typeset_log.txt")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "[ERROR]" in line or "[CRITICAL]" in line:
                        log_errors += 1

        passed = all(checks.values()) and docx_size > 0 and log_errors == 0
        return {
            "step": "step6_typeset_exam",
            "passed": passed,
            "checks": checks,
            "statistics": {
                "docx_size_kb": round(docx_size / 1024, 1),
                "log_errors": log_errors,
            },
            "issues": [] if passed else [
                f"缺失产物: {[k for k, v in checks.items() if not v]}" if not all(checks.values()) else "",
                "docx 文件为空" if docx_size == 0 else "",
                f"日志含 {log_errors} 个 ERROR" if log_errors > 0 else "",
            ],
        }

    # ========================================================================
    # 验收标准检查
    # ========================================================================

    def check_acceptance(self, step_results: Dict) -> Dict:
        """按验收标准逐项评分。"""
        acceptance = {}

        # F1: 六步流水线贯通
        acceptance["F1"] = {
            "name": "六步流水线贯通",
            "passed": all(
                step_results.get(s, {}).get("passed", False)
                for s in ["step1_clean_exam", "step2_tag_structure", "step3_tag_placeholders",
                          "step4_tag_images", "step5_map_images", "step6_typeset_exam"]
            ),
            "detail": {s: step_results.get(s, {}).get("passed", False) for s in [
                "step1_clean_exam", "step2_tag_structure", "step3_tag_placeholders",
                "step4_tag_images", "step5_map_images", "step6_typeset_exam"
            ]},
        }

        # F3: 每步产物可独立校验
        f3_passed = True
        for step_key in ["step2_tag_structure", "step3_tag_placeholders", "step5_map_images"]:
            validation = step_results.get(step_key, {}).get("validation")
            if validation and not validation.get("valid", False):
                f3_passed = False
                break
        acceptance["F3"] = {"name": "每步产物可独立校验", "passed": f3_passed}

        # F6: 兜底字段生效（需要检查 S4 类型试卷）
        step2 = step_results.get("step2_tag_structure", {})
        stats = step2.get("statistics", {})
        f6_passed = stats.get("uncertain_questions", 0) > 0 or stats.get("unclassified_blocks", 0) > 0
        acceptance["F6"] = {
            "name": "兜底字段生效",
            "passed": f6_passed,
            "detail": f"uncertain: {stats.get('uncertain_questions', 0)}, unclassified: {stats.get('unclassified_blocks', 0)}",
        }

        # Q3: 排版成功率
        step6 = step_results.get("step6_typeset_exam", {})
        acceptance["Q3"] = {
            "name": "排版成功率",
            "passed": step6.get("passed", False),
        }

        # Q4: 占位合理性
        step3 = step_results.get("step3_tag_placeholders", {})
        s3_stats = step3.get("statistics", {})
        total = s3_stats.get("total_placeholders", 0)
        with_reason = s3_stats.get("with_reason", 0)
        q4_rate = round(with_reason / total * 100) if total > 0 else 100
        acceptance["Q4"] = {
            "name": "占位合理性",
            "passed": q4_rate >= 90,
            "detail": f"{with_reason}/{total} ({q4_rate}%)",
        }

        # Q5: 异常覆盖率
        error_cases_path = os.path.join(self.project_dir, "docs", "error_cases.md")
        error_count = 0
        if os.path.exists(error_cases_path):
            with open(error_cases_path, "r", encoding="utf-8") as f:
                content = f.read()
                import re
                error_count = len(re.findall(r'^## E\d+: ', content, re.MULTILINE))
        acceptance["Q5"] = {
            "name": "异常覆盖率",
            "passed": error_count >= 8,
            "detail": f"预定义 {error_count} 类异常",
        }

        return acceptance

    # ========================================================================
    # 运行全部测试
    # ========================================================================

    def run_all(self) -> Dict:
        """运行全部测试步骤。"""
        print(f"\n{'='*60}")
        print(f"端到端测试: {self.exam_name}")
        print(f"目录: {self.exam_dir}")
        print(f"{'='*60}\n")

        step_results = {}

        # Step1
        print("[Step1] clean_exam ... ", end="", flush=True)
        r = self.test_step1()
        step_results["step1_clean_exam"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # Step2
        print("[Step2] tag_structure ... ", end="", flush=True)
        r = self.test_step2()
        step_results["step2_tag_structure"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # Step3
        print("[Step3] tag_placeholders ... ", end="", flush=True)
        r = self.test_step3()
        step_results["step3_tag_placeholders"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # Step4
        print("[Step4] tag_images ... ", end="", flush=True)
        r = self.test_step4()
        step_results["step4_tag_images"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # Step5
        print("[Step5] map_images ... ", end="", flush=True)
        r = self.test_step5()
        step_results["step5_map_images"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # Step6
        print("[Step6] typeset_exam ... ", end="", flush=True)
        r = self.test_step6()
        step_results["step6_typeset_exam"] = r
        print("PASS" if r["passed"] else "FAIL")
        if not r["passed"]:
            for issue in r.get("issues", []):
                if issue:
                    print(f"  - {issue}")

        # 验收标准
        acceptance = self.check_acceptance(step_results)
        self.results["steps"] = step_results
        self.results["acceptance"] = acceptance
        self.results["overall_pass"] = all(
            r.get("passed", False) for r in step_results.values()
        )

        # 汇总
        step_status = {k: "PASS" if v.get("passed") else "FAIL" for k, v in step_results.items()}
        acceptance_status = {k: "PASS" if v.get("passed") else "FAIL" for k, v in acceptance.items()}

        print(f"\n{'='*60}")
        print(f"步骤结果: {step_status}")
        print(f"验收标准: {acceptance_status}")
        print(f"总体结果: {'PASS' if self.results['overall_pass'] else 'FAIL'}")
        print(f"{'='*60}")

        return self.results


# ============================================================================
# HTML 报告生成
# ============================================================================

def generate_html_report(results_list: List[Dict], output_path: str):
    """为多个测试结果生成 HTML 报告。"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    overall_pass = all(r.get("overall_pass", False) for r in results_list)
    total = len(results_list)
    passed_count = sum(1 for r in results_list if r.get("overall_pass", False))

    # 生成每份试卷的行
    exam_rows = ""
    for r in results_list:
        steps = r.get("steps", {})
        row = f"<tr><td>{r['exam_name']}</td>"
        for step_key in ["step1_clean_exam", "step2_tag_structure", "step3_tag_placeholders",
                         "step4_tag_images", "step5_map_images", "step6_typeset_exam"]:
            s = steps.get(step_key, {})
            passed = s.get("passed", False)
            if not s:
                row += '<td><span class="tag tag-na">N/A</span></td>'
            elif passed:
                row += '<td><span class="tag tag-pass">PASS</span></td>'
            else:
                row += '<td><span class="tag tag-fail">FAIL</span></td>'
        row += f"<td>{'PASS' if r.get('overall_pass') else 'FAIL'}</td></tr>"
        exam_rows += row

    # 验收标准汇总
    criteria_rows = ""
    for cid, crit in ACCEPTANCE_CRITERIA.items():
        all_passed = all(
            r.get("acceptance", {}).get(cid, {}).get("passed", False)
            for r in results_list
        )
        badge = '<span class="tag tag-pass">ALL</span>' if all_passed else '<span class="tag tag-fail">PARTIAL</span>'
        criteria_rows += f"<tr><td>{cid}</td><td>{crit['name']}</td><td>{crit['description']}</td><td>{badge}</td></tr>"

    header_class = "pass" if overall_pass else "fail"
    header_text = "全部通过" if overall_pass else f"{passed_count}/{total} 通过"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>端到端测试报告 - 地理试卷排版 v3.0</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei",sans-serif;background:#f0f2f5;color:#333;line-height:1.7;padding:20px}}
.container{{max-width:1100px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1a5276,#2980b9);color:#fff;padding:24px 36px;border-radius:12px 12px 0 0}}
.header.pass{{background:linear-gradient(135deg,#1e8449,#27ae60)}}
.header.fail{{background:linear-gradient(135deg,#922b21,#c0392b)}}
.header h1{{font-size:22px;margin-bottom:4px}}
.header .sub{{font-size:13px;opacity:.9}}
.card{{background:#fff;padding:24px 36px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:0}}
.card.last{{border-radius:0 0 12px 12px;margin-bottom:20px}}
.card h2{{font-size:16px;color:#1a5276;border-left:4px solid #2980b9;padding-left:10px;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px}}
th{{background:#eaf2f8;color:#1a5276;font-weight:600;padding:9px 12px;text-align:left;border-bottom:2px solid #d5dbdb}}
td{{padding:8px 12px;border-bottom:1px solid #ecf0f1}}
.tag{{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600}}
.tag-pass{{background:#e8f8e8;color:#27ae60}}
.tag-fail{{background:#fde8e8;color:#e74c3c}}
.tag-na{{background:#f0f0f0;color:#999}}
.footer{{text-align:center;font-size:12px;color:#bdc3c7;padding:20px 0}}
</style>
</head>
<body>
<div class="container">
<div class="header {header_class}">
<h1>端到端测试报告</h1>
<div class="sub">地理试卷排版 v3.0 | {now} | {header_text}</div>
</div>
<div class="card">
<h2>测试样本 ({total} 份)</h2>
<table>
<thead><tr><th>试卷</th><th>Step1</th><th>Step2</th><th>Step3</th><th>Step4</th><th>Step5</th><th>Step6</th><th>结果</th></tr></thead>
<tbody>{exam_rows}</tbody>
</table>
</div>
<div class="card last">
<h2>验收标准检查</h2>
<table>
<thead><tr><th>编号</th><th>名称</th><th>标准</th><th>状态</th></tr></thead>
<tbody>{criteria_rows}</tbody>
</table>
</div>
<div class="footer">地理试卷排版 v3.0 端到端测试 | {now}</div>
</div>
</body>
</html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="端到端测试验证 - 地理试卷排版 v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python e2e_test.py --exam-dir "output/batch/S1_test/"
  python e2e_test.py --batch-dir "output/batch/" --output "output/e2e_report.html"
  python e2e_test.py --exam-dir "output/batch/S1_test/" --step step2
        """
    )
    parser.add_argument("--exam-dir", help="单份试卷的工作目录")
    parser.add_argument("--batch-dir", help="批量输出目录（自动扫描所有子目录）")
    parser.add_argument("--output", "-o", default="output/e2e_report.html", help="HTML 报告输出路径")
    parser.add_argument("--step", choices=["step1", "step2", "step3", "step4", "step5", "step6"],
                        help="仅验证指定步骤")

    args = parser.parse_args()

    if not args.exam_dir and not args.batch_dir:
        print("错误: 请指定 --exam-dir 或 --batch-dir", file=sys.stderr)
        sys.exit(2)

    # 收集测试目标
    exam_dirs = []

    if args.exam_dir:
        if os.path.isdir(args.exam_dir):
            exam_dirs.append(args.exam_dir)
        else:
            print(f"错误: 目录不存在: {args.exam_dir}", file=sys.stderr)
            sys.exit(2)

    if args.batch_dir:
        if os.path.isdir(args.batch_dir):
            for entry in os.listdir(args.batch_dir):
                entry_path = os.path.join(args.batch_dir, entry)
                if os.path.isdir(entry_path) and not entry.startswith("."):
                    # 检查是否有 清洗产物 目录（确认是试卷工作目录）
                    if os.path.isdir(os.path.join(entry_path, "清洗产物")):
                        exam_dirs.append(entry_path)
        else:
            print(f"错误: 目录不存在: {args.batch_dir}", file=sys.stderr)
            sys.exit(2)

    if not exam_dirs:
        print("错误: 未找到任何试卷工作目录", file=sys.stderr)
        sys.exit(2)

    # 运行测试
    all_results = []
    for exam_dir in exam_dirs:
        tester = E2ETester(exam_dir)

        if args.step:
            # 仅运行指定步骤
            step_method = getattr(tester, f"test_{args.step}", None)
            if step_method:
                result = step_method()
                tester.results["steps"] = {args.step: result}
                tester.results["overall_pass"] = result.get("passed", False)
                all_results.append(tester.results)
                print(f"\n{args.step}: {'PASS' if result['passed'] else 'FAIL'}")
            else:
                print(f"错误: 未知步骤 {args.step}", file=sys.stderr)
        else:
            # 运行全部
            result = tester.run_all()
            all_results.append(result)

    # 生成报告
    if len(all_results) > 0:
        report_path = generate_html_report(all_results, args.output)
        print(f"\n测试报告: {report_path}")

    # 退出码
    all_pass = all(r.get("overall_pass", False) for r in all_results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
