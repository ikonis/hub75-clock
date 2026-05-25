param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$PythonExe = "python"
$PythonArgs = @()
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
        $PythonArgs = @("-3")
    } else {
        throw "Python was not found. Install Python 3 first."
    }
}

if (-not $SkipInstall) {
    & $PythonExe @PythonArgs -m pip install --upgrade pyinstaller paramiko
}

& $PythonExe @PythonArgs -m PyInstaller `
    --onefile `
    --name ikonis-theme-builder `
    --add-data "tools/theme-server.py;tools" `
    --add-data "tools/theme-builder.html;tools" `
    tools/ikonis-theme-builder.py

Write-Host ""
Write-Host "Built: $RepoRoot\dist\ikonis-theme-builder.exe"
Write-Host "First run to save your SSH password:"
Write-Host "  .\dist\ikonis-theme-builder.exe --save-password"
