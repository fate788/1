Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Fixed-purpose launcher: no user-supplied command or arguments are accepted.
if ($args.Count -ne 0) {
    Write-Host 'This launcher accepts no command-line arguments.' -ForegroundColor Red
    exit 2
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'This launcher is not running with an elevated administrator token.' -ForegroundColor Red
    Write-Host 'Open Windows PowerShell with Run as administrator, then execute this fixed script.' -ForegroundColor Yellow
    exit 740
}

$pythonPath = 'C:\Users\13162\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$scriptPath = 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\diagnostic-package\observe_modifier_startup.py'
$workDirectory = 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\target-observation'
$targetPath = 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\target-observation\SC2_Inv_260804SPt19_1316241517.exe'
$referenceDllPath = 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\finalized\ARCHIVE-260804\lua53-64.dll'
$launcherLog = 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\diagnostic-package\launcher-output.log'
$expectedTargetHash = 'cea1493191bbd5513f556413d167e2fad81879e91294dff7c5cdca61497cc9ef'
$expectedDllHash = '436f6bf9ac414e7e7259bef4f6e287702a41e1fddbdd9af7d43350d47539a3c9'
$expectedScriptHash = '999cc443743459a2cd1a8796e1880ef82299839de699216353611f2a98f642b2'

foreach ($requiredPath in @($pythonPath, $scriptPath, $workDirectory, $targetPath, $referenceDllPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        Write-Host "Required path is missing: $requiredPath" -ForegroundColor Red
        exit 3
    }
}

function Get-Sha256([string] $path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if ((Get-Sha256 $scriptPath) -ne $expectedScriptHash) {
    Write-Host 'Observer script hash mismatch; refusing to run.' -ForegroundColor Red
    exit 4
}
if ((Get-Sha256 $targetPath) -ne $expectedTargetHash) {
    Write-Host 'Target EXE hash mismatch; refusing to run.' -ForegroundColor Red
    exit 5
}
if ((Get-Sha256 $referenceDllPath) -ne $expectedDllHash) {
    Write-Host 'Reference Lua DLL hash mismatch; refusing to run.' -ForegroundColor Red
    exit 6
}

$existing = Get-Process -Name 'SC2_Inv_260804SPt19_1316241517' -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Write-Host 'A process with the target modifier name is already running; refusing a second launch.' -ForegroundColor Red
    exit 7
}

$startTime = (Get-Date).ToString('o')
$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $pythonPath
$psi.Arguments = '"' + $scriptPath + '"'
$psi.WorkingDirectory = $workDirectory
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

$process = [Diagnostics.Process]::new()
$process.StartInfo = $psi
if (-not $process.Start()) {
    Write-Host 'Python observer could not be started.' -ForegroundColor Red
    exit 8
}

$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$process.WaitForExit()
$stdout = $stdoutTask.Result
$stderr = $stderrTask.Result
$endTime = (Get-Date).ToString('o')

@(
    "launcher_start=$startTime"
    "launcher_end=$endTime"
    "python=$pythonPath"
    "script=$scriptPath"
    "working_directory=$workDirectory"
    "python_exit_code=$($process.ExitCode)"
    '--- stdout ---'
    $stdout
    '--- stderr ---'
    $stderr
) | Set-Content -LiteralPath $launcherLog -Encoding UTF8

Write-Host "Observer finished with exit code $($process.ExitCode)."
Write-Host "Run log: $launcherLog"
exit $process.ExitCode
