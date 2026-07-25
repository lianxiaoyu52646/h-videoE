@echo off
chcp 65001 >nul
echo ========================================
echo   妈宝男英语 Android APK Build Guide
echo ========================================
echo.
echo 项目已准备就绪，以下是构建APK的步骤：
echo.
echo 前置要求：
echo   1. JDK 17 或更高版本
echo   2. Android SDK (包含 platform-tools, platforms;android-34, build-tools;34.0.0)
echo   3. Gradle 8.4 (项目已配置wrapper，会自动下载)
echo.
echo ========================================
echo   方法一：使用 Android Studio (推荐)
echo ========================================
echo.
echo 1. 打开 Android Studio
echo 2. 选择 "Open an Existing Project"
echo 3. 选择目录: %~dp0
echo 4. 等待 Gradle Sync 完成
echo 5. 菜单: Build -^> Build Bundle(s) / APK(s) -^> Build APK(s)
echo 6. APK 生成位置: app\build\outputs\apk\debug\app-debug.apk
echo.
echo ========================================
echo   方法二：使用命令行 (需要先配置环境)
echo ========================================
echo.
echo 1. 配置 JAVA_HOME 环境变量指向 JDK 17
echo 2. 配置 ANDROID_HOME 环境变量指向 Android SDK
echo 3. 在此目录下运行: gradlew.bat assembleDebug
echo 4. APK 生成位置: app\build\outputs\apk\debug\app-debug.apk
echo.
echo ========================================
echo   项目结构说明
echo ========================================
echo.
echo app\src\main\assets\          - Web资源文件(HTML/CSS/JS)
echo   ^|- index.html               - 主页面
echo   ^|- css\styles.css           - 样式文件
echo   ^|- js\                      - JavaScript文件
echo   ^|- dictionary.db            - 本地词典数据库(ECDICT 全量约77万词)
echo   ^|- assets\core_en.json      - 备用词典JSON
echo.
echo app\src\main\java\             - Java源代码
echo   ^|- MainActivity.java        - 主Activity(WebView容器)
echo   ^|- DictionaryDatabaseHelper.java - 词典数据库管理
echo.
echo ========================================
echo   功能说明
echo ========================================
echo.
echo - 阅读练习：内置示例文章，点词即查
echo - 单词本：收藏和管理生词
echo - 本地词典：915个常用词，离线秒查
echo - 联网查询：本地查不到时自动联网翻译
echo - 安卓原生词典：优先使用SQLite数据库查询
echo.
pause
