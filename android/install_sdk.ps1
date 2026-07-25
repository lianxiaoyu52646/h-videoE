$env:ANDROID_HOME = "$env:USERPROFILE\.android\sdk"
$env:ANDROID_SDK_ROOT = "$env:USERPROFILE\.android\sdk"

$sdkManager = "$env:ANDROID_HOME\cmdline-tools\latest\bin\sdkmanager.bat"

Write-Host "Installing Android SDK components using TUNA mirror..."
Write-Host "  proxy: mirrors.tuna.tsinghua.edu.cn:80"

$packages = @(
    "platform-tools",
    "platforms;android-34",
    "build-tools;34.0.0"
)

foreach ($pkg in $packages) {
    Write-Host "`nInstalling $pkg..."
    "y" | & $sdkManager --no_https --proxy=http --proxy_host=mirrors.tuna.tsinghua.edu.cn --proxy_port=80 $pkg 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $pkg installed successfully"
    } else {
        Write-Host "  $pkg installation may have issues (exit code: $LASTEXITCODE)"
    }
}

Write-Host "`n========================================"
Write-Host "Installed packages:"
& $sdkManager --list_installed 2>&1 | Select-Object -First 30
