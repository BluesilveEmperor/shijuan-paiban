#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py - 运行 tests/ 下全部回归测试

用法:
  python tests/run_all.py          # 跑全部
  python tests/run_all.py -v       # 显示每个测试的完整输出

退出码: 0 全部通过 / 1 存在失败
"""

import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent


def main():
    verbose = "-v" in sys.argv
    with_tex = "--with-tex" in sys.argv
    files = sorted(TESTS_DIR.glob("test_*.py"))
    if not files:
        print("[FATAL] tests/ 下没有 test_*.py")
        return 1

    failed = []
    for f in files:
        # 本分支只有数学 fixture：显式固定学科，避免环境变量残留把用例带偏。
        # test_subject.py 例外——它验证的正是学科解析本身。
        env = dict(os.environ)
        if f.name == "test_subject.py":
            env.pop("SHIJUAN_SUBJECT", None)
        else:
            env["SHIJUAN_SUBJECT"] = "math"
        argv = [sys.executable, str(f)]
        result = subprocess.run(
            argv, cwd=str(ROOT),
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        ok = result.returncode == 0
        print(f"{'[PASS]' if ok else '[FAIL]'} {f.name}")
        if verbose or not ok:
            for line in (result.stdout or "").strip().split("\n"):
                if line.startswith(("FAIL", "  actual", "  expected", "Traceback",
                                    "  File", "    ")) or not ok:
                    print("       " + line)
            if result.stderr.strip():
                print("       " + result.stderr.strip().replace("\n", "\n       "))
        if not ok:
            failed.append(f.name)

    print()
    if failed:
        print(f"{len(failed)}/{len(files)} 个测试文件失败: {', '.join(failed)}")
        return 1
    print(f"全部 {len(files)} 个测试文件通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
