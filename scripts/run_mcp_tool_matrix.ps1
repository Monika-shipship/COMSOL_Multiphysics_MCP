[CmdletBinding()]
param(
    [string]$ComsolRoot = 'D:\Program Files\COMSOL\COMSOL52a\Multiphysics',
    [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'

if (-not $PythonPath) {
    if ($env:COMSOL_MCP_PYTHON) {
        $PythonPath = $env:COMSOL_MCP_PYTHON
    }
    else {
        $PythonPath = Join-Path $env:USERPROFILE '.codex\mcp\COMSOL_Multiphysics_MCP_VENV\Scripts\python.exe'
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Compatible Python runtime not found: $PythonPath"
}

$ServerExecutable = Join-Path $ComsolRoot 'bin\win64\comsolmphserver.exe'
if (-not (Test-Path -LiteralPath $ServerExecutable -PathType Leaf)) {
    throw "COMSOL 5.2a server executable not found: $ServerExecutable"
}

$MatrixScript = Join-Path $PSScriptRoot 'run_mcp_tool_matrix.py'
& $PythonPath $MatrixScript --comsol-root $ComsolRoot
exit $LASTEXITCODE
