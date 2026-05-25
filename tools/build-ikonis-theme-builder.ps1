param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$PythonExe = $null
$PythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "py"
        $PythonArgs = @("-3")
    }
}

if (-not $PythonExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "python"
    }
}

if (-not $PythonExe) {
    throw "Python 3 was not found. The Windows Store python alias may be enabled; try running this with py -3 available."
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
