#Requires -RunAsAdministrator
<#
    setup-prod.ps1 — one-time prod-side cutover for Phase 134.

    Run this on the prod box (192.168.0.137) AFTER the code is deployed.
    Idempotent: safe to re-run.

    What it does:
      1. Edits MySQL my.ini bind-address to allow LAN connections
      2. Adds Windows Firewall rule for TCP 3306 limited to LAN subnet
      3. Pauses for you to manually restart MySQL (you start it standalone, not as a service)
      4. Creates fed_app@192.168.0.% with same password as fed_app@localhost

    Daily load and backups are NOT scheduled — run them manually as needed:
      - Daily load: python ./fed_prospector/main.py job daily   (run from project root)
      - Backup:     powershell -ExecutionPolicy Bypass -File backup.ps1
#>

param(
    # Dev box IP — used for both firewall rule and MySQL GRANT.
    # If your DHCP lease shifts, re-run with -DevIp <new-ip>.
    [string]$DevIp    = "192.168.0.250",
    [string]$MySqlBin = "C:\mysql\bin",
    [string]$MySqlIni = "C:\mysql\my.ini"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$EnvFile  = Join-Path $RepoRoot "fed_prospector\.env"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Yellow }
function Skip($msg) { Write-Host "  $msg" -ForegroundColor DarkGray }

# --- Pre-flight ---
Step "Pre-flight"
foreach ($p in @($MySqlIni, $EnvFile)) {
    if (-not (Test-Path $p)) { throw "Missing required file: $p" }
}
Info "Repo root: $RepoRoot"
Info "MySQL ini: $MySqlIni"

# --- Read fed_app password from .env (so LAN user gets same pw as localhost user) ---
$envContent = Get-Content $EnvFile
function Get-EnvVar($key) {
    $line = $envContent | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
    if ($line) { return ($line -replace "^$key=", '').Trim() }
    return $null
}
$dbPassword = Get-EnvVar 'DB_PASSWORD'
if (-not $dbPassword) { throw "DB_PASSWORD not found in $EnvFile" }
Info "Read fed_app password from .env"

# --- Step 1: bind-address ---
Step "1. MySQL bind-address"
$ini = Get-Content $MySqlIni -Raw
$needsRestart = $false
if ($ini -match '(?m)^\s*bind-address\s*=\s*0\.0\.0\.0') {
    Skip "Already 0.0.0.0"
} elseif ($ini -match '(?m)^\s*bind-address\s*=') {
    $ini = $ini -replace '(?m)^\s*bind-address\s*=.*$', 'bind-address=0.0.0.0'
    Set-Content $MySqlIni $ini -NoNewline
    Info "Updated bind-address to 0.0.0.0"
    $needsRestart = $true
} elseif ($ini -match '(?m)^\[mysqld\]') {
    $ini = $ini -replace '(?m)^\[mysqld\]', "[mysqld]`r`nbind-address=0.0.0.0"
    Set-Content $MySqlIni $ini -NoNewline
    Info "Added bind-address=0.0.0.0 under [mysqld]"
    $needsRestart = $true
} else {
    throw "[mysqld] section not found in $MySqlIni"
}

# --- Step 2: firewall ---
Step "2. Firewall rule (TCP 3306 from $DevIp only)"
$ruleName = "FedProspect MySQL Dev"
if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
    Skip "Rule already exists — updating RemoteAddress to $DevIp"
    Set-NetFirewallRule -DisplayName $ruleName -RemoteAddress $DevIp | Out-Null
} else {
    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3306 `
        -RemoteAddress $DevIp -Profile Any | Out-Null
    Info "Created firewall rule"
}

# --- Step 3: pause for MySQL restart ---
if ($needsRestart) {
    Step "3. MySQL restart REQUIRED"
    Write-Host "  bind-address changed. Restart MySQL now using your normal workflow:" -ForegroundColor Yellow
    Write-Host "    1. In another terminal: $MySqlBin\mysqladmin -u root -p shutdown" -ForegroundColor Yellow
    Write-Host "    2. Restart with: $MySqlBin\mysqld --console (or however you usually start it)" -ForegroundColor Yellow
    Read-Host "  Press Enter once MySQL is back up"
} else {
    Step "3. MySQL restart"
    Skip "Not needed (bind-address already correct)"
}

# --- Step 4: GRANT ---
Step "4. GRANT fed_app@$DevIp"
$rootPwd = Read-Host -AsSecureString "  Enter MySQL root password"
$rootPwdPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPwd))

# Use a temp defaults-file so password isn't on the command line
$tmpCnf = [System.IO.Path]::GetTempFileName()
@"
[client]
user=root
password=$rootPwdPlain
host=127.0.0.1
"@ | Set-Content $tmpCnf -Encoding ASCII

$grantSql = @"
CREATE USER IF NOT EXISTS 'fed_app'@'$DevIp' IDENTIFIED BY '$dbPassword';
ALTER USER 'fed_app'@'$DevIp' IDENTIFIED BY '$dbPassword';
GRANT ALL PRIVILEGES ON fed_contracts.* TO 'fed_app'@'$DevIp';
GRANT FILE ON *.* TO 'fed_app'@'$DevIp';
FLUSH PRIVILEGES;
SELECT user, host FROM mysql.user WHERE user='fed_app';
"@

$tmpSql = [System.IO.Path]::GetTempFileName()
Set-Content $tmpSql $grantSql -Encoding ASCII
try {
    & "$MySqlBin\mysql.exe" --defaults-extra-file=$tmpCnf -e "source $tmpSql"
    if ($LASTEXITCODE -ne 0) { throw "GRANT failed (mysql exit $LASTEXITCODE)" }
    Info "Grants applied"
} finally {
    Remove-Item $tmpSql, $tmpCnf -ErrorAction SilentlyContinue
}

# --- Done ---
Step "Done"
Write-Host "  Verify from dev:" -ForegroundColor Green
Write-Host "    mysql -h 192.168.0.137 -u fed_app -p fed_contracts -e `"SELECT 1;`"" -ForegroundColor Green
Write-Host ""
Write-Host "  Daily load + backups are NOT scheduled. Run manually:" -ForegroundColor Green
Write-Host "    python ./fed_prospector/main.py job daily   (daily ETL, run from project root)" -ForegroundColor Green
Write-Host "    .\backup.ps1               (robocopy MySQL data dir to NAS)" -ForegroundColor Green
