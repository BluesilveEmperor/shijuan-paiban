# 仓库运维

> 排版任务完成后的仓库检查与更新动作。与排版流程无关，按需执行。

## 检查 Git 环境

```bash
python scripts/ops/setup_git.py          # 检查安装状态；缺失时引导安装
python scripts/ops/setup_git.py --check  # 只检查
```

按电脑名配置 `user.name` / `user.email`，避免不同机器提交同一作者。

## 双仓库并行更新

本技能镜像在两个仓库：

| 仓库 | 地址 |
|------|------|
| GitHub | https://github.com/BluesilveEmperor/shijuan-paiban.git |
| GitCode | https://gitcode.com/GSIM-NHD/shijuan-paiban.git |

```bash
python scripts/ops/update_repo.py --check   # 仅检查是否有更新
python scripts/ops/update_repo.py           # 检查并更新（并行 clone，先完成者胜）
python scripts/ops/update_repo.py --force   # 强制重新 clone
```

更新会把 `SKILL.md` / `README.md` / `templates` / `scripts` / `docs` / `evals`
覆盖到技能目录。**本地有未提交改动时先确认**，否则会被覆盖。
