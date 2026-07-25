$ErrorActionPreference = "Stop"

$androidHome = "$env:USERPROFILE\.android\sdk"
$cmdlineToolsDir = "$androidHome\cmdline-tools\latest"

Write-Host "Android SDK will be installed to: $androidHome"

if (-not (Test-Path $androidHome)) {
    New-Item -ItemType Directory -Path $androidHome -Force | Out-Null
}

$tempZip = "$env:TEMP\commandlinetools-win.zip"

if (-not (Test-Path $tempZip)) {
    Write-Host "Downloading Android command-line tools..."
    $zipUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
}

Write-Host "Extracting..."
$tempExtract = "$env:TEMP\android-cmdline-tools"
if (Test-Path $tempExtract) {
    Remove-Item -Path $tempExtract -Recurse -Force
}
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

$toolsDir = "$androidHome\cmdline-tools"
if (-not (Test-Path $toolsDir)) {
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
}

$latestDir = "$toolsDir\latest"
if (Test-Path $latestDir) {
    Remove-Item -Path $latestDir -Recurse -Force
}

Move-Item -Path "$tempExtract\cmdline-tools" -Destination $latestDir -Force

Write-Host "Setting environment variables..."
$env:ANDROID_HOME = $androidHome
$env:ANDROID_SDK_ROOT = $androidHome
$env:PATH = "$latestDir\bin;$androidHome\platform-tools;$env:PATH"

Write-Host "Accepting licenses and installing SDK components..."
$sdkManager = "$latestDir\bin\sdkmanager.bat"

Write-Host "  - Accepting licenses..."
"y" | & $sdkManager --licenses 2>&1 | Out-Null

Write-Host "  - Installing platform-tools..."
& $sdkManager "platform-tools" 2>&1 | Out-Null

Write-Host "  - Installing platforms;android-34..."
& $sdkManager "platforms;android-34" 2>&1 | Out-Null

Write-Host "  - Installing build-tools;34.0.0..."
& $sdkManager "build-tools;34.0.0" 2>&1 | Out-Null

Write-Host ""
Write-Host "========================================"
Write-Host "Android SDK setup complete!"
Write-Host "ANDROID_HOME=$androidHome"
Write-Host "========================================"

$sdkManagerPath = "$latestDir\bin\sdkmanager.bat"
& $sdkManagerPath --list_installed
