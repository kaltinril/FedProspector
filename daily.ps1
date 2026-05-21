<#
    daily.ps1 — run the FedProspect daily ETL.

    Mirrors the manual workflow:
        cd c:\git\fedProspect
        .\fed_prospector\.venv\Scripts\activate
        python .\fed_prospector\main.py job daily

    Anchors to the repo root via $PSScriptRoot so it works from any CWD
    (including Windows Task Scheduler). Forwards extra args through to
    `job daily` (e.g. --dry-run, --skip awards_8a).

    Logs all output to logs\daily-YYYY-MM-DD_HH-mm-ss.log (per-invocation file).
    Exit code reflects python's exit code so callers (Task Scheduler) see pass/fail.
#>

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Activate the venv (dot-sourced so it affects this shell)
. .\fed_prospector\.venv\Scripts\Activate.ps1

# Ensure logs dir exists and pick today's log file
$logDir  = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ("daily-{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss"))

$startTime = Get-Date
Add-Content -Path $logFile -Value "=== Run started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# Force Python to flush stdout/stderr per write so the log captures
# last-second errors before any crash (Task Scheduler / log-redirect case).
$env:PYTHONUNBUFFERED = "1"

# Default to non-zero so the footer is meaningful even if python crashes
# before $LASTEXITCODE is set.
$exitCode = 1
try {
    python .\fed_prospector\main.py job daily @args *>> $logFile
    $exitCode = $LASTEXITCODE
} finally {
    $duration = (Get-Date) - $startTime
    $durStr = "{0:hh\:mm\:ss}" -f $duration
    Add-Content -Path $logFile -Value "=== Run finished: exit code $exitCode at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (duration: $durStr) ==="
}

exit $exitCode
