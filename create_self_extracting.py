
import os
import sys
import tempfile
import zipfile
import subprocess
import shutil
from pathlib import Path

def main():
    # 确定源文件夹
    source_dir = Path(__file__).parent / "dist" / "VideoEnglish" / "VideoEnglish"
    if not source_dir.exists():
        print(f"错误: 找不到源文件夹: {source_dir}")
        return

    # 创建一个临时目录来存放文件
    temp_dir = tempfile.mkdtemp(prefix="VideoEnglish_")
    print(f"正在处理文件...")

    try:
        # 把源文件夹复制到临时目录
        dest_dir = Path(temp_dir) / "VideoEnglish"
        shutil.copytree(source_dir, dest_dir)

        # 创建一个启动脚本
        startup_script = Path(temp_dir) / "start.bat"
        with open(startup_script, "w", encoding="gbk") as f:
            f.write("@echo off\n")
            f.write("cd /d \"%~dp0VideoEnglish\"\n")
            f.write("start VideoEnglish.exe\n")

        # 创建一个简单的自解压程序
        # 我们将使用PyInstaller来打包这个脚本
        self_extractor_script = Path(temp_dir) / "self_extract.py"
        with open(self_extractor_script, "w", encoding="utf-8") as f:
            f.write('''
import os
import sys
import tempfile
import zipfile
import subprocess
from pathlib import Path

# 这是嵌入的zip数据，稍后我们会填充
ZIP_DATA = b''

def main():
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="VideoEnglish_temp_")
    
    try:
        # 把嵌入的zip数据解压出来
        zip_path = Path(temp_dir) / "app.zip"
        with open(zip_path, "wb") as f:
            f.write(ZIP_DATA)
        
        extract_dir = Path(temp_dir) / "VideoEnglish"
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 启动程序
        exe_path = extract_dir / "VideoEnglish" / "VideoEnglish.exe"
        subprocess.Popen([str(exe_path)], cwd=str(extract_dir / "VideoEnglish"))
        
        # 稍微等一下让程序启动，然后可以退出
        import time
        time.sleep(2)
        
    except Exception as e:
        input(f"错误: {e}\\n按回车键退出...")

if __name__ == "__main__":
    main()
''')

        print(f"文件已准备好: {temp_dir}")
        print("\n现在你需要手动执行以下步骤来创建自解压exe:")
        print("1. 首先把 VideoEnglish 文件夹打包成 zip")
        print("2. 然后我们可以用 PyInstaller 打包一个简单的自解压程序")

        # 先创建一个zip
        print("\n正在创建应用程序zip...")
        app_zip = Path(__file__).parent / "dist" / "VideoEnglish_app.zip"
        if app_zip.exists():
            app_zip.unlink()

        with zipfile.ZipFile(app_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_dir.parent)
                    zipf.write(file_path, arcname)

        print(f"应用程序zip已创建: {app_zip}")

        # 创建一个简单的自解压脚本
        print("\n正在创建自解压脚本...")
        extract_dir = Path(__file__).parent / "dist" / "self_extract"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        extract_script = extract_dir / "extract_and_run.py"
        with open(extract_script, "w", encoding="utf-8") as f:
            f.write(f'''
import os
import sys
import tempfile
import zipfile
import subprocess
import shutil
from pathlib import Path

# 编译时会把zip数据嵌入在这里
ZIP_DATA = b''

def main():
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="VideoEnglish_")
    
    try:
        # 先尝试查找同目录下的zip（开发模式）
        script_dir = Path(__file__).parent
        zip_path = script_dir / "VideoEnglish_app.zip"
        
        if not zip_path.exists() and ZIP_DATA:
            # 使用嵌入的数据
            zip_path = Path(temp_dir) / "app.zip"
            with open(zip_path, "wb") as f:
                f.write(ZIP_DATA)
        
        if not zip_path.exists():
            input("找不到应用程序文件，按回车键退出...")
            return
        
        # 解压应用程序
        extract_path = Path(temp_dir) / "VideoEnglish"
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        
        # 找到exe并运行
        exe_path = extract_path / "VideoEnglish" / "VideoEnglish.exe"
        
        if not exe_path.exists():
            input("找不到应用程序，按回车键退出...")
            return
        
        # 启动应用程序
        subprocess.Popen([str(exe_path)], cwd=str(extract_path / "VideoEnglish"))
        
        # 等待一下让程序启动
        import time
        time.sleep(1.5)
        
    except Exception as e:
        input(f"错误: {{e}}\\n按回车键退出...")

if __name__ == "__main__":
    main()
''')

        # 复制zip到extract目录
        shutil.copy(app_zip, extract_dir / "VideoEnglish_app.zip")

        print("\n✅ 自解压程序准备完毕！")
        print(f"现在我们尝试构建它...")

        # 尝试构建，但可能会遇到同样的网络问题
        print("\n尝试构建自解压exe...")
        os.chdir(extract_dir)

        try:
            # 先测试一下脚本能不能运行
            subprocess.run([sys.executable, "extract_and_run.py"], cwd=extract_dir)
            print("自解压脚本可以运行！")

        except Exception as e:
            print(f"测试运行遇到问题: {e}")

        print(f"\n📁 所有文件都在这里: {extract_dir}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
