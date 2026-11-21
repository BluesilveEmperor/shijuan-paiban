# tests/legacy/ — 归档回归测试

这三个用例测的是 `scripts/legacy/md2tex.py` 的清洗逻辑（`clean` / `fix_dollar_signs` /
表格与括号修复），属于 MD→TeX 直转时代。主流程改走 IR 后不再随 `run_all.py` 运行。

- 手动运行：`python tests/legacy/test_fixed.py`（同 `test_round2.py` / `test_round3.py`）
- `run_all.py` 只 glob `tests/test_*.py`，不递归本目录
- 若恢复 `md2tex.py` 到主流程，把这三个文件移回 `tests/` 即可
