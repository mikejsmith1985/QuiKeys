<#
.SYNOPSIS
    Build QuiKeys for Windows — produces dist\QuiKeys-windows-vX.Y.Z.zip
.DESCRIPTION
    Requires Python 3.10+ and PyInstaller in the venv.
    Run from the QuiKeys project root.
#>

$ErrorActionPreference = "Stop"
$Version = (Get-Content package.json | ConvertFrom-Json).version
$AppName = "QuiKeys"

Write-Host "=== QuiKeys Windows Build ===" -ForegroundColor Cyan

# ── Virtual environment ──────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& ".venv\Scripts\pip" install --quiet -r requirements.txt

# ── Generate icon ────────────────────────────────────────────────────
Write-Host "Generating icon assets..." -ForegroundColor Yellow
& ".venv\Scripts\python" src\generate_icon.py

# ── PyInstaller ──────────────────────────────────────────────────────
Write-Host "Running PyInstaller..." -ForegroundColor Yellow

$spec_args = @(
    "src\main.py"
    "--name", $AppName
    "--onefile"
    "--windowed"
    "--icon", "$PWD\assets\icon.ico"
    "--add-data", "$PWD\assets;assets"
    "--paths", "src"
    "--hidden-import", "pystray._win32"
    "--hidden-import", "PIL._tkinter_finder"
    "--noconfirm"
    "--distpath", "dist"
    "--workpath", "build\_work"
    "--specpath", "build"
)

& ".venv\Scripts\pyinstaller" @spec_args

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed."
    exit 1
}

# ── Package into ZIP ─────────────────────────────────────────────────
$ZipName = "$AppName-windows-v$Version.zip"
$ZipPath = "dist\$ZipName"

if (Test-Path $ZipPath) { Remove-Item $ZipPath }

Compress-Archive -Path "dist\$AppName.exe" -DestinationPath $ZipPath

Write-Host ""
Write-Host "✅ Build complete: $ZipPath" -ForegroundColor Green
Write-Host "   Distribute this ZIP — users extract and run $AppName.exe (no install needed)."
