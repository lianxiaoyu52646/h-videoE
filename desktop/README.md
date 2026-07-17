# VideoEnglish Desktop

桌面版采用 `Tauri + FastAPI sidecar`：

- `app.desktop_runtime` 启动本地 API、SQLite 和常驻 worker
- `desktop/tauri` 提供 Windows 桌面壳
- `desktop/build_backend.py` 用 PyInstaller 打包 Python sidecar

## 本地开发

1. 安装 Python 依赖：`pip install -r requirements.txt`
2. 启动后端：`python -m app.desktop_runtime`
3. 进入 `desktop/tauri`
4. 安装 Tauri CLI：`npm install`
5. 运行桌面壳：`npm run dev`

开发模式下，Tauri 会从仓库根目录调用 `python -m app.desktop_runtime`。

## 打包 Windows EXE

1. 安装 Python 依赖：`pip install -r requirements.txt`
2. 生成 sidecar：`python desktop/build_backend.py`
3. 进入 `desktop/tauri`
4. 安装 Tauri CLI：`npm install`
5. 构建桌面安装包：`npm run build`

PyInstaller 产物会输出到 `desktop/sidecar/`，Tauri 构建时会把它作为资源一并打包。
