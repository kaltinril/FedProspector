<#
    restore-test.ps1 — verify the NAS backup is restorable.

    Pulls the NAS snapshot to a throwaway location, starts a temporary mysqld
    instance against it on a non-default port, and compares row counts on a
    handful of canary tables vs prod. PASS = backup is good.

    Run on dev (must reach both \\diskstation and prod's MySQL on 192.168.0.137).
    Reads DB_PASSWORD and MYSQL_ROOT_PASS from fed_prospector\.env.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\restore-test.ps1
        powershell -ExecutionPolicy Bypass -File .\restore-test.ps1 -RestoreRoot E:\my_test -TestPort 3308
#>

param(
    [string]$NasData       = "\\diskstation\home\fedprospector\mysql",
    [string]$RestoreRoot   = "E:\mysql_restore_test",
    [int]$TestPort         = 3307,
    [string]$ProdHost      = "192.168.0.137",
    [int]$ProdPort         = 3306,
    [string]$DbName        = "fed_contracts",
    [string]$DbUser        = "fed_app",
    [string]$RootUser      = "root",
    [string]$BaseDir       = "E:/mysql",
    [string]$MysqldExe     = "E:\mysql\bin\mysqld.exe",
    [string]$MysqlExe      = "E:\mysql\bin\mysql.exe",
    [string]$MysqladminExe = "E:\mysql\bin\mysqladmin.exe"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Yellow }
function Pass($msg) { Write-Host "  PASS: $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red }

# --- Read passwords from .env ---
$envFile = Join-Path $PSScriptRoot "fed_prospector\.env"
if (-not (Test-Path $envFile)) { throw ".env not found at $envFile" }
function Get-EnvValue([string]$key) {
    $line = Select-String -Path $envFile -Pattern "^$key=(.+)$" | Select-Object -First 1
    if (-not $line) { throw "$key not found in $envFile" }
    $line.Matches[0].Groups[1].Value.Trim()
}
$dbPass   = Get-EnvValue "DB_PASSWORD"
$rootPass = Get-EnvValue "MYSQL_ROOT_PASS"

# --- Pre-flight ---
Step "Pre-flight"
foreach ($p in @($NasData, $MysqldExe, $MysqlExe, $MysqladminExe)) {
    if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}
Info "All paths and binaries reachable"

$portInUse = Get-NetTCPConnection -LocalPort $TestPort -ErrorAction SilentlyContinue
if ($portInUse) { throw "Port $TestPort already in use — pick another with -TestPort." }
Info "Port $TestPort is free"

# --- Wipe + create restore root ---
Step "Wipe / create restore dir"
if (Test-Path $RestoreRoot) {
    Remove-Item $RestoreRoot -Recurse -Force
    Info "Removed existing $RestoreRoot"
}
$dataDir = Join-Path $RestoreRoot "data"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
Info "Created $dataDir"

# --- Pull from NAS ---
Step "Robocopy NAS -> $dataDir"
$rcTimer = [System.Diagnostics.Stopwatch]::StartNew()
robocopy $NasData $dataDir /MIR /MT:8 /R:1 /W:1 /XJ /NFL /NDL /NP /ETA
$rc = $LASTEXITCODE
$rcTimer.Stop()
Info ("Elapsed: {0:hh\:mm\:ss}" -f $rcTimer.Elapsed)
if ($rc -ge 8) { throw "Robocopy failed (exit $rc)" }
Info "Restore data dir populated (robocopy exit $rc)"

# --- Write minimal my.ini ---
# Don't reuse prod's my.ini — it binds to prod's LAN IP, has prod-tuned buffer
# sizes, and references log paths that may not exist here. A minimal ini is
# enough to start mysqld against an already-initialized data dir.
Step "Write test my.ini"
$dataDirFwd = $dataDir -replace "\\", "/"
$logErrFwd  = "$RestoreRoot/error.log" -replace "\\", "/"
$iniPath    = Join-Path $RestoreRoot "my.ini"
@"
[mysqld]
basedir=$BaseDir
datadir=$dataDirFwd
port=$TestPort
bind-address=127.0.0.1
log-error=$logErrFwd
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
secure-file-priv=
"@ | Set-Content -Path $iniPath -Encoding ASCII
Info "Wrote $iniPath (datadir=$dataDirFwd, port=$TestPort, loopback only)"

# --- Start mysqld in background ---
Step "Start temporary mysqld"
$stdoutLog = Join-Path $RestoreRoot "mysqld.stdout.log"
$stderrLog = Join-Path $RestoreRoot "mysqld.stderr.log"
$mysqldProc = Start-Process -FilePath $MysqldExe `
    -ArgumentList "--defaults-file=`"$iniPath`"", "--console" `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError  $stderrLog `
    -PassThru -WindowStyle Hidden
Info "mysqld PID: $($mysqldProc.Id), error log: $logErrFwd"

# Poll port for readiness
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($mysqldProc.HasExited) {
        Get-Content $stderrLog -Tail 30 -ErrorAction SilentlyContinue | Write-Host
        Get-Content (Join-Path $RestoreRoot "error.log") -Tail 30 -ErrorAction SilentlyContinue | Write-Host
        throw "mysqld exited early (code $($mysqldProc.ExitCode)) — see logs above"
    }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $TestPort)
        if ($client.Connected) { $ready = $true; break }
    } catch {} finally { $client.Close() }
}
if (-not $ready) {
    Stop-Process -Id $mysqldProc.Id -Force -ErrorAction SilentlyContinue
    Get-Content (Join-Path $RestoreRoot "error.log") -Tail 30 -ErrorAction SilentlyContinue | Write-Host
    throw "Test mysqld did not come up on port $TestPort within 30s"
}
Info "Test mysqld listening on 127.0.0.1:$TestPort"

# --- Compare row counts ---
Step "Compare row counts (test vs prod)"
$canaryTables = @(
    "opportunity",         # large ETL table — proves bulk data made it
    "usaspending_award",   # huge ETL table — ~28M rows
    "prospect",            # user data
    "app_user",            # user data
    "organization",        # user data
    "saved_search",        # user data
    "etl_load_log"         # operational metadata
)

function Get-Count {
    param([string]$Server, [int]$Port, [string]$Table)
    $sql = "SELECT COUNT(*) FROM $DbName.$Table"
    $env:MYSQL_PWD = $dbPass
    try {
        $out = & $MysqlExe -h $Server -P $Port -u $DbUser -N -B -e $sql 2>&1
        if ($LASTEXITCODE -ne 0) { throw "mysql failed for $Table @ ${Server}:${Port}: $out" }
        [int64]($out.Trim())
    } finally {
        Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    }
}

$allMatch = $true
foreach ($t in $canaryTables) {
    try {
        $prodCnt = Get-Count -Server $ProdHost   -Port $ProdPort -Table $t
        $testCnt = Get-Count -Server "127.0.0.1" -Port $TestPort -Table $t
    } catch {
        Fail "$t — query error: $_"
        $allMatch = $false
        continue
    }
    if ($prodCnt -eq $testCnt) {
        Pass ("{0,-22} {1,12:N0} == {2,12:N0}" -f $t, $prodCnt, $testCnt)
    } else {
        Fail ("{0,-22} prod={1,12:N0}  test={2,12:N0}  diff={3:N0}" -f `
            $t, $prodCnt, $testCnt, ($prodCnt - $testCnt))
        $allMatch = $false
    }
}

# --- Shutdown test mysqld ---
Step "Shutdown test mysqld"
$env:MYSQL_PWD = $rootPass
try {
    & $MysqladminExe -h 127.0.0.1 -P $TestPort -u $RootUser shutdown 2>&1 | Out-Null
} finally {
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
}
$null = Wait-Process -Id $mysqldProc.Id -Timeout 30 -ErrorAction SilentlyContinue
if (-not $mysqldProc.HasExited) {
    Info "Graceful shutdown timed out — forcing stop"
    Stop-Process -Id $mysqldProc.Id -Force
}
Info "Test mysqld stopped"

# --- Summary ---
Step "Result"
if ($allMatch) {
    Write-Host "  RESTORE TEST: PASS — all canary table counts match prod" -ForegroundColor Green
    Write-Host "  Test data left at $RestoreRoot — delete when satisfied:" -ForegroundColor DarkGray
    Write-Host "    Remove-Item $RestoreRoot -Recurse -Force" -ForegroundColor DarkGray
    exit 0
} else {
    Write-Host "  RESTORE TEST: FAIL — see counts above" -ForegroundColor Red
    Write-Host "  Test data left at $RestoreRoot for debugging" -ForegroundColor Yellow
    exit 1
}
