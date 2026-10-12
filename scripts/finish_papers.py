#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finish all un-typeset papers in 高三数学.

Pipeline: staged renamed PDF -> MinerU OCR -> .math-output/<target>.md
Resumable: skips a job when .math-output/<target>.md already exists.
DOCX sources must be pre-converted to staged PDFs (convert_docx.ps1).
Usage:
  python finish_papers.py            # run all pending OCR jobs
  python finish_papers.py --list     # show pending jobs only
"""
import sys, os, time, shutil, traceback, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path(r"D:\Music\试题加题库\高三数学")
MATH_OUT = BASE / ".math-output"
STAGE = Path(r"C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage")
LOG = STAGE / "ocr_log.txt"

P = r"数学思考2025年03月资料分享"

# (source path relative to BASE, OCR target name, kind)
# kind: exam = 试卷 (md2tex), ans = 答案/解析 (md2ans)
MANIFEST = [
    # -- 半成品补缺 --
    (r"温州市2024-2025学年高三下学期学业水平评估数学试卷.pdf",
     "温州市2024-2025学年高三下学期学业水平评估数学试卷", "exam"),
    (r"河南省2025年高考综合改革适应性演练 -解析.docx",
     "河南省2025年高考综合改革适应性演练-数学参考答案", "ans"),
    # -- 6 个子文件夹 --
    (r"2025届长沙一中高三上学期阶段性检测（一）数学试题+答案\数学（一中）_.pdf",
     "2025届长沙一中高三上学期阶段性检测（一）数学试题+答案", "exam"),
    (r"湖北华中师大一附中2025届高三十月月考数学试卷+答案\湖北华中师范大学第一附属中学2025届高三上学期十月月度检测数学试卷（原卷版）.pdf",
     "湖北省武汉市华中师范大学第一附属中学2024-2025学年高三上学期十月月度检测数学试卷", "exam"),
    (r"湖北华中师大一附中2025届高三十月月考数学试卷+答案\湖北华中师范大学第一附属中学2025届高三上学期十月月度检测数学试卷（解析版）.pdf",
     "湖北省武汉市华中师范大学第一附属中学2024-2025学年高三上学期十月月度检测数学试卷参考答案", "ans"),
    (r"湖南天一大联考高三9月月考数学试题+答案\湖南天一大联考高三9月月考数学试题.pdf",
     "湖南天一大联考高三9月月考数学试题", "exam"),
    (r"湖南天一大联考高三9月月考数学试题+答案\湖南天一大联考高三9月月考数学答案.pdf",
     "湖南天一大联考高三9月月考数学答案", "ans"),
    (r"湖南长沙明德中学2025届高三上学期8月阶段检测数学试卷+答案\2024-2025届湖南省长沙市明德中学高三上学期8月份阶段检测数学试卷.pdf",
     "湖南省长沙市明德中学2024-2025学年高三上学期8月阶段检测数学试卷", "exam"),
    (r"湖南长沙明德中学2025届高三上学期8月阶段检测数学试卷+答案\2024-2025届湖南省长沙市明德中学高三上学期8月份阶段检测数学答案(教师版).pdf",
     "湖南省长沙市明德中学2024-2025学年高三上学期8月阶段检测数学答案", "ans"),
    (r"雅礼中学2025届高三上学期（9月）综合自主测试数学试题+答案\数学（YL）_.pdf",
     "雅礼中学2025届高三上学期9月综合自主测试数学试题", "exam"),
    (r"雅礼中学2025届高三上学期（9月）综合自主测试数学试题+答案\数学答案（YL）_.pdf",
     "雅礼中学2025届高三上学期9月综合自主测试数学答案", "ans"),
    (r"浙江省名校新高考研究联盟（Z20名校联盟）2025届高三上学期第一次联考（暑假返校考）数学试题+答案\浙江省名校新高考研究联盟（Z20名校联盟）2024-2025学年高三上学期第一次联考（暑假返校考）数学试题（原卷版）.pdf",
     "浙江省名校新高考研究联盟（Z20名校联盟）2025届高三上学期第一次联考（暑假返校考）数学试题", "exam"),
    (r"浙江省名校新高考研究联盟（Z20名校联盟）2025届高三上学期第一次联考（暑假返校考）数学试题+答案\浙江省名校新高考研究联盟（Z20名校联盟）2024-2025学年高三上学期第一次联考（暑假返校考）数学试题（解析版）.pdf",
     "浙江省名校新高考研究联盟（Z20名校联盟）2025届高三上学期第一次联考（暑假返校考）数学试题参考答案", "ans"),
    # -- 数学思考2025年03月资料分享 --
    (P + r"\东北三省精准教学2025届高三3月联考数学强化卷\东北三省精准教学2025年3月高三联考 强化卷 正文 0228.pdf",
     "东北三省精准教学2025届高三3月联考数学强化卷", "exam"),
    (P + r"\东北三省精准教学2025届高三3月联考数学强化卷\东北三省精准教学2025年3月高三联考 强化卷 解析 0228.pdf",
     "东北三省精准教学2025届高三3月联考数学强化卷解析", "ans"),
    (P + r"\东北三省精准教学2025届高三3月联考数学强化卷\东北三省精准教学2025年3月高三联考 强化卷 简答 0228.pdf",
     "东北三省精准教学2025届高三3月联考数学强化卷简答", "ans"),
    (P + r"\福建省2025届高中毕业班适应性（一模）考试数学卷(1)\福建省2025届高中毕业班适应性（一模）考试数学卷(1).pdf",
     "福建省2025届高中毕业班适应性（一模）考试数学卷", "exam"),
    (P + r"\福建省2025届高中毕业班适应性（一模）考试数学卷(1)\福建省2025届高中毕业班适应性练习卷数学试题.pdf",
     "福建省2025届高中毕业班适应性练习卷数学试题", "exam"),
    (P + r"\福建省泉州市2025届高三下学期数学质量检测试题（三）数学试题\福建省泉州市2025届高三下学期数学质量检测试题（三）数学试题.pdf",
     "福建省泉州市2025届高三下学期数学质量检测试题（三）", "exam"),
    (P + r"\甘肃省2025届高三下学期3月月考试卷\甘肃省2025届高三下学期3月月考试卷.pdf",
     "甘肃省2025届高三下学期3月月考试卷", "exam"),
    (P + r"\河北省衡水市2025届高三下学期3月联考数学试卷\河北省衡水市2025届高三下学期3月联考数学试卷.pdf",
     "河北省衡水市2025届高三下学期3月联考数学试卷", "exam"),
    (P + r"\河北省石家庄市2025届高三下学期教学质量检测（一）数学试题\2025年3月石家庄数学质检一答案.pdf",
     "河北省石家庄市2025届高三下学期教学质量检测（一）数学试题答案", "ans"),
    (P + r"\河北省石家庄市2025届高三下学期教学质量检测（一）数学试题\河北省石家庄市2025届高三下学期教学质量检测（一）数学试题.pdf",
     "河北省石家庄市2025届高三下学期教学质量检测（一）数学试题", "exam"),
    (P + r"\河北省邢台市2024-2025学年高三下学期3月调研考试数学试题\河北省邢台市2024-2025学年高三下学期3月调研考试数学试题.pdf",
     "河北省邢台市2024-2025学年高三下学期3月调研考试数学试题", "exam"),
    (P + r"\河南省新乡、驻马店市部分学校2024-2025学年高三下学期3月模拟考试数学试卷\河南省新乡、驻马店市部分学校2024-2025学年高三下学期3月模拟考试数学试卷.pdf",
     "河南省新乡、驻马店市部分学校2024-2025学年高三下学期3月模拟考试数学试卷", "exam"),
    (P + r"\河南省郑州市2024-2025学年高三下学期第二次质量预测数学试题\2025届河南省郑州市3月高三二模数学试题.pdf",
     "河南省郑州市2024-2025学年高三下学期第二次质量预测数学试题", "exam"),
    (P + r"\河南省郑州市2024-2025学年高三下学期第二次质量预测数学试题\郑州数学答案.pdf",
     "河南省郑州市2024-2025学年高三下学期第二次质量预测数学试题答案", "ans"),
    (P + r"\黑龙江省名校协作体2025届高三下学期一模考试数学试题\黑龙江省名校协作体2025届高三下学期一模考试数学试题.pdf",
     "黑龙江省名校协作体2025届高三下学期一模考试数学试题", "exam"),
    (P + r"\湖北省八市2025届高三下学期3月联考数学试卷\湖北省八市2025届高三下学期3月联考数学试卷.pdf",
     "湖北省八市2025届高三下学期3月联考数学试卷", "exam"),
    (P + r"\湖北省八市2025届高三下学期3月联考数学试卷\数学三月联考答案(1).pdf",
     "湖北省八市2025届高三下学期3月联考数学试卷答案", "ans"),
    (P + r"\湖北省七市州2024-2025学年高三下学期3月联合统一调研测试数学试题\湖北省七市州2024-2025学年高三下学期3月联合统一调研测试数学试题.pdf",
     "湖北省七市州2024-2025学年高三下学期3月联合统一调研测试数学试题", "exam"),
    (P + r"\湖北省十一校2024-2025学年高三第二次联考数学试卷\湖北省十一校2024-2025学年高三第二次联考数学试卷.pdf",
     "湖北省十一校2024-2025学年高三第二次联考数学试卷", "exam"),
    (P + r"\湖南省长沙市雅礼中学2025届高三一模数学试题\雅礼中学2025届高三一模数学试题.pdf",
     "雅礼中学2025届高三一模数学试题", "exam"),
    (P + r"\湖南省长沙市雅礼中学2025届高三一模数学试题\雅礼中学高三一模数学答案.pdf",
     "雅礼中学2025届高三一模数学答案", "ans"),
    (P + r"\江苏省苏锡常镇2024-2025学年高三下学期教学情况调研（一）数学试题\江苏省苏锡常镇2024-2025学年高三下学期教学情况调研（一）数学试题.pdf",
     "江苏省苏锡常镇2024-2025学年高三下学期教学情况调研（一）数学试题", "exam"),
    (P + r"\江苏省苏锡常镇2024-2025学年高三下学期教学情况调研（一）数学试题\苏锡常镇一模答案.pdf",
     "江苏省苏锡常镇2024-2025学年高三下学期教学情况调研（一）数学试题答案", "ans"),
    (P + r"\江西省赣州市2025届高三下学期3月摸底考试（一模）数学试卷\江西省赣州市2025届高三下学期3月摸底考试（一模）数学试卷.pdf",
     "江西省赣州市2025届高三下学期3月摸底考试（一模）数学试卷", "exam"),
    (P + r"\山东省烟台市、德州、东营市2025届高三一模数学试题\山东省烟台市2024-2025学年高三一模数学试题.docx",
     "山东省烟台市2024-2025学年高三一模数学试题", "exam"),
    (P + r"\山东省烟台市、德州、东营市2025届高三一模数学试题\数学2025诊断性测试参考答案.pdf",
     "山东省烟台市2024-2025学年高三一模数学试题参考答案", "ans"),
    (P + r"\陕西省2025届高三下学期高考适应性检测数学试题\陕西省2025届高三下学期高考适应性检测数学试题.pdf",
     "陕西省2025届高三下学期高考适应性检测数学试题", "exam"),
    (P + r"\陕西省西安市部分学校2025届高三联考数学试题\陕西省西安市部分学校2025届高三联考数学试题.pdf",
     "陕西省西安市部分学校2025届高三联考数学试题", "exam"),
    (P + r"\浙江省杭州市金丽衢十二校2024-2025学年高三下学期(3月)第二次联考数学试题\金丽衢十二校数学试卷.pdf",
     "浙江省杭州市金丽衢十二校2024-2025学年高三下学期3月第二次联考数学试题", "exam"),
    (P + r"\浙江省杭州市金丽衢十二校2024-2025学年高三下学期(3月)第二次联考数学试题\数学参考答案及评分标准.pdf",
     "浙江省杭州市金丽衢十二校2024-2025学年高三下学期3月第二次联考数学试题参考答案", "ans"),
    (P + r"\浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题\浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题.docx",
     "浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题", "exam"),
    (P + r"\浙江省宁波市“十校”2025届高三下学期3月联考数学试卷\宁波十校数学试卷.pdf",
     "浙江省宁波市十校2025届高三下学期3月联考数学试卷", "exam"),
    (P + r"\浙江省宁波市“十校”2025届高三下学期3月联考数学试卷\数学（宁波十校）答案.pdf",
     "浙江省宁波市十校2025届高三下学期3月联考数学试卷答案", "ans"),
    (P + r"\浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题\浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题.pdf",
     "浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题", "exam"),
    (P + r"\浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题\浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题参考答案.pdf",
     "浙江省天域全国名校协作体2024-2025学年高三下学期3月联考数学试题参考答案", "ans"),
    (P + r"\河北省邯郸市2025届高三第三次调研监测（一模）数学试题.pdf",
     "河北省邯郸市2025届高三第三次调研监测（一模）数学试题", "exam"),
    (P + r"\黑龙江省部分学校2024-2025学年高三第二次检测模拟考试数学试题.pdf",
     "黑龙江省部分学校2024-2025学年高三第二次检测模拟考试数学试题", "exam"),
    # -- 顶层散落（试题+答案合一 PDF）--
    (r"深圳中学2025届高三上学期第一次阶段考试（10月）数学试题+答案.pdf",
     "广东省深圳市深圳中学2025届高三上学期第一次阶段考试（10月）数学试题+答案", "exam"),
    (r"湖南长郡中学2025年高三下学期月考（七）数学试题+答案.pdf",
     "湖南省长郡中学2025年高三下学期月考（七）数学试题+答案", "exam"),
    (r"雅礼中学2025届高三第六次月考数学试题+答案.pdf",
     "雅礼中学2025届高三第六次月考数学试题+答案", "exam"),
    (r"浙江杭州学军中学2025届高三下学期2月月考数学试题+答案.pdf",
     "浙江省杭州学军中学2025届高三下学期2月月考数学试题+答案", "exam"),
]

_client = None

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_token():
    import yaml
    cfg = Path.home() / ".mineru" / "config.yaml"
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    return data["token"]

def get_client():
    global _client
    if _client is None:
        from mineru import MinerU
        _client = MinerU(token=load_token())
    return _client

def save_images(res, img_dir: Path):
    imgs = getattr(res, "images", None) or []
    n = 0
    if not imgs:
        return 0
    img_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(imgs, dict):
        for name, data in imgs.items():
            if data:
                (img_dir / os.path.basename(name)).write_bytes(data)
                n += 1
    else:
        for i, im in enumerate(imgs):
            name = (getattr(im, "name", None) or getattr(im, "filename", None)
                    or f"img_{i}.png")
            data = getattr(im, "data", None) or getattr(im, "content", None)
            if data:
                (img_dir / os.path.basename(name)).write_bytes(data)
                n += 1
    return n

def ocr_one(src: Path, target: str):
    md_path = MATH_OUT / f"{target}.md"
    if md_path.exists() and md_path.stat().st_size > 100:
        return ("skip", target, 0)
    staged = STAGE / f"{target}.pdf"
    if not staged.exists():
        if src.suffix.lower() == ".pdf":
            shutil.copy2(src, staged)
        else:
            raise FileNotFoundError(f"staged pdf missing (convert docx first): {staged}")
    cli = get_client()
    res = cli.extract(str(staged), model="vlm", ocr=True, language="ch",
                      formula=True, table=True, timeout=1800)
    md = getattr(res, "markdown", None) or getattr(res, "md", None) or ""
    if not md or len(md) < 200:
        raise RuntimeError(f"empty markdown ({len(md)} chars)")
    md_path.write_text(md, encoding="utf-8")
    n = save_images(res, MATH_OUT / target / "images")
    return ("ok", target, n)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    STAGE.mkdir(parents=True, exist_ok=True)
    jobs = []
    missing = []
    for src_rel, target, kind in MANIFEST:
        src = BASE / src_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        jobs.append((src, target, kind))

    pending = [(s, t, k) for s, t, k in jobs
               if not (MATH_OUT / f"{t}.md").exists()
               or (MATH_OUT / f"{t}.md").stat().st_size <= 100]

    print(f"total={len(jobs)}  done={len(jobs)-len(pending)}  pending={len(pending)}")
    if missing:
        print("MISSING SOURCES:")
        for m in missing:
            print("  " + m)
    if args.list:
        for s, t, k in pending:
            print(f"  [{k}] {t}")
        return
    if not pending:
        print("nothing to do")
        return

    log(f"=== OCR batch start: {len(pending)} pending, workers={args.workers} ===")
    ok = fail = 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(ocr_one, s, t): (s, t) for s, t, k in pending}
        for fut in as_completed(futs):
            s, t = futs[fut]
            try:
                status, target, n = fut.result()
                log(f"{status.upper()}: {target} (imgs={n})")
                if status == "ok":
                    ok += 1
            except Exception as e:
                fail += 1
                failures.append((t, str(e)))
                log(f"FAIL: {t} :: {type(e).__name__}: {e}")
    log(f"=== OCR batch done: ok={ok} fail={fail} ===")
    if failures:
        log("FAILED LIST:")
        for t, e in failures:
            log(f"  {t} :: {e[:120]}")

if __name__ == "__main__":
    main()
