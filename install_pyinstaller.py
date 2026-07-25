
import os
import sys
import urllib.request

# 完全禁用代理
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 禁用 urllib 的代理
proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)
urllib.request.install_opener(opener)

# 现在尝试使用 pip 安装
import subprocess

print("正在安装 PyInstaller...")
result = subprocess.run(
    [
        sys.executable, "-m", "pip", "install", "PyInstaller",
        "-i", "https://mirrors.cloud.tencent.com/pypi/simple",
        "--trusted-host", "mirrors.cloud.tencent.com"
    ],
    env=os.environ
)

if result.returncode == 0:
    print("\n✓ PyInstaller 安装成功！")
else:
    print(f"\n✗ 安装失败，错误代码: {result.returncode}")
    sys.exit(1)
