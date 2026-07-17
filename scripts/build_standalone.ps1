# Build portable VideoEnglish.exe for sharing (no Python/Node/Rust required on recipient machine).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Installing Python dependencies..."
python -m pip install -r requirements.txt

Write-Host "==> Building standalone VideoEnglish..."
python desktop/build_standalone.py

$OutDir = Join-Path $Root "dist\VideoEnglish"
$Exe = Join-Path $OutDir "VideoEnglish.exe"
if (-not (Test-Path $Exe)) {
    throw "Build failed: $Exe not found"
}

Write-Host ""
Write-Host "Done."
Write-Host "  Run:       $Exe"
Write-Host "  Share:     zip the folder $OutDir"
Write-Host "  User data: %LOCALAPPDATA%\VideoEnglish\"
