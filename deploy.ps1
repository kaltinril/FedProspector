$target = "192.168.0.137"
$credFile = "$PSScriptRoot\.deploy-cred.xml"

if (-not (Test-Path $credFile)) {
    Write-Host "No credential file found. Creating one now..." -ForegroundColor Yellow
    Get-Credential -UserName "fedprospecttransfer" -Message "Enter transfer password" | Export-Clixml $credFile
}

$cred = Import-Clixml $credFile
$user = $cred.UserName
$pass = $cred.GetNetworkCredential().Password

# Build the UI into the API's wwwroot (Option B single-port) BEFORE robocopy so the
# transfer picks up the freshly built SPA. Vite's build.outDir + emptyOutDir handle
# output location and stale-asset cleanup, so this is idempotent.
Write-Host "Building UI (npm run build -> api wwwroot)..." -ForegroundColor Green
Push-Location "$PSScriptRoot\ui"
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "UI build failed (exit code $LASTEXITCODE). Aborting deploy." -ForegroundColor Red
        Pop-Location
        exit 1
    }
} finally {
    Pop-Location
}
Write-Host "UI build complete." -ForegroundColor Green

# Build the C# API on dev so the compiled binaries ship with the copy — prod then
# just needs 'start', no manual 'build api'. The service manager runs `dotnet run
# --no-build`, which uses these Debug binaries. (/XF excludes appsettings.Local.json
# from the copy, so prod keeps its own secrets even though bin/ ships.)
Write-Host "Building API (dotnet build)..." -ForegroundColor Green
& dotnet build "$PSScriptRoot\api\src\FedProspector.Api" --verbosity quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "API build failed (exit code $LASTEXITCODE). Aborting deploy." -ForegroundColor Red
    exit 1
}
Write-Host "API build complete." -ForegroundColor Green

# Disconnect stale connections before authenticating
foreach ($share in @("gitshare")) {
    net use "\\$target\$share" /delete /y 2>$null | Out-Null
}

# Authenticate to target
net use "\\$target\gitshare" /user:$user $pass

$totalTimer = [System.Diagnostics.Stopwatch]::StartNew()
Write-Host "Starting transfers..." -ForegroundColor Green

# Robocopy exit codes: 0-7 = success/warnings, 8+ = errors
$jobs = @()

$jobs += Start-Job -Name "Project" -ScriptBlock {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # /XF appsettings.Local.json: this file holds PER-MACHINE secrets — prod's DB
    # creds, JWT key, AND the Kestrel HTTPS/self-signed-cert config. Never overwrite
    # prod's copy with dev's, or every deploy would wipe the SSL setup. Prod owns its
    # own appsettings.Local.json; deploy leaves it untouched.
    # /XD attachments: downloaded attachment files are RUNTIME data, per-machine.
    # A bare folder name excludes ANY directory called "attachments" at any depth
    # (both fed_prospector\data\attachments and a stray data\attachments), so dev's
    # stores never ship to / mix with prod's. Prod downloads its own.
    # (Reference files in data\ — canonical_labor_categories.csv, sca_active_wds.* — still ship.)
    $output = robocopy "C:\git\fedProspect" "\\$using:target\gitshare\fedProspect" /E /MT:16 /J /R:1 /W:1 /ETA /XD ".git" "node_modules" "__pycache__" ".venv" "attachments" /XF "appsettings.Local.json"
    $exitCode = $LASTEXITCODE
    $sw.Stop()
    [PSCustomObject]@{ Output = ($output -join "`r`n"); Elapsed = $sw.Elapsed; ExitCode = $exitCode }
}

# Wait and report
$hasErrors = $false
foreach ($job in $jobs) {
    $job | Wait-Job | Out-Null
    $result = Receive-Job $job
    Write-Host "`n=== $($job.Name) ===" -ForegroundColor Cyan
    Write-Host $result.Output
    if ($result.ExitCode -ge 8) {
        Write-Host ("  FAILED (exit code {0})" -f $result.ExitCode) -ForegroundColor Red
        $hasErrors = $true
    } else {
        Write-Host ("  OK (exit code {0})" -f $result.ExitCode) -ForegroundColor Green
    }
    Write-Host ("  Time: {0:hh\:mm\:ss}" -f $result.Elapsed) -ForegroundColor Yellow
    Remove-Job $job
}

if ($hasErrors) {
    Write-Host "`nOne or more transfers failed. Skipping post-copy fixes." -ForegroundColor Red
    net use "\\$target\gitshare" /delete /y 2>$null | Out-Null
    exit 1
}

Write-Host "`nApplying post-copy fixes..." -ForegroundColor Green

# --- Post-copy fixes on target ---

# Fix: Rewrite prod-specific values in .env (deploy includes .env, but a few
# values diverge between dev and prod machines)
#   - DB_HOST: dev points at prod IP; prod is localhost to itself
#   - MYSQL_BIN_DIR: dev has MySQL on E:\, prod has it on C:\
$envFile = "\\$target\gitshare\fedProspect\fed_prospector\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    $newEnvContent = $envContent `
        -replace "(?m)^DB_HOST=.*$", "DB_HOST=localhost" `
        -replace "(?m)^MYSQL_BIN_DIR=.*$", "MYSQL_BIN_DIR=C:\mysql\bin"
    if ($newEnvContent -ne $envContent) {
        Set-Content $envFile $newEnvContent -NoNewline
        Write-Host "  Rewrote prod-specific values in .env (DB_HOST, MYSQL_BIN_DIR)" -ForegroundColor Yellow
    } else {
        Write-Host "  Prod-specific .env values already correct" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  No fed_prospector\.env found on prod (skipping .env rewrites)" -ForegroundColor DarkGray
}

# Safety net for appsettings.Local.json. As of the /XF exclusion above this file is
# NO LONGER copied from dev — prod owns its own (DB creds, JWT key, Kestrel HTTPS
# cert config). This block now only normalizes prod's existing file: fed_app is
# granted @'localhost' so the connection must use loopback. On a correctly
# configured prod box this is an idempotent no-op; it stays to self-heal an older
# file that still had a LAN Server= value.
$appSettings = "\\$target\gitshare\fedProspect\api\src\FedProspector.Api\appsettings.Local.json"
if (Test-Path $appSettings) {
    $content = Get-Content $appSettings -Raw
    $orig = $content
    $content = $content -replace "Server=[^;]+", "Server=localhost"
    if ($content -notmatch "MaxPoolSize") {
        $content = $content -replace "(SslMode=None;AllowPublicKeyRetrieval=True)", "`$1;MaxPoolSize=50;MinPoolSize=5"
    }
    if ($content -ne $orig) {
        Set-Content $appSettings $content -NoNewline
        Write-Host "  Rewrote prod-specific appsettings (Server=localhost, pool limits)" -ForegroundColor Yellow
    } else {
        Write-Host "  Prod-specific appsettings values already correct" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  No appsettings.Local.json found (ok if not yet configured)" -ForegroundColor DarkGray
}

# Disconnect shares
net use "\\$target\gitshare" /delete /y 2>$null | Out-Null

$totalTimer.Stop()
Write-Host ("`nTotal time: {0:hh\:mm\:ss}" -f $totalTimer.Elapsed) -ForegroundColor Green
Write-Host "Done! Restart the C# API on prod to pick up the new code." -ForegroundColor Green
