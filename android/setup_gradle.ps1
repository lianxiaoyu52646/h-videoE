$ErrorActionPreference = "Stop"

$gradleVersion = "8.4"
$gradleZip = "gradle-$gradleVersion-bin.zip"
$gradleUrl = "https://mirrors.aliyun.com/gradle/$gradleZip"
$gradleUserHome = "$env:USERPROFILE\.gradle"
$wrapperDir = "$gradleUserHome\wrapper\dists\gradle-$gradleVersion-bin"

Write-Host "Downloading Gradle $gradleVersion from Alibaba mirror..."
$tempZip = "$env:TEMP\$gradleZip"

if (-not (Test-Path $tempZip)) {
    Invoke-WebRequest -Uri $gradleUrl -OutFile $tempZip -UseBasicParsing
    Write-Host "Download complete."
} else {
    Write-Host "Gradle zip already downloaded."
}

Write-Host "Extracting Gradle..."
$gradleHome = "$env:USERPROFILE\.gradle\gradle-$gradleVersion"
if (Test-Path $gradleHome) {
    Remove-Item -Path $gradleHome -Recurse -Force
}
Expand-Archive -Path $tempZip -DestinationPath "$env:USERPROFILE\.gradle" -Force

Write-Host "Gradle installed at: $gradleHome"
Write-Host "Gradle version:"
& "$gradleHome\bin\gradle.bat" --version

Write-Host "`nDownloading gradle-wrapper.jar..."
$wrapperJarUrl = "https://raw.githubusercontent.com/gradle/gradle/v$gradleVersion/gradle/wrapper/gradle-wrapper.jar"
$wrapperJarPath = "d:\lian\praPro\h-videoE\android\gradle\wrapper\gradle-wrapper.jar"

try {
    Invoke-WebRequest -Uri $wrapperJarUrl -OutFile $wrapperJarPath -UseBasicParsing
    Write-Host "gradle-wrapper.jar downloaded."
} catch {
    Write-Host "Failed to download gradle-wrapper.jar from GitHub, trying alternative..."
    $altUrl = "https://mirrors.aliyun.com/maven2/org/gradle/gradle-wrapper/$gradleVersion/gradle-wrapper-$gradleVersion.jar"
    try {
        Invoke-WebRequest -Uri $altUrl -OutFile $wrapperJarPath -UseBasicParsing
        Write-Host "gradle-wrapper.jar downloaded from Alibaba mirror."
    } catch {
        Write-Host "Alternative download also failed. We'll use local gradle directly."
    }
}

Write-Host "`nDone!"
