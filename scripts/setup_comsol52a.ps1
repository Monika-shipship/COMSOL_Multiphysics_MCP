[CmdletBinding()]
param([string]$Python = 'python', [switch]$BuildLoader)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot -Parent
$EnvDir = Join-Path $Repo 'runtime\python52a'
$TempDir = Join-Path $Repo 'runtime\tmp'
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$OldTemp = $env:TEMP
$OldTmp = $env:TMP
try {
    $env:TEMP = $TempDir
    $env:TMP = $TempDir
    & $Python -m venv $EnvDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
    & (Join-Path $EnvDir 'Scripts\python.exe') -m pip install --no-cache-dir -r (Join-Path $Repo 'requirements-comsol52a.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    if ($BuildLoader) { & (Join-Path $PSScriptRoot 'build_native_loader.ps1') }
} finally {
    $env:TEMP = $OldTemp
    $env:TMP = $OldTmp
}
