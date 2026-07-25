# VideoEnglish 英语学习系统

自用英语学习工具：**看视频、读文章、背词书、FSRS 复习**，全部在本地运行，数据保存在本机。

打包成 **Windows 可执行文件** 后，可直接把文件夹压缩发给其他人；对方 **双击 `VideoEnglish.exe` 即可使用**，无需安装 Python、浏览器插件或其他依赖。

---

## 功能概览

| 模块 | 页面 | 说明 |
|------|------|------|
| 视频学习 | `/learn` | 输入 B 站 / YouTube 链接，自动抓取字幕，中英对照、点词查义、收藏生词 |
| 阅读 | `/read`、`/reader` | 粘贴文本、上传 EPUB/PDF，或从内置书库导入；自动分块翻译，支持高亮、笔记、书签 |
| 词书 | `/wordbooks` | 内置 CET4/6、考研、托福、雅思、GRE 等词书，可安装与学习 |
| 生词复习 | `/vocab` | FSRS 间隔重复算法，支持默写与多种练习模式 |

桌面版默认 **免登录**（自动创建本地用户），无需账号即可使用全部功能。

---

## 技术架构

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLModel + Alembic |
| 数据库 | SQLite |
| 前端 | 纯静态 HTML / CSS / JavaScript |
| 翻译 | 有道翻译、deep-translator |
| 视频 | yt-dlp、faster-whisper、bilibili-api |
| 阅读 | EPUB / PDF 解析（ebooklib、pymupdf） |
| 复习 | FSRS 算法 |
| 桌面壳（可选） | Tauri + PyInstaller sidecar |
| 测试 | pytest |

---

## 项目结构

```
h-videoE/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── desktop_runtime.py      # 桌面模式运行时
│   ├── standalone_launcher.py  # 独立 EXE 启动入口
│   ├── models.py               # 数据模型
│   ├── routers/                # API 路由（auth、videos、readings、wordbooks 等）
│   ├── services/               # 业务逻辑（字幕、翻译、词典、FSRS 等）
│   ├── static/                 # 前端页面
│   └── assets/curated/         # 内置词书、书库数据
├── desktop/
│   ├── build_backend.py        # 打包 Tauri sidecar
│   ├── build_standalone.py     # 打包独立可分发 EXE
│   └── tauri/                  # Tauri 桌面壳（可选，需 Rust）
├── extension/                  # Chrome 扩展（可选，Web 模式用）
├── scripts/
│   └── build_standalone.ps1    # 一键打包脚本
├── tests/                      # 测试
└── tools/                      # 数据同步、审计脚本
```

---

## 给使用者：双击即用

1. 解压收到的 **`VideoEnglish`** 文件夹（不要只复制 exe，需保留整个文件夹）
2. 双击 **`VideoEnglish.exe`**
3. 等待几秒，浏览器会自动打开应用（默认 `http://127.0.0.1:18555`）
4. 关闭黑色命令行窗口即退出程序

### 数据保存在哪

用户的学习数据、词书、阅读进度等保存在：

```
%LOCALAPPDATA%\VideoEnglish\
├── data\videoenglish.sqlite3   # 数据库
├── cache\                      # 缓存（书籍、翻译等）
└── logs\                       # 日志
```

卸载时删除上述文件夹即可清除全部数据。

### 系统要求

- Windows 10 / 11（64 位）
- 无需安装 Python、Node.js、Chrome 插件
- 需要能访问互联网（抓取视频字幕、在线翻译等）

---

## 给自己：打包成 EXE 分发

### 方式一：独立 EXE（推荐，仅需 Python）

适合快速打包、直接压缩文件夹发给别人。

**环境：** 已安装 Python 3.11+

```powershell
# 在项目根目录执行
powershell -ExecutionPolicy Bypass -File scripts/build_standalone.ps1
```

或手动执行：

```powershell
pip install -r requirements.txt
python desktop/build_standalone.py
```

**产物位置：**

```
dist/VideoEnglish/
├── VideoEnglish.exe    # 双击启动
└── _internal/          # 运行时依赖，需一并保留
```

将整个 **`dist/VideoEnglish`** 文件夹打成 zip 即可分发。

### 方式二：Tauri 桌面安装包（可选，需 Rust）

带原生窗口的安装包，体验更接近桌面应用。

**额外环境：** Node.js、Rust（[rustup.rs](https://rustup.rs/)）

```powershell
pip install -r requirements.txt
python desktop/build_backend.py

cd desktop/tauri
npm install
npm run build
```

安装包输出在 `desktop/tauri/src-tauri/target/release/bundle/`。

---

## 开发运行

### Web 模式

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

浏览器打开：<http://127.0.0.1:8000>

### 桌面开发模式

```powershell
python -m app.desktop_runtime
```

浏览器打开：<http://127.0.0.1:18555>

### 运行测试

```powershell
pytest
```

---

## 数据模型

主要实体：

- **User** — 用户（桌面模式自动创建本地用户）
- **Video / Subtitle** — 视频与字幕
- **ReadingDocument / ReadingBlock** — 阅读文档与段落
- **WordBook / WordBookEntry** — 词书与词条
- **VocabItem** — 生词卡片（含 FSRS 复习字段）
- **ReviewLog** — 复习记录
- **LibraryBook** — 内置书库

---

## Chrome 扩展（可选）

`extension/` 目录为浏览器扩展，可在 YouTube / B 站 / 英文网页上边看边收藏生词。

**桌面 EXE 版不需要安装扩展**，所有功能已在应用内提供。扩展仅在使用 Web 开发模式、希望在原站页面学习时使用。

安装方式见 [extension/README.md](extension/README.md)。

---

## 环境变量（高级）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_MODE` | `desktop` | `desktop` 或 `web` |
| `DESKTOP_PORT` | `18555` | 桌面模式端口 |
| `VIDEOENGLISH_HOME` | `%LOCALAPPDATA%\VideoEnglish` | 数据目录 |
| `DATABASE_URL` | 自动 | 数据库连接串 |

---

## 许可与说明

本项目为 **个人自用** 工具。内置词书数据来源于开源词库（如 kylebing-vocab），书籍资源来自公开仓库。

打包分发时请遵守相关平台服务条款（B 站、YouTube 等）及翻译 API 使用规范。


阅读、词书模块数据来源
100 篇小说
优先读仓库里的 app/assets/books/gutenberg/*.txt。本地有就不再去 Gutenberg 下载；只有缺文件时才会退回下载。

词典
构建时跑 ensure_dictionary_db.py：

已有可用的 dictionary.db → 直接用
否则用本地 ecdict.csv 转成 dictionary.db
再没有就下载 ECDICT 再转换
运行时查词读的是磁盘上的 dictionary.db（或 csv），不会进 Neon。
词书
单词内容从 app/assets/curated/wordbooks/*.json 读。Neon 只存用户壳子、进度、星标等，不整本导入词条。

Neon：用户、登录、阅读进度、PK、词书进度等用户数据。