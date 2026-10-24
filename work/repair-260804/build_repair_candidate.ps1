$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = 'C:\Users\13162\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$scriptPath = Join-Path $scriptRoot 'build_repair_candidate.py'
$workPath = $scriptRoot
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw "Python not found: $pythonPath" }
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) { throw "Build script not found: $scriptPath" }
Push-Location -LiteralPath $workPath
try {
    & $pythonPath $scriptPath
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
