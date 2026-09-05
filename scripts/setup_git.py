#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_git.py - 检查 git 安装状态，未安装则引导安装，并按电脑名称配置用户名和邮箱

用法:
  python scripts/setup_git.py          # 检查并配置
  python scripts/setup_git.py --check  # 仅检查，不安装
"""

import os
import platform
import subprocess
import sys


def get_computer_name():
    """获取电脑名称作为 git 用户名"""
    # Windows: COMPUTERNAME 环境变量
    # macOS/Linux: hostname
    name = os.environ.get("COMPUTERNAME", "")
    if not name:
        try:
            name = platform.node()
        except Exception:
            name = "unknown"
    # 清理名称：移除特殊字符，替换空格为连字符
    name = name.strip().replace(" ", "-")
    # 移除 Windows 域名后缀（如 DESKTOP-ABC123.domain → DESKTOP-ABC123）
    if "." in name:
        name = name.split(".")[0]
    return name


def check_git_installed():
    """检查 git 是否已安装"""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[OK] Git 已安装: {version}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print("[WARN] Git 未安装")
    return False


def check_git_configured():
    """检查 git 用户名和邮箱是否已配置"""
    try:
        name_result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True, text=True, timeout=5
        )
        email_result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, timeout=5
        )
        name = name_result.stdout.strip() if name_result.returncode == 0 else ""
        email = email_result.stdout.strip() if email_result.returncode == 0 else ""
        if name and email:
            print(f"[OK] Git 已配置: {name} <{email}>")
            return True
        else:
            print(f"[WARN] Git 配置不完整 (name={name or '(空)'}, email={email or '(空)'})")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def configure_git(computer_name):
    """配置 git 用户名和邮箱"""
    email = f"{computer_name.lower()}@users.noreply.github.com"
    print(f"[INFO] 配置 Git 用户: {computer_name} <{email}>")

    try:
        subprocess.run(
            ["git", "config", "--global", "user.name", computer_name],
            check=True, timeout=10
        )
        subprocess.run(
            ["git", "config", "--global", "user.email", email],
            check=True, timeout=10
        )
        print("[OK] Git 配置完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git 配置失败: {e}")
        return False


def get_embedded_installer():
    """获取嵌入的 Git 安装包路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    installer_dir = os.path.join(script_dir, "installers")
    # 查找 Git 安装包
    for fname in os.listdir(installer_dir):
        if fname.lower().startswith("git-") and fname.lower().endswith(".exe"):
            return os.path.join(installer_dir, fname)
    return None


def install_git_windows():
    """在 Windows 上安装 git"""
    print("[INFO] 正在安装 Git for Windows...")

    # 方法 1: 使用嵌入的安装包
    embedded = get_embedded_installer()
    if embedded:
        print(f"[INFO] 使用嵌入的安装包: {os.path.basename(embedded)}")
        try:
            # 静默安装: /SILENT 或 /VERYSILENT
            # Git for Windows 支持 /SILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
            result = subprocess.run(
                [embedded, "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-",
                 "/CLOSEAPPLICATIONS", "/COMPONENTS=icons,ext\\reg\\shellhere,assoc,assoc_sh"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                print("[OK] Git 安装成功（嵌入安装包）")
                # 刷新 PATH（安装后 git 可能在新的 PATH 中）
                # 将 Git 的 cmd 目录添加到当前进程的 PATH
                git_cmd_paths = [
                    r"C:\Program Files\Git\cmd",
                    r"C:\Program Files (x86)\Git\cmd",
                ]
                for p in git_cmd_paths:
                    if os.path.isdir(p):
                        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
                        break
                return True
            else:
                print(f"[WARN] 静默安装返回码: {result.returncode}")
                print(f"[WARN] stderr: {result.stderr[:200] if result.stderr else '(空)'}")
        except subprocess.TimeoutExpired:
            print("[WARN] 安装超时")
        except Exception as e:
            print(f"[WARN] 安装异常: {e}")

    # 方法 2: 尝试 winget（Windows 10/11 自带）
    try:
        print("[INFO] 尝试使用 winget 安装...")
        result = subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--accept-source-agreements", "--accept-package-agreements"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("[OK] Git 安装成功（winget）")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 方法 3: 尝试 scoop（如果已安装）
    try:
        print("[INFO] 尝试使用 scoop 安装...")
        result = subprocess.run(
            ["scoop", "install", "git"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("[OK] Git 安装成功（scoop）")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 方法 4: 提供手动安装指引
    print("[WARN] 自动安装失败，请手动安装 Git:")
    print("  1. 访问 https://git-scm.com/download/win")
    print("  2. 下载并运行安装程序")
    print("  3. 使用默认设置完成安装")
    print("  4. 重新运行此脚本")
    return False


def install_git():
    """根据操作系统安装 git"""
    system = platform.system()
    if system == "Windows":
        return install_git_windows()
    elif system == "Darwin":
        # macOS: 尝试 brew
        try:
            print("[INFO] 尝试使用 brew 安装...")
            result = subprocess.run(
                ["brew", "install", "git"],
                capture_output=True, text=True, timeout=300
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("[WARN] 请先安装 Homebrew: https://brew.sh")
            return False
    elif system == "Linux":
        # Linux: 尝试 apt
        try:
            print("[INFO] 尝试使用 apt 安装...")
            result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", "git"],
                capture_output=True, text=True, timeout=300
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("[WARN] 请手动安装: sudo apt-get install git")
            return False
    else:
        print(f"[ERROR] 不支持的操作系统: {system}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Git 安装检查与配置")
    parser.add_argument("--check", action="store_true", help="仅检查，不安装")
    args = parser.parse_args()

    print("=" * 50)
    print("Git 环境检查")
    print("=" * 50)

    # 步骤 1: 检查 git 是否安装
    if not check_git_installed():
        if args.check:
            print("[RESULT] Git 未安装")
            sys.exit(1)
        if not install_git():
            print("[RESULT] Git 安装失败")
            sys.exit(1)
        # 安装后重新检查
        if not check_git_installed():
            print("[ERROR] 安装后仍无法检测到 Git，请重启终端后重试")
            sys.exit(1)

    # 步骤 2: 检查是否已配置
    if check_git_configured():
        print("[RESULT] Git 环境就绪")
        sys.exit(0)

    # 步骤 3: 配置 git
    if args.check:
        print("[RESULT] Git 未配置")
        sys.exit(1)

    computer_name = get_computer_name()
    print(f"[INFO] 电脑名称: {computer_name}")
    if configure_git(computer_name):
        print("[RESULT] Git 配置完成")
        sys.exit(0)
    else:
        print("[RESULT] Git 配置失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
