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
foreach ($share in @("gitshare", "mysql", "attachments")) {
    net use "\\$target\$share" /delete /y 2>$null | Out-Null
}

# Authenticate to target
net use "\\$target\gitshare" /user:$user $pass
net use "\\$target\mysql" /user:$user $pass
net use "\\$target\attachments" /user:$user $pass

$totalTimer = [System.Diagnostics.Stopwatch]::StartNew()
Write-Host "Starting transfers..." -ForegroundColor Green

# Run all three robocopy jobs in parallel, each timed
# Robocopy exit codes: 0-7 = success/warnings, 8+ = errors
$jobs = @()

$jobs += Start-Job -Name "Project" -ScriptBlock {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $output = robocopy "C:\git\fedProspect" "\\$using:target\gitshare\fedProspect" /E /MT:16 /J /R:1 /W:1 /ETA /XD ".git" "node_modules" "__pycache__" ".venv"
    $exitCode = $LASTEXITCODE
    $sw.Stop()
    [PSCustomObject]@{ Output = ($output -join "`r`n"); Elapsed = $sw.Elapsed; ExitCode = $exitCode }
}

$jobs += Start-Job -Name "MySQL" -ScriptBlock {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $output = robocopy "E:\mysql" "\\$using:target\mysql" /E /MT:8 /J /R:1 /W:1 /ETA
    $exitCode = $LASTEXITCODE
    $sw.Stop()
    [PSCustomObject]@{ Output = ($output -join "`r`n"); Elapsed = $sw.Elapsed; ExitCode = $exitCode }
}

$jobs += Start-Job -Name "Attachments" -ScriptBlock {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $output = robocopy "E:\fedprospector\attachments" "\\$using:target\attachments\attachments" /E /MT:8 /J /R:1 /W:1 /ETA
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
    net use "\\$target\mysql" /delete /y 2>$null | Out-Null
    net use "\\$target\attachments" /delete /y 2>$null | Out-Null
    exit 1
}

Write-Host "`nApplying post-copy fixes..." -ForegroundColor Green

# --- Post-copy fixes on target ---

# Fix 1: Rewrite E:\mysql -> C:\mysql in my.ini
$myIni = "\\$target\mysql\my.ini"
if (Test-Path $myIni) {
    (Get-Content $myIni) -replace [regex]::Escape("E:\mysql"), "C:\mysql" | Set-Content $myIni
    Write-Host "  Fixed my.ini paths" -ForegroundColor Yellow
} else {
    Write-Host "  WARNING: my.ini not found at $myIni" -ForegroundColor Red
}

# Fix 2: Delete InnoDB redo logs (MySQL regenerates on start)
$redoDir = "\\$target\mysql\data\#innodb_redo"
if (Test-Path $redoDir) {
    Remove-Item "$redoDir\*" -Force -Recurse
    Write-Host "  Cleared InnoDB redo logs" -ForegroundColor Yellow
} else {
    Write-Host "  No redo log dir found (ok if first deploy)" -ForegroundColor DarkGray
}

# Fix 3: Update .env paths
$envFile = "\\$target\gitshare\fedProspect\fed_prospector\.env"
if (Test-Path $envFile) {
    $content = Get-Content $envFile -Raw
    $content = $content -replace "MYSQL_BIN_DIR=E:\\mysql\\bin", "MYSQL_BIN_DIR=C:\mysql\bin"
    $content = $content -replace "ATTACHMENT_DIR=E:\\fedprospector\\attachments", "ATTACHMENT_DIR=C:\fedprospector\attachments"
    Set-Content $envFile $content -NoNewline
    Write-Host "  Fixed .env paths" -ForegroundColor Yellow
} else {
    Write-Host "  WARNING: .env not found at $envFile" -ForegroundColor Red
}

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
net use "\\$target\mysql" /delete /y 2>$null | Out-Null
net use "\\$target\attachments" /delete /y 2>$null | Out-Null

$totalTimer.Stop()
Write-Host ("`nTotal time: {0:hh\:mm\:ss}" -f $totalTimer.Elapsed) -ForegroundColor Green
Write-Host "Done! Start MySQL on target with: C:\mysql\bin\mysqld --console" -ForegroundColor Green
