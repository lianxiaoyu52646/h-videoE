$env:ANDROID_HOME = "$env:USERPROFILE\.android\sdk"
$env:ANDROID_SDK_ROOT = "$env:USERPROFILE\.android\sdk"

$sdkManager = "$env:ANDROID_HOME\cmdline-tools\latest\bin\sdkmanager.bat"

Write-Host "Testing sdkmanager with --no_https..."
& $sdkManager --no_https --list 2>&1 | Select-Object -First 30

Write-Host "`nTrying to install platform-tools..."
"y" | & $sdkManager --no_https "platform-tools" 2>&1

Write-Host "`nDone."
