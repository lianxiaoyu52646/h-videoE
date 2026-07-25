
import os
import sys
import site
from pathlib import Path

# 获取用户级别的 pip 配置目录
user_config_dir = site.getuserbase()
pip_config_dir = Path(user_config_dir) / "pip"
pip_config_dir.mkdir(parents=True, exist_ok=True)

pip_ini_path = pip_config_dir / "pip.ini"

# 创建临时禁用代理的 pip.ini
pip_config_content = """
[global]
proxy = 
index-url = https://mirrors.cloud.tencent.com/pypi/simple
trusted-host = mirrors.cloud.tencent.com
"""

with open(pip_ini_path, 'w', encoding='utf-8') as f:
    f.write(pip_config_content)

print(f"已创建临时配置文件: {pip_ini_path}")
print("现在尝试安装 PyInstaller...")

# 现在尝试安装
import subprocess

result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "PyInstaller"],
    capture_output=True,
    text=True
)

print("\n标准输出:")
print(result.stdout)

if result.stderr:
    print("\n标准错误:")
    print(result.stderr)

if result.returncode == 0:
    print("\nPyInstaller 安装成功！")
else:
    print(f"\n安装失败，退出代码: {result.returncode}")
    # 恢复原来的配置（如果有的话）
    print("请检查网络设置或手动安装 PyInstaller")
