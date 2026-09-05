#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_repo.py - 双仓库并行 clone 更新逻辑

从 GitHub 和 GitCode 同时检查更新，若有更新则并行 clone，
哪个先完成就用哪个安装。

仓库地址：
  GitHub: https://github.com/BluesilveEmperor/shijuan-paiban.git
  GitCode: https://gitcode.com/GLY-NXD/shijuan-paiban.git

用法:
  python scripts/update_repo.py              # 检查并更新
  python scripts/update_repo.py --check      # 仅检查是否有更新
  python scripts/update_repo.py --force      # 强制重新 clone
"""

import os
import subprocess
import sys
import tempfile
import shutil
import threading
import time


# 仓库配置
REPOS = {
    "github": {
        "url": "https://github.com/BluesilveEmperor/shijuan-paiban.git",
        "name": "github",
    },
    "gitcode": {
        "url": "https://gitcode.com/GLY-NXD/shijuan-paiban.git",
        "name": "gitcode",
    },
}

# 技能目录（脚本所在目录的上级）
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_local_commit():
    """获取本地当前 commit hash"""
    try:
        result = subprocess.run(
            ["git", "-C", SKILL_DIR, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_remote_commit(repo_url):
    """获取远程仓库的最新 commit hash（不 clone）"""
    try:
        result = subprocess.run(
            ["git", "ls-remote", repo_url, "HEAD"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # 输出格式: "<hash>\tHEAD"
            parts = result.stdout.strip().split()
            if parts:
                return parts[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def check_updates():
    """检查所有远程仓库是否有更新"""
    local = get_local_commit()
    if not local:
        print("[WARN] 无法获取本地版本（可能不是 git 仓库）")
        return {name: True for name in REPOS}  # 无法判断，全部视为有更新

    print(f"[INFO] 本地版本: {local[:8]}")
    updates = {}
    for name, config in REPOS.items():
        remote = get_remote_commit(config["url"])
        if remote:
            has_update = remote != local
            status = "有更新" if has_update else "最新"
            print(f"[INFO] {name}: 远程 {remote[:8]} → {status}")
            updates[name] = has_update
        else:
            print(f"[WARN] {name}: 无法连接")
            updates[name] = False
    return updates


def clone_repo(repo_url, dest_dir, result_dict, key):
    """在后台线程中 clone 仓库"""
    start_time = time.time()
    try:
        print(f"[INFO] 开始 clone {key}...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, dest_dir],
            capture_output=True, text=True, timeout=120
        )
        elapsed = time.time() - start_time
        if result.returncode == 0:
            print(f"[OK] {key} clone 完成 ({elapsed:.1f}s)")
            result_dict[key] = {"success": True, "dir": dest_dir, "time": elapsed}
        else:
            print(f"[WARN] {key} clone 失败: {result.stderr[:100]}")
            result_dict[key] = {"success": False, "error": result.stderr[:200]}
    except subprocess.TimeoutExpired:
        print(f"[WARN] {key} clone 超时")
        result_dict[key] = {"success": False, "error": "timeout"}
    except Exception as e:
        print(f"[WARN] {key} clone 异常: {e}")
        result_dict[key] = {"success": False, "error": str(e)}


def parallel_clone(repos_to_clone):
    """并行 clone 多个仓库，返回第一个成功的"""
    result_dict = {}
    threads = []
    temp_dirs = {}

    for key, url in repos_to_clone.items():
        # 为每个仓库创建临时目录
        temp_dir = tempfile.mkdtemp(prefix=f"repo_{key}_")
        temp_dirs[key] = temp_dir
        t = threading.Thread(target=clone_repo, args=(url, temp_dir, result_dict, key))
        threads.append(t)

    # 启动所有线程
    print(f"[INFO] 开始并行 clone {len(threads)} 个仓库...")
    start_time = time.time()
    for t in threads:
        t.start()

    # 等待第一个成功或全部完成
    first_success = None
    while any(t.is_alive() for t in threads):
        for key, result in result_dict.items():
            if result.get("success") and first_success is None:
                first_success = key
                break
        if first_success:
            break
        time.sleep(0.5)

    # 等待所有线程完成（或超时）
    for t in threads:
        t.join(timeout=10)

    elapsed = time.time() - start_time
    print(f"[INFO] 并行 clone 完成 ({elapsed:.1f}s)")

    # 返回第一个成功的结果
    if first_success:
        return first_success, temp_dirs[first_success]

    # 如果没有第一个成功的，检查是否有任何成功的
    for key, result in result_dict.items():
        if result.get("success"):
            return key, temp_dirs[key]

    return None, None


def install_from_clone(clone_dir):
    """从 clone 的目录安装到技能目录"""
    print(f"[INFO] 从 {clone_dir} 安装...")

    # 需要复制的文件/目录
    items_to_copy = [
        "SKILL.md",
        "README.md",
        "templates",
        "scripts",
        "docs",
        "evals",
    ]

    copied = []
    for item in items_to_copy:
        src = os.path.join(clone_dir, item)
        dst = os.path.join(SKILL_DIR, item)
        if os.path.exists(src):
            try:
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                copied.append(item)
            except Exception as e:
                print(f"[WARN] 复制 {item} 失败: {e}")

    print(f"[OK] 已安装: {', '.join(copied)}")
    return len(copied) > 0


def cleanup_temp_dirs(temp_dirs):
    """清理临时目录"""
    for key, temp_dir in temp_dirs.items():
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="双仓库并行更新")
    parser.add_argument("--check", action="store_true", help="仅检查是否有更新")
    parser.add_argument("--force", action="store_true", help="强制重新 clone")
    args = parser.parse_args()

    print("=" * 50)
    print("技能仓库更新检查")
    print("=" * 50)

    # 步骤 1: 检查更新
    if args.force:
        repos_to_clone = {name: config["url"] for name, config in REPOS.items()}
        print("[INFO] 强制更新模式")
    else:
        updates = check_updates()
        repos_to_clone = {
            name: REPOS[name]["url"]
            for name, has_update in updates.items()
            if has_update
        }
        if not repos_to_clone:
            print("[RESULT] 技能已是最新版本")
            sys.exit(0)

    if args.check:
        print(f"[RESULT] 有更新可用: {', '.join(repos_to_clone.keys())}")
        sys.exit(0)

    # 步骤 2: 并行 clone
    print(f"[INFO] 将从以下仓库更新: {', '.join(repos_to_clone.keys())}")
    temp_dirs = {}
    try:
        # 为所有要 clone 的仓库创建临时目录
        for key in repos_to_clone:
            temp_dirs[key] = tempfile.mkdtemp(prefix=f"repo_{key}_")

        # 并行 clone
        winner, winner_dir = parallel_clone(repos_to_clone)

        if winner:
            print(f"[OK] 使用 {winner} 的副本安装")
            if install_from_clone(winner_dir):
                print("[RESULT] 技能更新成功！")
                sys.exit(0)
            else:
                print("[ERROR] 安装失败")
                sys.exit(1)
        else:
            print("[ERROR] 所有仓库 clone 失败")
            sys.exit(1)
    finally:
        cleanup_temp_dirs(temp_dirs)


if __name__ == "__main__":
    main()
