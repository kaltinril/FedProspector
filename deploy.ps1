$target = "192.168.0.137"
$credFile = "$PSScriptRoot\.deploy-cred.xml"

if (-not (Test-Path $credFile)) {
    Write-Host "No credential file found. Creating one now..." -ForegroundColor Yellow
    Get-Credential -UserName "fedprospecttransfer" -Message "Enter transfer password" | Export-Clixml $credFile
}

$cred = Import-Clixml $credFile
$user = $cred.UserName
$pass = $cred.GetNetworkCredential().Password

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
    $output = robocopy "C:\git\fedProspect" "\\$using:target\gitshare\fedProspect" /E /MT:16 /J /R:1 /W:1 /ETA /XD ".git" "node_modules" "__pycache__" ".venv" /XF ".env"
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

# Fix 4: Ensure connection string has pool limits
$appSettings = "\\$target\gitshare\fedProspect\api\src\FedProspector.Api\appsettings.Local.json"
if (Test-Path $appSettings) {
    $content = Get-Content $appSettings -Raw
    if ($content -notmatch "MaxPoolSize") {
        $content = $content -replace "(SslMode=None;AllowPublicKeyRetrieval=True)", "`$1;MaxPoolSize=50;MinPoolSize=5"
        Set-Content $appSettings $content -NoNewline
        Write-Host "  Added connection pool limits to appsettings" -ForegroundColor Yellow
    } else {
        Write-Host "  Connection pool limits already set" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  No appsettings.Local.json found (ok if not yet configured)" -ForegroundColor DarkGray
}

# Disconnect shares
net use "\\$target\gitshare" /delete /y 2>$null | Out-Null

$totalTimer.Stop()
Write-Host ("`nTotal time: {0:hh\:mm\:ss}" -f $totalTimer.Elapsed) -ForegroundColor Green
Write-Host "Done! Restart the C# API on prod to pick up the new code." -ForegroundColor Green
