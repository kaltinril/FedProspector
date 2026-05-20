<#
    daily.ps1 — run the FedProspect daily ETL.

    Mirrors the manual workflow:
        cd c:\git\fedProspect
        .\fed_prospector\.venv\Scripts\activate
        python .\fed_prospector\main.py job daily

    Anchors to the repo root via $PSScriptRoot so it works from any CWD
    (including Windows Task Scheduler). Forwards extra args through to
    `job daily` (e.g. --dry-run, --skip awards_8a).

    Logs all output to logs\daily-YYYY-MM-DD.log.
    Exit code reflects python's exit code so callers (Task Scheduler) see pass/fail.
#>

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Activate the venv (dot-sourced so it affects this shell)
. .\fed_prospector\.venv\Scripts\Activate.ps1

# Ensure logs dir exists and pick today's log file
$logDir  = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ("daily-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

Add-Content -Path $logFile -Value "`n=== Run started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

python .\fed_prospector\main.py job daily @args *>> $logFile
exit $LASTEXITCODE
