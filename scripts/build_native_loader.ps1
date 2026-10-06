[CmdletBinding()]
param([string]$RustCompiler = 'rustc')
$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot -Parent
$Source = Join-Path $Repo 'runtime\native-loader\dllpath-rust-agent.rs'
$Output = Join-Path $Repo 'runtime\native-loader\dllpath-rust-agent.dll'
$TempDir = Join-Path $Repo 'runtime\tmp'
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$PreviousTemp = $env:TEMP
$PreviousTmp = $env:TMP
try {
    $env:TEMP = $TempDir
    $env:TMP = $TempDir
    # LLVM's bundled linker avoids needing a separately installed C compiler.
    & $RustCompiler --crate-type cdylib --edition 2021 -C opt-level=2 -C panic=abort -C strip=symbols -C linker=rust-lld -C link-self-contained=yes $Source -o $Output
    if ($LASTEXITCODE -ne 0) { throw 'Native loader compilation failed' }
    Get-FileHash -LiteralPath $Output -Algorithm SHA256
} finally {
    $env:TEMP = $PreviousTemp
    $env:TMP = $PreviousTmp
}
