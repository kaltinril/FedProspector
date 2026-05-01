<#
    backup.ps1 — robocopy MySQL data dir from prod to NAS.

    Run manually on prod whenever a backup snapshot is wanted (before risky
    operations, schema changes, etc.).

    Caveat: this is a HOT copy of a running InnoDB instance — it can capture
    inconsistent state across files. Acceptable as a "good enough" snapshot
    for a small-biz workload. For a guaranteed-consistent copy, stop MySQL
    first or hold FLUSH TABLES WITH READ LOCK during the copy.
#>

param(
    [string]$Source = "C:\mysql\data",
    [string]$Dest   = "\\diskstation\home\fedprospector\mysql",
    [string]$IniSource = "C:\mysql\my.ini",
    [string]$IniDest   = "\\diskstation\home\fedprospector\my.ini"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Yellow }

Step "Pre-flight"
if (-not (Test-Path $Source))   { throw "Source not found: $Source" }
if (-not (Test-Path $IniSource)) { throw "MySQL ini not found: $IniSource" }

# Refuse to run while MySQL is up — backup workflow requires DB stopped.
# Mirrors the is_running() pattern from fed_prospector.py.
if (Get-Process -Name "mysqld" -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "  ABORT: mysqld.exe is running." -ForegroundColor Red
    Write-Host "  Stop MySQL first, then re-run backup.ps1:" -ForegroundColor Red
    Write-Host "    python ./fed_prospector.py stop db" -ForegroundColor Red
    Write-Host ""
    throw "MySQL must be stopped before running backup."
}
Info "MySQL is stopped (good)"

# Make sure NAS share root exists / is reachable
$destParent = Split-Path $Dest -Parent
if (-not (Test-Path $destParent)) {
    throw "NAS path not reachable: $destParent  (check share mount / credentials)"
}
if (-not (Test-Path $Dest)) {
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
}
Info "Source: $Source"
Info "Dest:   $Dest"

Step "Robocopy MySQL data dir"
$timer = [System.Diagnostics.Stopwatch]::StartNew()
robocopy $Source $Dest /MIR /MT:8 /R:1 /W:1 /XJ /NFL /NDL /NP /ETA
$rc = $LASTEXITCODE
$timer.Stop()
Info ("Elapsed: {0:hh\:mm\:ss}" -f $timer.Elapsed)

# Robocopy: 0-7 = success/warnings, 8+ = errors
if ($rc -ge 8) { throw "Robocopy failed (exit $rc)" }
Info "Data dir copied (robocopy exit $rc)"

Step "Copy my.ini"
Copy-Item -Path $IniSource -Destination $IniDest -Force
Info "Copied $IniSource -> $IniDest"

Step "Done"
Write-Host "  Snapshot at $Dest" -ForegroundColor Green
Write-Host "  To restore: stop MySQL, replace data dir + my.ini from NAS, start MySQL." -ForegroundColor Green
