@echo off
chcp 65001 >nul
echo ========================================
echo   妈宝男英语 APK Build Script
echo ========================================
echo.

set ANDROID_HOME=%USERPROFILE%\.android\sdk
set ANDROID_SDK_ROOT=%USERPROFILE%\.android\sdk
set JAVA_HOME=%JAVA_HOME%

echo [1/4] Checking Java...
if "%JAVA_HOME%"=="" (
    echo ERROR: JAVA_HOME not set
    echo Please install JDK 17 or higher
    pause
    exit /b 1
)
echo Java: %JAVA_HOME%
echo.

echo [2/4] Checking Android SDK...
if not exist "%ANDROID_HOME%\cmdline-tools\latest\bin\sdkmanager.bat" (
    echo Android SDK not found, installing...
    
    set "ZIP_FILE=%TEMP%\commandlinetools-win.zip"
    if not exist "%ZIP_FILE%" (
        echo Downloading Android command-line tools...
        echo Please download manually from:
        echo   https://developer.android.com/studio#command-tools
        echo Or use a mirror:
        echo   https://mirrors.tuna.tsinghua.edu.cn/android/repository/
        echo.
        echo Then place the zip at: %ZIP_FILE%
        pause
        exit /b 1
    )
    
    echo Extracting...
    if not exist "%ANDROID_HOME%" mkdir "%ANDROID_HOME%"
    if not exist "%ANDROID_HOME%\cmdline-tools" mkdir "%ANDROID_HOME%\cmdline-tools"
    
    powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP%\android-sdk-temp' -Force"
    move "%TEMP%\android-sdk-temp\cmdline-tools" "%ANDROID_HOME%\cmdline-tools\latest"
    rmdir /s /q "%TEMP%\android-sdk-temp"
)
echo Android SDK: %ANDROID_HOME%
echo.

echo [3/4] Installing SDK components...
set SDK_MANAGER=%ANDROID_HOME%\cmdline-tools\latest\bin\sdkmanager.bat

if not exist "%ANDROID_HOME%\platform-tools" (
    echo Installing platform-tools...
    echo y | "%SDK_MANAGER%" --no_https --proxy=http --proxy_host=mirrors.tuna.tsinghua.edu.cn --proxy_port=80 "platform-tools"
)

if not exist "%ANDROID_HOME%\platforms\android-34" (
    echo Installing android-34 platform...
    echo y | "%SDK_MANAGER%" --no_https --proxy=http --proxy_host=mirrors.tuna.tsinghua.edu.cn --proxy_port=80 "platforms;android-34"
)

if not exist "%ANDROID_HOME%\build-tools\34.0.0" (
    echo Installing build-tools 34.0.0...
    echo y | "%SDK_MANAGER%" --no_https --proxy=http --proxy_host=mirrors.tuna.tsinghua.edu.cn --proxy_port=80 "build-tools;34.0.0"
)
echo.

echo [4/4] Building APK...
cd /d "%~dp0"
call gradlew.bat assembleDebug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   Build Success!
    echo ========================================
    echo APK location:
    echo   %~dp0app\build\outputs\apk\debug\app-debug.apk
    echo.
) else (
    echo.
    echo ========================================
    echo   Build Failed!
    echo ========================================
    echo Please check the error messages above.
)

pause
